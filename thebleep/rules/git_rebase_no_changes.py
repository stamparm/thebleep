from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (
        command.script_parts[index:index + 2] == ['rebase', '--continue'] and
        'No changes - did you forget to use \'git add\'?' in command.output
    )


def get_new_command(command):
    return 'git rebase --skip'
