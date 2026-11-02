import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from src.cli import main
from src.config import parse_config
from src.errors import AppError
from src.graph import build_graph
from src.repository import NpmRepository
from src.reverse import reverse_dependencies
from src.test_repository import TestRepository
from src.versions import matches, version_key

LAST_CHAIN_NODE = 899
DIRECT_STAGE = 2
GRAPH_STAGE = 3
REVERSE_STAGE = 4
RENDER_STAGE = 5

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_values(self):
        config = parse_config(['--package', 'is-odd', '--version', '3.0.1',
                               '--max-depth', '0', '--stage', '1'])
        self.assertEqual(config.max_depth, 0)
        self.assertIn('output=graph.png', config.describe())

    def test_errors(self):
        cases = [('--package', '../x'), ('--version', '1.0'),
                 ('--max-depth', '-1'), ('--max-depth', 'abc'),
                 ('--repository', 'ftp://host'), ('--stage', '6'),
                 ('--repository', 'https://host:bad'),
                 ('--repository', 'https://user:pass@host'),
                 ('--output', 'out.svg'), ('--target', '../bad'),
                 ('--test', '--repository', '/missing/file')]
        for args in cases:
            with (self.subTest(args=args), redirect_stderr(io.StringIO()),
                  self.assertRaises(SystemExit)):
                parse_config(['--package', 'is-odd', '--version',
                              '3.0.1', *args])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_config([])


class VersionTests(unittest.TestCase):
    def test_ranges(self):
        cases = [('1.2.3', '^1.0.0', True), ('2.0.0', '^1.0.0', False),
                 ('0.3.0', '^0.2.1', False), ('0.0.4', '^0.0.3', False),
                 ('1.3.0', '~1.2.0', False), ('1.2.9', '~1.2', True),
                 ('1.9.0', '^1', True), ('0.0.9', '^0.0', True),
                 ('1.2.3', '1.x', True), ('2.0.0', '1', False),
                 ('2.1.0', '1 || >=2 <3', True),
                 ('1.4.0', '1.2 - 1.4', True),
                 ('1.4.1', '1.2.0 - 1.4.0', False),
                 ('1.2.3-beta.1', '*', False),
                 ('1.2.3-beta.2', '^1.2.3-beta.1', True)]
        for version, spec, expected in cases:
            with self.subTest(version=version, spec=spec):
                self.assertEqual(matches(version, spec), expected)

    def test_order(self):
        self.assertLess(version_key('1.0.0-beta.2'),
                        version_key('1.0.0-beta.11'))
        self.assertLess(version_key('1.0.0-rc.1'), version_key('1.0.0'))
        with self.assertRaises(AppError):
            matches('1.0.0', 'git+https://example.org/repo')


class RepositoryTests(unittest.TestCase):
    def test_metadata_and_versions(self):
        repo = NpmRepository('https://example.org')
        repo.cache['a'] = {'versions': {
            '1.0.0': {'dependencies': {'b': '^2.0.0'}},
            '1.2.0': {}}, 'dist-tags': {'latest': '1.2.0'}}
        self.assertEqual(repo.resolve('a', '^1'), '1.2.0')
        self.assertEqual(repo.resolve('a', 'latest'), '1.2.0')
        self.assertEqual(repo.dependencies('a', '1.0.0'),
                         [('b', '^2.0.0')])
        with self.assertRaises(AppError):
            repo.dependencies('a', '9.0.0')

    def test_bad_json_and_network(self):
        repo = NpmRepository('https://example.org')
        with (patch('src.repository.urlopen', side_effect=OSError('x')),
              self.assertRaises(AppError)):
            repo.project('a')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            for raw in ['[]', '{}', '{"A": ["B"]}', '{"a": []}']:
                path.write_text(raw)
                with self.assertRaises(AppError):
                    TestRepository(path, '1.0.0')


class GraphTests(unittest.TestCase):
    def graph(self, name, depth=10):
        repo = TestRepository(ROOT / f'examples/{name}.json', '1.0.0')
        return build_graph(repo, 'A', '1.0.0', depth)

    def test_dfs_and_cycle(self):
        graph = self.graph('diamond')
        self.assertEqual([n[0] for n in graph.order], ['A', 'B', 'D', 'C'])
        graph = self.graph('cycle')
        self.assertEqual(graph.edges[('C', '1.0.0')], [('A', '1.0.0')])

    def test_depth_and_shorter_path(self):
        self.assertEqual(len(self.graph('diamond', 0).order), 1)
        self.assertEqual(len(self.graph('diamond', 1).order), 3)
        graph = self.graph('shortcut', 2)
        self.assertIn(('E', '1.0.0'), graph.edges)
        self.assertEqual(graph.depths[('D', '1.0.0')], 1)

    def test_self_cycle(self):
        repo = Mock()
        repo.dependencies.return_value = [('A', '1.0.0')]
        repo.resolve.return_value = '1.0.0'
        graph = build_graph(repo, 'A', '1.0.0')
        self.assertEqual(graph.order, [('A', '1.0.0')])
        self.assertEqual(graph.edges[('A', '1.0.0')], [('A', '1.0.0')])

    def test_no_fetch_at_boundary(self):
        repo = Mock()
        graph = build_graph(repo, 'A', '1.0.0', 0)
        repo.dependencies.assert_not_called()
        self.assertEqual(graph.order, [('A', '1.0.0')])

    def test_multiple_versions(self):
        repo = NpmRepository('https://example.org')
        repo.cache = {
            'a': {'versions': {'1.0.0': {'dependencies': {
                'b': '1', 'c': '1'}}}},
            'b': {'versions': {'1.0.0': {}, '2.0.0': {}}},
            'c': {'versions': {'1.0.0': {'dependencies': {'b': '2'}}}}}
        graph = build_graph(repo, 'a', '1.0.0')
        self.assertIn(('b', '1.0.0'), graph.edges)
        self.assertIn(('b', '2.0.0'), graph.edges)

    def test_deep_without_recursion(self):
        class Chain:
            def dependencies(self, name, version):
                n = int(name)
                return [(str(n + 1), version)] if n < LAST_CHAIN_NODE else []

            def resolve(self, name, spec):
                return spec
        self.assertEqual(len(build_graph(Chain(), '0', '1.0.0',
                                         999).order), 900)


class ReverseTests(unittest.TestCase):
    def test_full_test_scope_and_cycle(self):
        output = io.StringIO()
        args = ['--test', '--package', 'D', '--version', '1.0.0',
                '--repository', str(ROOT / 'examples/reverse.json'),
                '--stage', '4']
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        for node in ['A', 'B', 'C']:
            self.assertIn(node + '@1.0.0', output.getvalue())
        self.assertNotIn('Z@', output.getvalue())
        repo = TestRepository(ROOT / 'examples/cycle.json', '1.0.0')
        graph = build_graph(repo, 'A', '1.0.0')
        nodes = reverse_dependencies(graph, 'A')
        self.assertEqual({n[0] for n in nodes}, {'B', 'C'})
        self.assertEqual(len(reverse_dependencies(graph, 'A', 1)), 1)
