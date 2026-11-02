import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AppError
from .versions import version_key

LAST_STAGE = 3
MIN_DEPTH = 0
MIN_PORT = 1
NAME = r'(?:@[a-z0-9._-]+/)?[a-z0-9][a-z0-9._-]*'


@dataclass(frozen=True)
class Config:
    package: str
    version: str
    repository: str
    test: bool
    output: str
    max_depth: int
    stage: int
    target: str | None

    def describe(self):
        """Представить настройки в формате ключ=значение."""
        values = vars(self).items()
        lines = []
        for key, value in values:
            text = str(value).lower() if isinstance(value, bool) else value
            lines.append(f'{key}={text}')
        return '\n'.join(lines)


def validate(config):
    """Проверить структуру входных данных."""
    pattern = r'[A-Z]+' if config.test else NAME
    if not re.fullmatch(pattern, config.package):
        raise AppError('Неверное имя пакета.')
    version_key(config.version)
    if config.max_depth < MIN_DEPTH:
        raise AppError('Глубина должна быть неотрицательной.')
    validate_output(config.output)
    if config.target and not re.fullmatch(pattern, config.target):
        raise AppError('Неверное имя для обратных зависимостей.')
    if config.test:
        validate_test_path(config.repository)
    else:
        validate_url(config.repository)


def validate_test_path(value):
    """Проверить чтение тестового файла до запуска этапа."""
    try:
        Path(value).read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
        raise AppError(f'Не прочитан тестовый файл: {error}')


def validate_output(value):
    """Проверить расширение PNG и существование каталога."""
    path = Path(value)
    if path.suffix.lower() != '.png' or path.is_dir():
        raise AppError('Имя изображения должно оканчиваться на .png.')
    if not path.parent.is_dir():
        raise AppError('Каталог изображения не существует.')


def url_has_credentials(url):
    """Не разрешать логин, пароль и URL-параметры."""
    return any((url.username, url.password, url.query, url.fragment))


def validate_url(value):
    """Проверить схему, адрес, пробелы, авторизацию и номер порта."""
    try:
        url = urlsplit(value)
        if url.scheme not in {'http', 'https'} or not url.hostname:
            raise ValueError('Неверная схема или адрес.')
        if any(c.isspace() for c in value) or url_has_credentials(url):
            raise ValueError('Пробелы или авторизация в URL.')
        port = url.port
        if port is not None and port < MIN_PORT:
            raise ValueError('Порт должен быть положительным.')
    except ValueError as error:
        message = 'Нужен корректный URL http(s) без логина и #.'
        raise AppError(message) from error


def parse_config(arguments=None):
    """Прочитать и проверить параметры командной строки."""
    parser = argparse.ArgumentParser(
        description='Зависимости npm, ПР №2, вариант 14.')
    parser.add_argument('--package', required=True, help='Имя пакета')
    parser.add_argument('--version', required=True, help='Точная версия')
    parser.add_argument('--repository', default='https://registry.npmjs.org',
                        help='URL registry или тестовый JSON')
    parser.add_argument('--test', action='store_true', help='Локальный граф')
    parser.add_argument('--output', default='graph.png', help='PNG-файл')
    parser.add_argument('--max-depth', type=int, default=10,
                        help='Глубина: корень 0, прямые зависимости 1')
    parser.add_argument('--stage', type=int, default=LAST_STAGE,
                        choices=range(1, LAST_STAGE + 1))
    parser.add_argument('--target', help='Цель обратного поиска, этап 4')
    config = Config(**vars(parser.parse_args(arguments)))
    try:
        validate(config)
    except (AppError, ValueError) as error:
        parser.error(str(error))
    return config
