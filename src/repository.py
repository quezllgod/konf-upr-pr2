import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import NAME
from .errors import AppError
from .versions import matches, version_key

TIMEOUT = 20
MAX_BYTES = 32 * 1024 * 1024


class NpmRepository:
    def __init__(self, url):
        """Инициализировать объект."""
        self.url = url.rstrip('/')
        self.cache = {}

    def project(self, name):
        """Получить и кешировать метаданные пакета из registry."""
        if name not in self.cache:
            request = Request(self.url + '/' + quote(name, safe=''),
                              headers={'Accept': 'application/json'})
            try:
                with urlopen(request, timeout=TIMEOUT) as response:
                    raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise AppError('Ответ registry слишком большой.')
                result = json.loads(raw)
            except HTTPError as error:
                raise AppError(f'HTTP {error.code}: {name}') from error
            except (OSError, URLError, ValueError) as error:
                raise AppError(f'Ошибка registry: {error}') from error
            if not isinstance(result, dict):
                raise AppError('Registry вернул не объект JSON.')
            if not isinstance(result.get('versions'), dict):
                raise AppError(f'Нет списка версий: {name}')
            validate_tags(result.get('dist-tags', {}))
            self.cache[name] = result
        return self.cache[name]

    def dependencies(self, name, version):
        """Вернуть прямые зависимости заданной версии."""
        info = self.project(name)['versions'].get(version)
        if not isinstance(info, dict):
            raise AppError(f'Версия не найдена: {name}@{version}')
        dependencies = info.get('dependencies', {})
        if not isinstance(dependencies, dict) or any(
                not isinstance(k, str) or not isinstance(v, str)
                for k, v in dependencies.items()):
            raise AppError(f'Неверные dependencies: {name}@{version}')
        if any(not re.fullmatch(NAME, child) for child in dependencies):
            raise AppError(f'Некорректное имя зависимости: {name}')
        return list(dependencies.items())

    def resolve(self, name, specifier):
        """Выбрать версию для указанного ограничения."""
        project = self.project(name)
        tags = project.get('dist-tags', {})
        validate_tags(tags)
        if specifier in tags:
            version = tags[specifier]
            if version not in project['versions']:
                raise AppError(f'Dist-tag: версия отсутствует у {name}')
            return version
        candidates = []
        for version in project['versions']:
            try:
                version_key(version)
            except AppError:
                continue
            if matches(version, specifier):
                candidates.append(version)
        if not candidates:
            raise AppError(f'Нет подходящей версии: {name}@{specifier}')
        return max(candidates, key=version_key)


def validate_tags(tags):
    """Отклонить повреждённые dist-tags до выбора версии."""
    if not isinstance(tags, dict):
        raise AppError('Неверные dist-tags в registry.')
    for name, version in tags.items():
        if not isinstance(name, str) or not isinstance(version, str):
            raise AppError('Неверное значение dist-tag.')
        version_key(version)
