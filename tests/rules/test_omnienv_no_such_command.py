import pytest

from thebleep.rules.omnienv_no_such_command import get_new_command, match
from thebleep.types import Command


@pytest.fixture
def output(pyenv_cmd):
    return "pyenv: no such command `{}'".format(pyenv_cmd)


@pytest.fixture(autouse=True)
def commands(mocker):
    listed = (
        b'--version\nactivate\ncommands\ncompletions\ndeactivate\nexec_\n'
        b'global\nhelp\nhooks\ninit\ninstall\nlocal\nprefix_\n'
        b'realpath.dylib\nrehash\nroot\nshell\nshims\nuninstall\nversion_\n'
        b'version-file\nversion-file-read\nversion-file-write\nversion-name_\n'
        b'version-origin\nversions\nvirtualenv\nvirtualenv-delete_\n'
        b'virtualenv-init\nvirtualenv-prefix\nvirtualenvs_\n'
        b'virtualenvwrapper\nvirtualenvwrapper_lazy\nwhence\nwhich_\n'
    ).decode('utf-8').split()
    return mocker.patch(
        'thebleep.rules.omnienv_no_such_command.tool_lines',
        return_value=listed)


@pytest.mark.parametrize('script, pyenv_cmd', [
    ('pyenv globe', 'globe'),
    ('pyenv intall 3.8.0', 'intall'),
    ('pyenv list', 'list'),
])
def test_match(script, pyenv_cmd, output):
    assert match(Command(script, output=output))


def test_match_goenv_output_quote():
    """test goenv's specific output with quotes (')"""
    assert match(Command('goenv list', output="goenv: no such command 'list'"))


@pytest.mark.parametrize('script, output', [
    ('pyenv global', 'system'),
    ('pyenv versions', '  3.7.0\n  3.7.1\n* 3.7.2\n'),
    ('pyenv install --list', '  3.7.0\n  3.7.1\n  3.7.2\n'),
])
def test_not_match(script, output):
    assert not match(Command(script, output=output))


@pytest.mark.parametrize('script, pyenv_cmd, result', [
    ('pyenv globe', 'globe', 'pyenv global'),
    ('pyenv intall 3.8.0', 'intall', 'pyenv install 3.8.0'),
    ('pyenv list', 'list', 'pyenv install --list'),
    ('pyenv remove 3.8.0', 'remove', 'pyenv uninstall 3.8.0'),
])
def test_get_new_command(script, pyenv_cmd, output, result):
    assert result in get_new_command(Command(script, output))


def test_environment_assignment_is_not_used_as_the_app(mocker):
    get_commands = mocker.patch(
        'thebleep.rules.omnienv_no_such_command.get_app_commands',
        return_value=['global'])
    command = Command(
        'PYENV_ROOT=/tmp/pyenv pyenv globe',
        "pyenv: no such command `globe'")

    assert 'PYENV_ROOT=/tmp/pyenv pyenv global' in get_new_command(command)
    get_commands.assert_called_once_with('pyenv')
