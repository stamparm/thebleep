from thebleep.utils import eager, replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return (
        parts[index:index + 1] == ["commit"]
        and "no changes added to commit" in command.output
    )


@eager
@git_support
def get_new_command(command):
    for opt in ("-a", "-p"):
        yield replace_argument(command.script, "commit", "commit {}".format(opt))
