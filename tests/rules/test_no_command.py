import pytest
from thebleep.rules.no_command import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def get_all_executables(mocker):
    mocker.patch('thebleep.rules.no_command.get_all_executables',
                 return_value=['vim', 'fsck', 'git', 'go', 'python'])


@pytest.fixture(autouse=True)
def history_without_current(mocker):
    return mocker.patch(
        'thebleep.rules.no_command.get_valid_history_without_current',
        return_value=['git commit'])


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, output', [
    ('vom file.py', 'vom: not found'),
    ('fucck', 'fucck: not found'),
    ('puthon', "'puthon' is not recognized as an internal or external command"),
    ('got commit', 'got: command not found'),
    ('gti commit -m "new commit"', 'gti: command not found')])
def test_match(mocker, script, output):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)

    assert match(Command(script, output))


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, output, which', [
    ('qweqwe', 'qweqwe: not found', None),
    ('vom file.py', 'some text', None),
    ('vim file.py', 'vim: not found', 'vim')])
def test_not_match(mocker, script, output, which):
    mocker.patch('thebleep.rules.no_command.which', return_value=which)

    assert not match(Command(script, output))


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, result', [
    ('vom file.py', ['vim file.py']),
    ('fucck', ['fsck']),
    ('got commit', ['git commit', 'go commit']),
    ('gti commit -m "new commit"', ['git commit -m "new commit"'])])
def test_get_new_command(script, result):
    assert get_new_command(Command(script, '')) == result


def test_corrects_a_command_inside_a_pipeline(mocker):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)

    command = Command(
        'cd project && gti status | grpe main', 'gti: command not found')

    assert get_new_command(command)[0] == (
        'cd project && git status | grpe main')


@pytest.mark.parametrize('script, expect', [
    ('cd project&&gti status', 'cd project&&git status'),
    ('gti status|grpe main', 'git status|grpe main'),
    ('cd project&&sudo gti status', 'cd project&&sudo git status'),
    ('FOO=bar cd project&&env BAZ=qux gti status',
     'FOO=bar cd project&&env BAZ=qux git status'),
])
def test_corrects_unspaced_or_wrapped_compound_commands(mocker, script, expect):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)

    command = Command(script, 'gti: command not found')

    assert get_new_command(command)[0] == expect


@pytest.mark.parametrize('script, expect', [
    ('if gti status; then echo ok; fi',
     'if git status; then echo ok; fi'),
    ('if ! gti status; then echo ok; fi',
     'if ! git status; then echo ok; fi'),
    ('while gti status; do echo ok; done',
     'while git status; do echo ok; done'),
    ('(gti status) && echo ok',
     '(git status) && echo ok'),
    ('{ gti status; }', '{ git status; }'),
])
def test_corrects_commands_inside_control_blocks(mocker, script, expect):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)

    command = Command(script, 'bash: line 1: gti: command not found')

    assert get_new_command(command)[0] == expect


@pytest.mark.parametrize('script, expect', [
    ('if ($true) { gti status }',
     'if ($true) { git status }'),
    ('try { gti status } catch { echo failed }',
     'try { git status } catch { echo failed }'),
])
def test_corrects_commands_inside_powershell_blocks(mocker, script, expect):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)
    mocker.patch('thebleep.rules.no_command._is_powershell', return_value=True)

    command = Command(
        script,
        "gti: The term 'gti' is not recognized as a name of a cmdlet, "
        'function, script file, or executable program.')

    assert get_new_command(command)[0] == expect


def test_does_not_replace_an_ambiguous_argument(mocker):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)

    command = Command('echo gti && gti status', 'gti: command not found')

    assert get_new_command(command) == []


@pytest.mark.usefixtures('no_memoize')
def test_quotes_a_path_candidate(mocker):
    mocker.patch('thebleep.rules.no_command.which', return_value=None)
    mocker.patch('thebleep.rules.no_command.get_all_executables',
                 return_value=['gti;'])

    assert get_new_command(Command('gti', 'gti: not found')) == ["'gti;'"]


