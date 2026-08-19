import pytest
from thebleep.types import Command
from thebleep.rules.chmod_x import match, get_new_command


@pytest.fixture
def file_exists(mocker):
    return mocker.patch('os.path.exists', return_value=True)


@pytest.fixture
def file_access(mocker):
    return mocker.patch('os.access', return_value=False)


@pytest.mark.usefixtures('file_exists', 'file_access')
@pytest.mark.parametrize('script, output', [
    ('./gradlew build', 'gradlew: Permission denied'),
    ('./install.sh --help', 'install.sh: permission denied')])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output, exists, callable', [
    ('./gradlew build', 'gradlew: Permission denied', True, True),
    ('./gradlew build', 'gradlew: Permission denied', False, False),
    ('./gradlew build', 'gradlew: error', True, False),
    ('gradlew build', 'gradlew: Permission denied', True, False)])
def test_not_match(file_exists, file_access, script, output, exists, callable):
    file_exists.return_value = exists
    file_access.return_value = callable
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, result', [
    ('./gradlew build', 'chmod +x gradlew && ./gradlew build'),
    ('./install.sh --help', 'chmod +x install.sh && ./install.sh --help')])
def test_get_new_command(script, result):
    assert get_new_command(Command(script, '')) == result


def test_a_name_the_shell_would_read_is_quoted(set_shell, mocker):
    """`$(id)` is a legal file name, and this line goes back to the shell."""
    from thebleep.shells import Bash

    set_shell(Bash)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.access', return_value=False)
    assert get_new_command(Command('./a$(id)', 'permission denied')) == \
        "chmod +x 'a$(id)' && ./a$(id)"


class TestPathsThatAreNotRelative(object):
    """`./x` was the only form that used to be corrected.

    Every one of these is the same mistake with the same fix, and three of the
    four said "permission denied" and got nothing.

    Refs: nvbn/thefuck#1470

    """

    @pytest.fixture(autouse=True)
    def unrunnable(self, mocker):
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('os.access', return_value=False)

    @pytest.mark.parametrize('script', [
        './deploy.sh',
        'scripts/deploy.sh',
        '~/scripts/deploy.sh',
        '/home/alice/scripts/deploy.sh',
        '../deploy.sh',
    ])
    def test_match(self, script):
        assert match(Command(script, 'bash: {}: Permission denied'.format(
            script)))

    def test_a_bare_name_is_a_path_lookup_and_not_this(self):
        """`chmod +x deploy.sh` would be about a file in this directory, and
        the one that could not run is somewhere on PATH."""
        assert not match(Command('deploy.sh', 'permission denied'))

    @pytest.mark.parametrize('script, fixed', [
        ('scripts/deploy.sh',
         'chmod +x scripts/deploy.sh && scripts/deploy.sh'),
        ('/home/alice/scripts/deploy.sh',
         'chmod +x /home/alice/scripts/deploy.sh'
         ' && /home/alice/scripts/deploy.sh'),
        ('../deploy.sh', 'chmod +x ../deploy.sh && ../deploy.sh'),
    ])
    def test_get_new_command(self, script, fixed):
        assert get_new_command(Command(script, '')) == fixed

    def test_a_tilde_stays_a_tilde(self):
        """Quoting it is what would stop the shell expanding it."""
        assert get_new_command(Command('~/scripts/deploy.sh', '')) == \
            'chmod +x ~/scripts/deploy.sh && ~/scripts/deploy.sh'

    def test_a_tilde_path_with_a_space_in_it(self):
        """The tilde stays outside the quotes so that the shell expands it."""
        assert get_new_command(Command("'~/my scripts/deploy.sh'", '')) == \
            "chmod +x ~/'my scripts/deploy.sh' && '~/my scripts/deploy.sh'"
