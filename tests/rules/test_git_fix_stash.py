import pytest
from thebleep.rules.git_fix_stash import match, get_new_command
from thebleep.types import Command


git_stash_err = '''
usage: git stash list [<options>]
   or: git stash show [<stash>]
   or: git stash drop [-q|--quiet] [<stash>]
   or: git stash ( pop | apply ) [--index] [-q|--quiet] [<stash>]
   or: git stash branch <branchname> [<stash>]
   or: git stash [save [--patch] [-k|--[no-]keep-index] [-q|--quiet]
\t\t       [-u|--include-untracked] [-a|--all] [<message>]]
   or: git stash clear
'''


@pytest.mark.parametrize('wrong', [
    'git stash opp',
    'git stash Some message',
    'git stash saev Some message'])
def test_match(wrong):
    assert match(Command(wrong, git_stash_err))


def test_not_match():
    assert not match(Command("git", git_stash_err))


@pytest.mark.parametrize('wrong,fixed', [
    ('git stash opp', 'git stash pop'),
    ('git stash Some message', 'git stash save Some message'),
    ('git stash saev Some message', 'git stash save Some message')])
def test_get_new_command(wrong, fixed):
    assert get_new_command(Command(wrong, git_stash_err)) == fixed


# git 2.43, which prints no usage block at all -- and names the token it could
# not read, which the usage block never did.
MODERN = ("fatal: subcommand wasn't specified; 'push' can't be assumed due to"
          " unexpected token '{}'\n").format


class TestAgainstCurrentGit(object):
    """The rule looked for `usage:` and git stopped printing one, so every
    `git stash` typo went uncorrected for however many releases that has been."""

    @pytest.mark.parametrize('script, token, fixed', [
        ('git stash pp', 'pp', 'git stash pop'),
        ('git stash saev x', 'saev', 'git stash save x'),
        ('git stash aply', 'aply', 'git stash apply'),
        ('git stash dorp', 'dorp', 'git stash drop'),
        # An option in front of it, which is why the token is read out of the
        # message rather than taken from index 2.
        ('git stash -q saev', 'saev', 'git stash -q save'),
    ])
    def test_it_reads_the_token_git_named(self, script, token, fixed):
        command = Command(script, MODERN(token))
        assert match(command)
        assert get_new_command(command) == fixed

    def test_a_message_becomes_a_save(self):
        command = Command('git stash Some message', MODERN('Some'))
        assert match(command)
        assert get_new_command(command) == 'git stash save Some message'

    def test_a_stash_that_worked_says_nothing(self):
        assert not match(Command('git stash list', ''))
