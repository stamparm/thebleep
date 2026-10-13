import pytest

from thebleep.rules.systemctl import match, get_new_command
from thebleep.types import Command

# systemd 262 (debian:testing); 245 and older said `Unknown operation`.
OLD = "Unknown operation 'nginx'."
NEW = "Unknown command verb 'nginx', did you mean 'bind'?"


@pytest.mark.parametrize('output', [OLD, NEW])
def test_match(output):
    assert match(Command('systemctl nginx start', output))
    assert match(Command('sudo systemctl nginx start', output))
    assert not match(Command('systemctl start nginx', ''))
    assert not match(Command('sudo systemctl nginx', output))
    assert not match(Command('systemctl nginx', output))
    assert not match(Command('systemctl start wtf', 'Failed to start wtf.service: Unit wtf.service failed to load: No such file or directory.'))


@pytest.mark.parametrize('output', [OLD, NEW])
def test_get_new_command(output):
    """The unit was typed where the verb goes; systemd's `bind` is no help."""
    assert get_new_command(Command('systemctl nginx start', output)) == [
        'systemctl start nginx']
    assert get_new_command(Command('sudo systemctl nginx start', output)) == [
        'sudo systemctl start nginx']


@pytest.mark.parametrize('script, output, fixed', [
    ('systemctl strat ssh',
     "Unknown command verb 'strat', did you mean 'start'?", 'systemctl start ssh'),
    ('sudo systemctl statsu ssh',
     "Unknown command verb 'statsu', did you mean 'status'?",
     'sudo systemctl status ssh'),
])
def test_systemds_own_suggestion(script, output, fixed):
    assert match(Command(script, output))
    assert get_new_command(Command(script, output)) == [fixed]


def test_a_suggestion_nowhere_near_is_not_taken():
    output = "Unknown command verb 'xyzzy', did you mean 'show'?"
    assert not match(Command('systemctl xyzzy ssh', output))
