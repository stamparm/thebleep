# -*- coding: utf-8 -*-

"""PEP 668, which is what every current distribution now does.

Recorded from Debian trixie with `python3-pip` installed, running
`pip install requests`.

"""

import pytest
from thebleep.rules.pip_externally_managed import match, get_new_command
from thebleep.types import Command

OUTPUT = u'''error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.

    If you wish to install a non-Debian-packaged Python package,
    create a virtual environment using python3 -m venv path/to/venv.
    Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
    sure you have python3-full installed.

    If you wish to install a non-Debian packaged Python application,
    it may be easiest to use pipx install xyz, which will manage a
    virtual environment for you. Make sure you have pipx installed.

    See /usr/share/doc/python3.13/README.venv for more information.

note: If you believe this is a mistake, please contact your Python installation \
or OS distribution provider. You can override this, at the risk of breaking \
your Python installation or OS, by passing --break-system-packages.
hint: See PEP 668 for the detailed specification.
'''


@pytest.fixture
def no_pipx(mocker):
    return mocker.patch('thebleep.rules.pip_externally_managed.which',
                        return_value=None)


@pytest.fixture
def with_pipx(mocker):
    return mocker.patch('thebleep.rules.pip_externally_managed.which',
                        return_value='/usr/bin/pipx')


@pytest.mark.parametrize('script', [
    'pip install requests',
    'pip3 install requests',
    'pip3.12 install requests',
    'python -m pip install requests',
    'python3 -m pip install requests',
    'python3.13 -m pip install -r requirements.txt',
])
def test_match(script):
    assert match(Command(script, OUTPUT))


@pytest.mark.parametrize('script, output', [
    # Something else went wrong.
    ('pip install requests', 'ERROR: Could not find a version that satisfies'),
    # The same message, but nothing is being installed.
    ('pip download requests', OUTPUT),
    ('pip list', OUTPUT),
    # Not pip at all.
    ('apt install python3-requests', OUTPUT),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


class TestWhatItSuggests(object):
    def test_a_virtual_environment_is_always_offered(self, no_pipx):
        assert get_new_command(Command('pip install requests', OUTPUT)) == [
            'python3 -m venv .venv && .venv/bin/pip install requests']

    def test_pipx_first_for_one_application(self, with_pipx):
        assert get_new_command(Command('pip install black', OUTPUT)) == [
            'pipx install black',
            'python3 -m venv .venv && .venv/bin/pip install black']

    def test_no_pipx_when_it_is_not_installed(self, no_pipx):
        assert 'pipx' not in ' '.join(
            get_new_command(Command('pip install black', OUTPUT)))

    @pytest.mark.parametrize('script', [
        'pip install -r requirements.txt',
        'pip install -e .',
        'pip install requests flask',
        'pip install --target /tmp/here requests',
    ])
    def test_no_pipx_for_anything_but_one_application(self, with_pipx, script):
        """pipx installs one application; none of these is that."""
        assert 'pipx' not in ' '.join(get_new_command(Command(script, OUTPUT)))

    def test_the_options_are_carried_over(self, no_pipx):
        assert get_new_command(
            Command('pip install --no-deps requests==2.31.0', OUTPUT)) == [
            'python3 -m venv .venv && .venv/bin/pip install --no-deps'
            ' requests==2.31.0']


class TestWhatItRefusesToSuggest(object):
    """The one-word fix in the message is the one thing not to offer."""

    @pytest.mark.parametrize('script', [
        'pip install requests',
        'pip install -r requirements.txt',
        'python3 -m pip install black',
    ])
    def test_never_break_system_packages(self, with_pipx, script):
        suggested = ' '.join(get_new_command(Command(script, OUTPUT)))
        assert '--break-system-packages' not in suggested

    def test_never_sudo(self, with_pipx):
        suggested = ' '.join(
            get_new_command(Command('pip install requests', OUTPUT)))
        assert 'sudo' not in suggested

    def test_never_user(self, no_pipx):
        """PEP 668 marks the user site too, so `--user` fails the same way."""
        suggested = ' '.join(
            get_new_command(Command('pip install requests', OUTPUT)))
        assert '--user' not in suggested
