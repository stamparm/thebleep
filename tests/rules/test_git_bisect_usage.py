import pytest
from thebleep.types import Command
from thebleep.rules.git_bisect_usage import match, get_new_command


@pytest.fixture
def output():
    return ("usage: git bisect [help|start|bad|good|new|old"
            "|terms|skip|next|reset|visualize|replay|log|run]")


@pytest.mark.parametrize('script', [
    'git bisect strt', 'git bisect rset', 'git bisect goood'])
def test_match(output, script):
    assert match(Command(script, output))


@pytest.mark.parametrize('script', [
    'git bisect', 'git bisect start', 'git bisect good'])
def test_not_match(script):
    assert not match(Command(script, ''))


@pytest.mark.parametrize('script, new_cmd, ', [
    ('git bisect goood', ['good', 'old', 'log']),
    ('git bisect strt', ['start', 'terms', 'reset']),
    ('git bisect rset', ['reset', 'next', 'start'])])
def test_get_new_command(output, script, new_cmd):
    new_cmd = ['git bisect %s' % cmd for cmd in new_cmd]
    assert get_new_command(Command(script, output)) == new_cmd


@pytest.mark.parametrize('output', [
    # git 2.30.2 and 2.39.5.
    'usage: git bisect [help|start|bad|good|new|old|terms|skip|next|reset]',
    # git 2.47.3 answers a bare `git bisect` with this and no usage line.
    'fatal: need a command',
])
def test_a_bare_git_bisect_does_not_crash(output):
    """Forgetting the subcommand is how you find out you forgot it.

    There is nothing after `bisect` to correct, so the regex found nothing and
    the `[0]` on it raised `IndexError` -- a traceback in the terminal rather
    than a correction. Nothing to offer here is the right answer; crashing is
    not.

    """
    command = Command('git bisect', output)
    assert not match(command)
