import pytest
from thebleep.rules.history import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def history_without_current(mocker):
    return mocker.patch(
        'thebleep.rules.history.get_valid_history_without_current',
        return_value=['ls cat', 'diff x'])


@pytest.mark.parametrize('script', ['ls cet', 'daff x'])
def test_match(script):
    assert match(Command(script, ''))


@pytest.mark.parametrize('script', ['apt-get', 'nocommand y'])
def test_not_match(script):
    assert not match(Command(script, ''))


@pytest.mark.parametrize('script, result', [
    ('ls cet', 'ls cat'),
    ('daff x', 'diff x')])
def test_get_new_command(script, result):
    assert get_new_command(Command(script, '')) == [result]


@pytest.mark.parametrize('script, history', [
    # Each of these was offered, from an ordinary history, by the old rule.
    ('mkdir dir1', ['git rm dir1']),
    ('git push origin mian', ['git push --force origin main']),
    ('rm -rf /var/cache/y', ['sudo rm -rf /var/cache/x']),
    ('git merge featre', ['git checkout featuer']),
    # One word apart, but the one word is a different thing altogether.
    ('git log --graf', ['git log --stat']),
])
def test_unrelated_and_riskier_lines_are_not_corrections(
        script, history, history_without_current):
    history_without_current.return_value = history
    assert not match(Command(script, ''))


def test_the_risk_the_command_already_had_is_allowed(history_without_current):
    history_without_current.return_value = ['sudo apt install vim']
    assert get_new_command(Command('sudo apt instal vim', '')) == [
        'sudo apt install vim']


def test_a_command_that_succeeded_is_left_alone(history_without_current,
                                                os_environ):
    os_environ['TB_EXIT'] = '0'
    assert not match(Command('ls cet', ''))
