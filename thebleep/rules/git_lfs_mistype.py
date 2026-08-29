import re
from thebleep.utils import get_all_matched_commands, replace_command
from thebleep.specific.git import git_subcommand_index, git_support


UNKNOWN = re.compile(r'Error: unknown command "([^"]*)" for "git-lfs"')


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    unknown = UNKNOWN.search(command.output)
    return (index + 1 < len(command.script_parts)
            and command.script_parts[index] == 'lfs'
            and unknown is not None
            and command.script_parts[index + 1] == unknown.group(1)
            and 'Did you mean this?' in command.output)


@git_support
def get_new_command(command):
    broken_cmd = UNKNOWN.search(command.output).group(1)
    matched = get_all_matched_commands(command.output, ['Did you mean', ' for usage.'])
    return replace_command(command, broken_cmd, matched)
