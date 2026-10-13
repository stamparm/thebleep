"""`git pull` on a branch that has diverged from its upstream.

    $ git pull
    hint: You have divergent branches and need to specify how to reconcile them.
    ...
    fatal: Need to specify how to reconcile divergent branches.

Every git since 2.33 says this to anyone who never set `pull.rebase`, and the
three answers are in its own hint. Rebase first, because it is the one that
keeps history linear and the one most people set once they have been asked;
then a merge, then fast-forward only. Captured from git 2.53.0.

"""

from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_command_word


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['pull']
            and 'Need to specify how to reconcile divergent branches'
            in command.output)


@git_support
def get_new_command(command):
    index = git_subcommand_index(command.script_parts)
    return [replace_command_word(command.script, index, 'pull ' + flag)
            for flag in ('--rebase', '--no-rebase', '--ff-only')]
