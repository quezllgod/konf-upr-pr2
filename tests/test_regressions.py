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
