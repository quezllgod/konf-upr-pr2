from .config import parse_config


def main(arguments=None):
    """Проверить параметры и выполнить выбранный этап."""
    print(parse_config(arguments).describe())
    return 0
