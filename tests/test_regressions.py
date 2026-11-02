import io
import unittest
from contextlib import redirect_stderr

from src.config import parse_config
from src.errors import AppError
from src.versions import matches, version_key


class RegressionTests(unittest.TestCase):
    def test_invalid_semver(self):
        invalid = ['1.2.3+..', '1.2.3+a..b', '1.2.3-01', '1.2.3-',
                   '01.2.3', '1.02.3', '1.2.03', '١.2.3']
        for version in invalid:
            with self.subTest(version=version), self.assertRaises(AppError):
                version_key(version)

    def test_invalid_ranges(self):
        invalid = ['01', '1.02', '1.2.03', '1.2.3+..',
                   '1.2.3 || git+https://example.org/repo']
        for specifier in invalid:
            with (self.subTest(specifier=specifier),
                  self.assertRaises(AppError)):
                matches('1.2.3', specifier)

    def test_prerelease_hyphen(self):
        specifier = '1.2.3-beta.1 - 1.2.3'
        for version in ['1.2.3-beta.1', '1.2.3-beta.2', '1.2.3']:
            self.assertTrue(matches(version, specifier))
        self.assertFalse(matches('1.2.3-alpha', specifier))
        self.assertFalse(matches('1.2.4', specifier))
        self.assertFalse(matches('1.3.0-beta', '^1.2.3-beta'))

    def test_bad_urls(self):
        urls = ['https://host:0', 'https://host:65536',
                'https://[broken', 'https://host?q=a', 'https://host#x']
        for url in urls:
            with (self.subTest(url=url), redirect_stderr(io.StringIO()),
                  self.assertRaises(SystemExit)):
                parse_config(['--package', 'is-odd', '--version', '3.0.1',
                              '--repository', url])


class RegistryRegressionTests(unittest.TestCase):
    def project(self, data):
        import json
        from unittest.mock import patch

        from src.repository import NpmRepository

        response = io.BytesIO(json.dumps(data).encode())
        repo = NpmRepository('https://example.org')
        with patch('src.repository.urlopen', return_value=response):
            return repo.project('a')

    def test_malformed_metadata(self):
        invalid = [[], {}, {'versions': []},
                   {'versions': {}, 'dist-tags': []},
                   {'versions': {}, 'dist-tags': {'latest': None}},
                   {'versions': {}, 'dist-tags': {'latest': 'broken'}}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(AppError):
                self.project(data)

    def test_bad_dependencies(self):
        from src.repository import NpmRepository

        repo = NpmRepository('https://example.org')
        for dependencies in [[], {'b': None}, {'bad"name': '1.0.0'}]:
            repo.cache['a'] = {'versions': {
                '1.0.0': {'dependencies': dependencies}}}
            with (self.subTest(dependencies=dependencies),
                  self.assertRaises(AppError)):
                repo.dependencies('a', '1.0.0')

    def test_missing_tag_version(self):
        from src.repository import NpmRepository

        repo = NpmRepository('https://example.org')
        repo.cache['a'] = {'versions': {}, 'dist-tags': {'latest': '1.0.0'}}
        with self.assertRaises(AppError):
            repo.resolve('a', 'latest')
