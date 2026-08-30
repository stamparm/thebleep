import pytest
from thebleep.rules.lein_not_task import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def is_not_task():
    return ''''rpl' is not a task. See 'lein help'.

Did you mean this?
         repl
         jar
'''


def test_match(is_not_task):
    assert match(Command('lein rpl', is_not_task))
    assert not match(Command('ls', is_not_task))


def test_get_new_command(is_not_task):
    assert (get_new_command(Command('lein rpl --help', is_not_task))
            == ['lein repl --help', 'lein jar --help'])


def test_prefixed_command_keeps_assignment(is_not_task):
    command = Command('LEIN_JVM_OPTS=-Xmx1g lein rpl', is_not_task)
    assert match(command)
    assert get_new_command(command) == [
        'LEIN_JVM_OPTS=-Xmx1g lein repl',
        'LEIN_JVM_OPTS=-Xmx1g lein jar']
