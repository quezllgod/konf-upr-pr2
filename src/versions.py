"""Проверка SemVer и диапазонов npm без сторонних библиотек."""
import operator
import re

from .errors import AppError

COMPONENTS = 3
PATCH_INDEX = 2
MINOR_INDEX = 1
DECIMAL = r'(0|[1-9][0-9]*)'
PATTERN = rf'v?{DECIMAL}\.{DECIMAL}\.{DECIMAL}'
IDENTIFIER = r'[0-9A-Za-z-]+'
SUFFIX = (rf'(?:-({IDENTIFIER}(?:\.{IDENTIFIER})*))?'
          rf'(?:\+{IDENTIFIER}(?:\.{IDENTIFIER})*)?')
OPERATORS = {None: operator.eq, '=': operator.eq, '>': operator.gt,
             '>=': operator.ge, '<': operator.lt, '<=': operator.le}


def version_key(text):
    """Вернуть сравнимый ключ SemVer; build-метаданные не учитываются."""
    match = re.fullmatch(PATTERN + SUFFIX, text)
    if not match:
        raise AppError(f'Нужна версия SemVer X.Y.Z: {text}')
    major, minor, patch, pre = match.groups()
    identifiers = prerelease_key(pre) if pre else ()
    return int(major), int(minor), int(patch), not bool(pre), identifiers


def prerelease_key(text):
    """Числовые prerelease-компоненты предшествуют строковым."""
    parts = text.split('.')
    for part in parts:
        if part.isdigit() and part != str(int(part)):
            raise AppError(f'Ведущий ноль в prerelease: {text}')
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts)


def partial(text):
    """Разобрать частичную версию, оставив только заданные числа."""
    parts = text.removeprefix('v').split('.')
    if len(parts) > COMPONENTS:
        raise AppError(f'Неверный диапазон: {text}')
    values, wildcard = [], False
    for item in parts:
        if item.lower() in {'x', '*'}:
            wildcard = True
        elif re.fullmatch(DECIMAL, item) and not wildcard:
            values.append(int(item))
        else:
            raise AppError(f'Неподдерживаемый диапазон: {text}')
    return tuple(values)


def increment(core, index):
    """Увеличить компонент и обнулить все младшие компоненты."""
    return core[:index] + (core[index] + 1,) + (0,) * (PATCH_INDEX - index)


def bounds(text):
    """Получить включённую нижнюю и исключённую верхнюю границы."""
    values = partial(text)
    low = values + (0,) * (COMPONENTS - len(values))
    high = increment(low, len(values) - 1) if values else None
    return low, high


def expansion_upper(text, operation):
    """Верхняя граница для ^ и ~ с учётом неполных нулевых версий."""
    values = partial(text)
    if not values:
        return None
    core = values + (0,) * (COMPONENTS - len(values))
    if operation == '~':
        index = min(MINOR_INDEX, len(values) - 1)
    else:
        index = next((i for i, n in enumerate(values) if n),
                     len(values) - 1)
    return increment(core, index)


def upper_key(core):
    """Граница X.Y.Z-0 исключает prerelease следующего диапазона."""
    return (*core, False, ((0, 0),))


def partial_compare(key, operation, low, high):
    """Сравнить полную версию с частичной границей."""
    if operation in {None, '='}:
        return key[:COMPONENTS] >= low and (
            high is None or key < upper_key(high))
    if operation == '>=':
        return key >= (*low, True, ())
    if operation == '>':
        return high is not None and key >= (*high, True, ())
    if operation == '<':
        return key < upper_key(low)
    return high is None or key < upper_key(high)


def token_matches(key, token):
    """Проверить один компаратор, включая расширения ^ и ~."""
    operation, text = re.fullmatch(r'(\^|~|>=|<=|>|<|=)?(.+)', token).groups()
    try:
        exact = version_key(text)
    except AppError:
        exact = None
    if exact is None:
        low, high = bounds(text)
        if operation not in {'^', '~'}:
            return partial_compare(key, operation, low, high)
        high = expansion_upper(text, operation)
        return key >= (*low, True, ()) and (
            high is None or key < upper_key(high))
    if operation in {'^', '~'}:
        core_text = '.'.join(map(str, exact[:COMPONENTS]))
        high = expansion_upper(core_text, operation)
        return key >= exact and key < upper_key(high)
    return OPERATORS[operation](key, exact)


def hyphen_tokens(start, end):
    """Развернуть диапазон через дефис в два компаратора."""
    try:
        version_key(start)
        lower = '>=' + start
    except AppError:
        low, _ = bounds(start)
        lower = '>=' + '.'.join(map(str, low))
    try:
        version_key(end)
        upper = '<=' + end
    except AppError:
        _, high = bounds(end)
        upper = '<' + '.'.join(map(str, high)) if high else '*'
    return [lower, upper]


def group_tokens(group):
    """Нормализовать пробелы и раскрыть hyphen-диапазон."""
    group = re.sub(r'(>=|<=|>|<|=|~|\^)\s+', r'\1', group.strip())
    if ' - ' in group:
        return hyphen_tokens(*group.split(' - ', 1))
    return group.split()


def allows_prerelease(key, tokens):
    """Prerelease разрешён только при явном компараторе той же базы."""
    if key[COMPONENTS]:
        return True
    for token in tokens:
        text = re.sub(r'^[~^<>=]+', '', token)
        try:
            other = version_key(text)
        except AppError:
            continue
        if not other[COMPONENTS] and other[:COMPONENTS] == key[:COMPONENTS]:
            return True
    return False


def matches(version, specifier):
    """Проверить OR-группы; неверный диапазон вызывает AppError."""
    key = version_key(version)
    groups = [group_tokens(group) for group in specifier.split('||')]
    results = []
    for tokens in groups:
        comparisons = [token_matches(key, token) for token in tokens]
        results.append(all(comparisons) and allows_prerelease(key, tokens))
    return any(results)
