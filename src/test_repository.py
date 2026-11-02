import json
import re
from pathlib import Path

from .errors import AppError


class TestRepository:
    def __init__(self, path, version):
        """Инициализировать объект."""
        self.version = version
        try:
            self.data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError) as error:
            raise AppError(f'Ошибка тестового JSON: {error}') from error
        self.validate()

    def validate(self):
        """Проверить структуру входных данных."""
        if not isinstance(self.data, dict) or not self.data:
            raise AppError('Нужен непустой объект графа.')
        for name, children in self.data.items():
            if not re.fullmatch('[A-Z]+', name):
                raise AppError('Тестовые имена должны состоять из A-Z.')
            if not isinstance(children, list) or any(
                    not isinstance(c, str) or c not in self.data
                    for c in children):
                raise AppError(f'Неверные зависимости узла {name}.')

    def dependencies(self, name, version):
        """Вернуть прямые зависимости заданной версии."""
        if name not in self.data:
            raise AppError(f'Узел {name} отсутствует в тестовом графе.')
        return [(child, self.version) for child in self.data[name]]

    def resolve(self, name, specifier):
        """Выбрать версию для указанного ограничения."""
        return self.version
