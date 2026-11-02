import sys
from pathlib import Path

from src.cli import main

ROOT = Path(__file__).resolve().parent
ARGUMENTS = ['--test', '--package', 'A', '--version', '1.0.0',
             '--repository', str(ROOT / 'examples/diamond.json')]

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:] or ARGUMENTS))
