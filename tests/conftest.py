import os
import sys
import pytest
from thebleep import shells
from thebleep import conf, const
from thebleep.system import Path

# So that `windows_rules` is importable from here and from a test module,
# whichever import mode pytest is running in.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

shells.shell = shells.Generic()


def pytest_configure(config):
    config.addinivalue_line("markers", "functional: mark test as functional")
    # The three suites that take tens of seconds: the rule pack's equivalence
    # corpus, the large-output sweep and the structural rule checks. CI runs
    # them everywhere -- the pack marshals code objects and the structural
    # checks walk the syntax tree, both of which differ between interpreters.
    # The marker is for a quick local loop: `pytest -m "not slow"`.
    config.addinivalue_line(
        "markers", "slow: tens of seconds; skip for a quick local run")

    if config.getoption('windows_rules'):
        import windows_rules

        print('\nwindows rules: {}'.format(windows_rules.install()))


def pytest_addoption(parser):
    """Adds `--enable-functional` argument."""
    group = parser.getgroup("thebleep")
    group.addoption('--enable-functional', action="store_true", default=False,
                    help="Enable functional tests")
    group.addoption('--windows-rules', action="store_true", default=False,
                    help="Answer the questions Windows answers differently, "
                         "on any platform (see tests/windows_rules.py)")


@pytest.fixture
def no_memoize(monkeypatch):
    monkeypatch.setattr('thebleep.utils.memoize.disabled', True)


@pytest.fixture(autouse=True)
def settings(request):
    def _reset_settings():
        conf.settings.clear()
        conf.settings.update(const.DEFAULT_SETTINGS)

    request.addfinalizer(_reset_settings)
    conf.settings.user_dir = Path('~/.thebleep')
    return conf.settings


@pytest.fixture
def no_colors(settings):
    settings.no_colors = True


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr('thebleep.utils.cache.disabled', True)


@pytest.fixture(autouse=True)
def functional(request):
    if request.node.get_closest_marker('functional') \
            and not request.config.getoption('enable_functional'):
        pytest.skip('functional tests are disabled')


@pytest.fixture
def source_root():
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def set_shell(monkeypatch):
    def _set(cls):
        shell = cls()
        monkeypatch.setattr('thebleep.shells.shell', shell)
        return shell

    return _set


@pytest.fixture(autouse=True)
def os_environ(monkeypatch):
    env = {'PATH': os.environ['PATH']}
    monkeypatch.setattr('os.environ', env)
    return env
