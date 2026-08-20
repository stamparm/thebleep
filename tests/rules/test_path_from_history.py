import pytest
from thebleep.rules.path_from_history import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def history(mocker):
    return mocker.patch(
        'thebleep.rules.path_from_history.get_valid_history_without_current',
        return_value=['cd /opt/java', 'ls ~/work/project/'])


@pytest.fixture(autouse=True)
def path_exists(mocker):
    exists_mock = mocker.patch(
        'thebleep.rules.path_from_history.expanduser').return_value.exists
    exists_mock.return_value = True
    return exists_mock


@pytest.mark.parametrize('script, output', [
    ('ls project', 'no such file or directory: project'),
    ('cd project', "can't cd to project"),
])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('myapp cats', 'no such file or directory: project'),
    ('cd project', ""),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, output, result', [
    ('ls project', 'no such file or directory: project', 'ls ~/work/project'),
    ('cd java', "can't cd to java", 'cd /opt/java'),
])
def test_get_new_command(script, output, result):
    new_command = get_new_command(Command(script, output))
    assert new_command[0] == result


@pytest.mark.parametrize('remembered, typed, expected', [
    ("'/home/me/My Documents'", 'Documents', "ls '/home/me/My Documents'"),
    ("'/tmp/a b;rm -rf x'", 'x', "ls '/tmp/a b;rm -rf x'"),
    ("'/tmp/$(id) y'", 'y', "ls '/tmp/$(id) y'"),
    # The one character whose meaning the shell is meant to change stays
    # outside the quotes: `'~/work'` is a literal directory called `~`.
    ("~/'My Work'", 'Work', "ls ~/'My Work'"),
    ('~/work', 'work', 'ls ~/work'),
])
def test_a_path_from_history_is_quoted(history, remembered, typed, expected):
    """History holds whatever the filesystem allows -- a space, a `;`, a `$` --
    and this goes back to the shell to be evaluated."""
    history.return_value = ['ls {}'.format(remembered)]
    command = Command('ls {}'.format(typed),
                      "ls: cannot access '{}': No such file or directory"
                      .format(typed))
    assert get_new_command(command)[0] == expected
