# -*- encoding: utf-8 -*-

"""pip's own guess, and when not to lead with it.

Fixtures are real pip 25.0.1 output. The interesting case is `pip nistall`,
which pip answers with `uninstall` -- so the only suggestion offered was one
that removes the package the user was trying to install, and pressing enter did
it. `difflib` does not save you there either: it scores `nistall` closer to
`uninstall` (0.875) than to `install` (0.857).

"""

import pytest
from thebleep.rules import pip_unknown_command
from thebleep.rules.pip_unknown_command import match, get_new_command
from thebleep.types import Command

UNKNOWN = 'ERROR: unknown command "{}" - maybe you meant "{}"\n'
NO_GUESS = 'ERROR: unknown command "i"\n'

# What `pip --help` is built from and what pip dispatches on, so the whole list.
PIP_COMMANDS = ['install', 'download', 'uninstall', 'freeze', 'inspect',
                'list', 'show', 'check', 'config', 'search', 'cache',
                'index', 'wheel', 'hash', 'completion', 'debug', 'help']


@pytest.fixture(autouse=True)
def pip(mocker):
    """A pip whose command list is the real one, without running pip."""
    mocker.patch.object(pip_unknown_command, '_interpreter',
                        return_value='python3')
    return mocker.patch.object(pip_unknown_command, '_pip_commands',
                               return_value=PIP_COMMANDS)


class TestMatching(object):
    def test_a_guess_is_needed(self):
        assert match(Command('pip instatl', UNKNOWN.format('instatl',
                                                           'install')))

    def test_without_a_guess_there_is_nothing_to_go_on(self):
        assert not match(Command('pip i', NO_GUESS))


class TestOrdering(object):
    @pytest.mark.parametrize('typo, guess', [
        ('instatl', 'install'),
        ('isntall', 'install'),
        ('instal', 'install'),
        # pip's own guess is the destructive one, and it is wrong.
        ('nistall', 'uninstall'),
    ])
    def test_install_leads_for_an_install_typo(self, typo, guess):
        command = Command('pip {} requests'.format(typo),
                          UNKNOWN.format(typo, guess))
        assert get_new_command(command)[0] == 'pip install requests'

    @pytest.mark.parametrize('typo', ['unistall', 'uninstal', 'uninstll'])
    def test_uninstall_still_leads_for_an_uninstall_typo(self, typo):
        """The margin is what decides, so a real `uninstall` typo is not
        second-guessed: those are decided by 0.14, and `nistall` by 0.018."""
        command = Command('pip {} requests'.format(typo),
                          UNKNOWN.format(typo, 'uninstall'))
        assert get_new_command(command)[0] == 'pip uninstall requests'

    def test_the_alternative_is_still_offered(self):
        """Demoted, not dropped -- arrowing down has to reach it."""
        command = Command('pip nistall requests',
                          UNKNOWN.format('nistall', 'uninstall'))
        assert 'pip uninstall requests' in get_new_command(command)

    def test_an_unrelated_typo_is_left_to_pip(self):
        command = Command('pip freze', UNKNOWN.format('freze', 'freeze'))
        assert get_new_command(command)[0] == 'pip freeze'


class TestWithoutPipsList(object):
    def test_pips_own_guess_is_enough_on_its_own(self, pip):
        """A pip that cannot be asked -- no shebang, not on PATH, an error --
        leaves the guess, which is what this rule always had."""
        pip.return_value = []
        command = Command('pip instatl requests',
                          UNKNOWN.format('instatl', 'install'))
        assert get_new_command(command) == ['pip install requests']

    def test_a_name_needing_quotes_is_quoted(self, pip):
        """The name is read out of output and the result goes to a shell."""
        pip.return_value = []
        command = Command('pip x requests', UNKNOWN.format('x', 'a;id'))
        assert get_new_command(command) == ["pip 'a;id' requests"]

    def test_environment_assignment_keeps_pips_interpreter(self, mocker):
        interpreter = mocker.patch.object(
            pip_unknown_command, '_interpreter', return_value='python3')
        command = Command(
            'PIP_DISABLE_PIP_VERSION_CHECK=1 pip instatl requests',
            UNKNOWN.format('instatl', 'install'))

        assert get_new_command(command)[0] == \
            'PIP_DISABLE_PIP_VERSION_CHECK=1 pip install requests'
        interpreter.assert_called_once_with(command)
