# -*- encoding: utf-8 -*-

"""`git remote ad origin x` -> `git remote add origin x`.

git has a dozen commands that dispatch again on a second word, and a typo in
that second word got nothing at all from any rule. `git_not_command` reads
git's "most similar command" suggestion and git makes none here -- it prints its
usage, which is a list of the answers going unread.

Every output below was printed by git 2.43, captured verbatim, including the
awkward shapes: an option between the command and its subcommand, an
alternation on one line, and a usage line that wraps.

"""

import pytest
from thebleep.rules.git_unknown_subcommand import match, get_new_command
from thebleep.types import Command

REMOTE = """error: unknown subcommand: `ad'
usage: git remote [-v | --verbose]
   or: git remote add [-t <branch>] [-m <master>] [-f] [--tags | --no-tags] [--mirror=<fetch|push>] <name> <url>
   or: git remote rename [--[no-]progress] <old> <new>
   or: git remote remove <name>
   or: git remote set-head <name> (-a | --auto | -d | --delete | <branch>)
   or: git remote [-v | --verbose] show [-n] <name>
   or: git remote prune [-n | --dry-run] <name>
   or: git remote [-v | --verbose] update [-p | --prune] [(<group> | <remote>)...]
   or: git remote set-branches [--add] <name> <branch>...
   or: git remote get-url [--push] [--all] <name>
   or: git remote set-url [--push] <name> <newurl> [<oldurl>]
"""

# A usage line that wraps, and no `usage: git worktree` line of its own.
WORKTREE = """error: unknown subcommand: `lst'
usage: git worktree add [-f] [--detach] [--checkout] [--lock [--reason <string>]]
                        [--orphan] [(-b | -B) <new-branch>] <path> [<commit-ish>]
   or: git worktree list [-v | --porcelain [-z]]
   or: git worktree lock [--reason <string>] <worktree>
   or: git worktree move <worktree> <new-path>
   or: git worktree prune [-n] [-v] [--expire <expire>]
   or: git worktree remove [-f] <worktree>
   or: git worktree repair [<path>...]
   or: git worktree unlock <worktree>
"""

# An option between the command and the subcommand: `git notes [--ref <x>] add`.
NOTES = """error: unknown subcommand: `ad'
usage: git notes [--ref <notes-ref>] [list [<object>]]
   or: git notes [--ref <notes-ref>] add [-f] [--allow-empty] [<object>]
   or: git notes [--ref <notes-ref>] copy [-f] <from-object> <to-object>
   or: git notes [--ref <notes-ref>] append [--allow-empty] [<object>]
   or: git notes [--ref <notes-ref>] edit [--allow-empty] [<object>]
   or: git notes [--ref <notes-ref>] show [<object>]
   or: git notes [--ref <notes-ref>] remove [<object>...]
   or: git notes [--ref <notes-ref>] prune [-n] [-v]
"""

# The whole list on one line, as an alternation.
SPARSE = """error: unknown subcommand: `se'
usage: git sparse-checkout (init | list | set | add | reapply | disable | check-rules) [<options>]
"""


@pytest.mark.parametrize('script, output, first', [
    ('git remote ad origin x', REMOTE, 'git remote add origin x'),
    ('git worktree lst', WORKTREE, 'git worktree list'),
    ('git notes ad', NOTES, 'git notes add'),
    ('git sparse-checkout se', SPARSE, 'git sparse-checkout set'),
])
def test_it_reads_the_list_git_printed(script, output, first):
    command = Command(script, output)
    assert match(command)
    assert get_new_command(command)[0] == first


def test_the_rest_of_the_command_survives():
    command = Command('git remote ad origin git@example.com:x.git', REMOTE)
    assert get_new_command(command)[0] \
        == 'git remote add origin git@example.com:x.git'


def test_no_placeholder_is_offered_as_a_subcommand():
    """`<name>`, `<url>` and `[-v | --verbose]` are all on those lines."""
    offered = get_new_command(Command('git remote ad', REMOTE))
    for suggestion in offered:
        word = suggestion.split()[2]
        assert word.replace('-', '').isalpha(), word


def test_an_option_between_the_two_is_stepped_over():
    """`git notes [--ref <notes-ref>] add` -- the subcommand is the third word
    of that line, not the second."""
    offered = get_new_command(Command('git notes ad', NOTES))
    assert 'git notes add' in offered


class TestWhenItSaysNothing(object):
    @pytest.mark.parametrize('output', [
        '',
        # The error without a usage block.
        "error: unknown subcommand: `ad'\n",
        # A usage block for something else entirely.
        "error: unknown subcommand: `ad'\nusage: git commit [-a] [-m <msg>]\n",
        # git's own suggestion, which `git_not_command` reads.
        "git: 'remot' is not a git command. See 'git --help'.\n\n"
        'The most similar command is\n\tremote\n',
    ])
    def test_output_it_cannot_read(self, output):
        assert not match(Command('git remote ad', output))

    def test_a_command_with_no_subcommand_in_it(self):
        assert not match(Command('git remote', REMOTE))