class TestHistoryMayNotPromoteAWorseAnswer:
    """`ca .gitignore` answered `cd .gitignore`, with `cat .gitignore` second.

    The metric had `cat` first. The history tie-break grouped candidates by edit
    distance alone, `cd` is one edit from `ca` too, and `cd` is in everybody's
    history -- so it was promoted over a better answer for anyone who ran this.

    """

    @pytest.fixture(autouse=True)
    def executables(self, mocker):
        mocker.patch('thebleep.rules.no_command.get_all_executables',
                     return_value=['cat', 'cd', 'cp', 'ls', 'git'])

    @pytest.fixture
    def history(self, mocker):
        def _set(*commands):
            return mocker.patch(
                'thebleep.rules.no_command'
                '.get_valid_history_without_current',
                return_value=list(commands))

        return _set

    @pytest.mark.usefixtures('no_memoize')
    def test_the_dropped_key_wins(self, history):
        history('cd /tmp', 'cd ..', 'git status')
        assert get_new_command(Command('ca setup.py', ''))[0] == 'cat setup.py'

    @pytest.mark.usefixtures('no_memoize')
    def test_even_with_nothing_in_the_history(self, history):
        history()
        assert get_new_command(Command('ca setup.py', ''))[0] == 'cat setup.py'

    @pytest.mark.usefixtures('no_memoize')
    def test_a_used_command_still_wins_a_real_tie(self, history):
        """`cp` and `cd` are both one key from `cs`, and both are neighbours of
        `s`, so history is what should choose."""
        history('cd /tmp')
        ranked = get_new_command(Command('cs /tmp', ''))
        assert ranked[0] == 'cd /tmp'


class TestASuggestionThatCannotRun:
    """`cd` was offered for `ca .gitignore`, where the argument is a file."""

    @pytest.fixture(autouse=True)
    def executables(self, mocker):
        mocker.patch('thebleep.rules.no_command.get_all_executables',
                     return_value=['cat', 'cd'])

    @pytest.mark.usefixtures('no_memoize')
    def test_cd_goes_last_when_the_argument_is_a_file(self, mocker, tmpdir):
        mocker.patch('thebleep.rules.no_command'
                     '.get_valid_history_without_current',
                     return_value=['cd /tmp'])
        a_file = tmpdir.join('.gitignore')
        a_file.write('*.pyc')
        ranked = get_new_command(Command(u'ca {}'.format(a_file), ''))
        assert ranked[0].startswith('cat ')
        assert not ranked[0].startswith('cd ')

    @pytest.mark.usefixtures('no_memoize')
    def test_a_directory_argument_is_left_alone(self, mocker, tmpdir):
        """The demotion is about what cannot work, not about disliking `cd`."""
        mocker.patch('thebleep.rules.no_command'
                     '.get_valid_history_without_current',
                     return_value=['cd /tmp'])
        assert any(script.startswith('cd ') for script
                   in get_new_command(Command(u'ca {}'.format(tmpdir), '')))

    @pytest.mark.usefixtures('no_memoize')
    def test_a_path_that_does_not_exist_is_not_evidence(self, mocker):
        """It may be a typo of its own, or relative to somewhere else."""
        mocker.patch('thebleep.rules.no_command'
                     '.get_valid_history_without_current',
                     return_value=['cd /tmp'])
        assert any(script.startswith('cd ') for script in
                   get_new_command(Command('ca no/such/path', '')))


class TestSilenceWhenNothingIsAPlausibleSlip:
    """`cargo buld` answered `xargs buld`.

    On a machine without `cargo` -- a container, a CI image -- `cargo` is two
    substitutions from `xargs`, and no finger explains them: `a` to `r` and
    `o` to `s` sit rows apart. Similar is not mistyped; the honest answer is
    nothing, the same trade `max_distance` already makes for `ndeo`.
    """

    @pytest.mark.usefixtures('no_memoize')
    def test_similar_is_not_offered_when_it_is_not_a_slip(self, mocker):
        mocker.patch('thebleep.rules.no_command.get_all_executables',
                     return_value=['xargs'])
        mocker.patch('thebleep.rules.no_command.which', return_value=None)
        command = Command('cargo buld', 'bash: cargo: command not found')
        assert match(command)
        assert get_new_command(command) == []
