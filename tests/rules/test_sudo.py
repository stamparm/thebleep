import shlex
import pytest
from thebleep.rules.sudo import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('output', [
    'Permission denied',
    'permission denied',
    "npm ERR! Error: EACCES, unlink",
    'requested operation requires superuser privilege',
    'need to be root',
    'need root',
    'shutdown: NOT super-user',
    'Error: This command has to be run with superuser privileges (under the root user on most systems).',
    'updatedb: can not open a temporary file for `/var/lib/mlocate/mlocate.db',
    'must be root',
    'You don\'t have access to the history DB.',
    "error: [Errno 13] Permission denied: '/usr/local/lib/python2.7/dist-packages/ipaddr.py'"])
def test_match(output):
    assert match(Command('', output))


def test_not_match():
    assert not match(Command('', ''))
    assert not match(Command('sudo ls', 'Permission denied'))


@pytest.mark.parametrize('before, after', [
    ('ls', 'sudo ls'),
    ('echo a > b', "sudo sh -c 'echo a > b'"),
    ('echo "a" >> b', 'sudo sh -c \'echo "a" >> b\''),
    ('mkdir && touch a', "sudo sh -c 'mkdir && touch a'"),
    ('sudo apt update && sudo apt upgrade',
     "sudo sh -c 'apt update && apt upgrade'")])
def test_get_new_command(before, after):
    assert get_new_command(Command(before, '')) == after


@pytest.mark.parametrize('script', [
    # Each of these has something the user quoted so it would stay data.
    """mkdir /opt/x && echo '$(id -u)'""",
    """mkdir /opt/x && echo '`id -u`'""",
    """touch /etc/x && printf '%s' '$HOME'""",
    '''mkdir /opt/x && touch 'a"; id -u; echo "b\'''',
    """echo '$(id -u)' > /etc/conf""",
    '''echo 'a"b' > /etc/conf''',
])
def test_the_script_reaches_root_exactly_as_it_was_typed(script):
    """What `sh -c` runs is run by root, so it has to be the command the user
    typed and nothing else.

    A quote in the script used to close the `sh -c` argument early, which both
    split one root command into several and let text the user had quoted as
    data be evaluated as code.

    """
    new_command = get_new_command(Command(script, 'permission denied'))

    argv = shlex.split(new_command)
    assert argv[:3] == ['sudo', 'sh', '-c'], 'the script escaped its argument'
    assert len(argv) == 4, 'the script split into more than one command'
    assert argv[3] == script
