import sys

from .config import parse_config
from .errors import AppError
from .graph import build_graph, describe_graph
from .repository import NpmRepository
from .test_repository import TestRepository

CONFIG_STAGE, DIRECT_STAGE, GRAPH_STAGE, REVERSE_STAGE = 1, 2, 3, 4


def main(arguments=None):
    """Проверить параметры и выполнить выбранный этап."""
    config = parse_config(arguments)
    if config.stage == CONFIG_STAGE:
        print(config.describe())
        return 0
    try:
        return run(config)
    except (AppError, OSError) as error:
        print(f'Ошибка: {error}', file=sys.stderr)
        return 1


def run(config):
    """Выполнить операцию над репозиторием и вывести результат."""
    repository = (TestRepository(config.repository, config.version)
                  if config.test else NpmRepository(config.repository))
    if config.stage == DIRECT_STAGE:
        print(f'Прямые зависимости {config.package}@{config.version}:')
        dependencies = repository.dependencies(config.package, config.version)
        for name, specifier in dependencies:
            print(f'{name}: {specifier}')
        if not dependencies:
            print('(нет зависимостей)')
        return 0
    graph = build_graph(repository, config.package,
                        config.version, config.max_depth)
    print(describe_graph(graph))
    return 0
