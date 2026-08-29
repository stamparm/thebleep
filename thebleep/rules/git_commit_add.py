from thebleep.utils import command_word_index, eager, replace_argument
from thebleep.specific.git import git_support


@git_support
def match(command):
    parts = command.script_parts
    index = command_word_index(parts)
    return (
        parts[index + 1:index + 2] == ["commit"]
        and "no changes added to commit" in command.output
    )


@eager
@git_support
def get_new_command(command):
    for opt in ("-a", "-p"):
        yield replace_argument(command.script, "commit", "commit {}".format(opt))
