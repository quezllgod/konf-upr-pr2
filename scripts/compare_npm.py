"""npm используется только как независимый эталон сравнения."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [('is-odd', '3.0.1'), ('is-even', '1.0.0'),
            ('ansi-styles', '4.3.0')]


def npm_graph(tree, name, version):
    nodes, edges = set(), set()
    stack = [((name, version), tree)]
    while stack:
        parent, data = stack.pop()
        nodes.add(parent)
        for child, info in data.get('dependencies', {}).items():
            node = (child, info['version'])
            edges.add((parent, node))
            stack.append((node, info))
    return nodes, edges


def npm_reference(name, version, directory):
    options = ['--cache', str(Path(directory) / 'cache'),
               '--registry', 'https://registry.npmjs.org']
    manifest = {'name': 'pr2-comparison', 'version': '1.0.0',
                'private': True, 'dependencies': {name: version}}
    Path(directory, 'package.json').write_text(json.dumps(manifest))
    subprocess.run(['npm', 'install', '--ignore-scripts', '--no-audit',
                    '--no-fund', '--omit=dev', *options], cwd=directory,
                   check=True, capture_output=True, text=True, timeout=120)
    raw = subprocess.check_output(['npm', 'ls', '--all', '--json',
                                   *options], cwd=directory, text=True)
    text = subprocess.check_output(['npm', 'ls', '--all', *options],
                                   cwd=directory, text=True)
    return json.loads(raw)['dependencies'][name], text


def compare(name, version):
    from src.graph import build_graph, label
    from src.render import save_graph
    from src.repository import NpmRepository

    graph = build_graph(NpmRepository('https://registry.npmjs.org'),
                        name, version, 10)
    with tempfile.TemporaryDirectory(prefix='pr2-npm-') as directory:
        tree, text = npm_reference(name, version, directory)
    nodes, edges = npm_graph(tree, name, version)
    actual = {(p, c) for p, children in graph.edges.items() for c in children}
    same = nodes == set(graph.order) and edges == actual
    save_graph(graph, ROOT / 'examples' / f'{name}.png')
    (ROOT / 'examples' / f'{name}-npm.txt').write_text(text)
    report = [f'# {name}@{version}', '',
              f'Узлы: {len(graph.order)}. Рёбра: {len(actual)}.',
              f'Совпадение с npm ls --all: {same}.', '',
              '## DFS', '', ' → '.join(map(label, graph.order)), '',
              '## Рёбра', '']
    report += [f'- {label(p)} → {label(c)}' for p, c in sorted(actual)]
    (ROOT / 'examples' / f'{name}-comparison.md').write_text(
        '\n'.join(report) + '\n')
    print(name, 'MATCH' if same else 'DIFFERENCE', flush=True)
    if not same:
        raise RuntimeError('Расхождение с npm: см. отчёт.')


if __name__ == '__main__':
    for name, version in PACKAGES:
        compare(name, version)
