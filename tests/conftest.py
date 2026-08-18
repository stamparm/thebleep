import os
import pytest
from thebleep import shells
from thebleep import conf, const
from thebleep.system import Path

shells.shell = shells.Generic()


def pytest_configure(config):
    config.addinivalue_line("markers", "functional: mark test as functional")
    # Suites that take tens of seconds and are about logic rather than about
    # this machine: the rule pack's equivalence corpus, the large-output sweep,
    # the structural rule checks. Worth running on every commit, not worth
    # running once per operating system per Python version -- CI runs them on
    # one job with `-m 'not slow'` everywhere else.
    config.addinivalue_line(
        "markers", "slow: platform-independent and slow; run once in CI")


def pytest_addoption(parser):
    """Adds `--enable-functional` argument."""
    group = parser.getgroup("thebleep")
    group.addoption('--enable-functional', action="store_true", default=False,
                    help="Enable functional tests")


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
