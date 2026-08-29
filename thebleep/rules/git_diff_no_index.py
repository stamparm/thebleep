from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    files = [arg for arg in parts[index + 1:]
             if not arg.startswith('-')]
    return (parts[index:index + 1] == ['diff']
            and '--no-index' not in parts
            and len(files) == 2)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'diff', 'diff --no-index')


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
