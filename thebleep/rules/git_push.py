import re
from thebleep.utils import quote_words, raw_script_parts, replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['push']
            and 'git push --set-upstream' in command.output)


def _get_upstream_option_index(command_parts, start):
    for index, part in enumerate(command_parts[start:], start):
        if part in ('--set-upstream', '-u'):
            return index

    else:
        return None


@git_support
def get_new_command(command):
    # If --set-upstream or -u are passed, remove it and its argument. This is
    # because the remaining arguments are concatenated onto the command suggested
    # by git, which includes --set-upstream and its argument
    command_parts = command.script_parts[:]
    raw_parts = raw_script_parts(command.script)
    if len(raw_parts) != len(command_parts):
        return []
    push_index = git_subcommand_index(command_parts)
    upstream_option_index = _get_upstream_option_index(command_parts,
                                                       push_index + 1)

    if upstream_option_index is not None:
        command_parts.pop(upstream_option_index)
        raw_parts.pop(upstream_option_index)

        # In case of `git push -u` we don't have next argument:
        if len(command_parts) > upstream_option_index:
            command_parts.pop(upstream_option_index)
            raw_parts.pop(upstream_option_index)
    else:
        # the only non-qualified permitted options are the repository and refspec; git's
        # suggestion include them, so they won't be lost, but would be duplicated otherwise.
        push_idx = git_subcommand_index(command_parts) + 1
        while len(command_parts) > push_idx and command_parts[len(command_parts) - 1][0] != '-':
            command_parts.pop(len(command_parts) - 1)
            raw_parts.pop(len(raw_parts) - 1)

    # git's hint has the branch name in it and a branch name may be shell
    # syntax, so the words of the hint are quoted rather than pasted in. This was
    # `.replace("'", r"\'")`, which was added upstream to stop a branch with an
    # apostrophe in it crashing the eval and does nothing at all about `;`, `$()`
    # or a backtick. Quoting also settles the crash it was written for, and the
    # `#` in a name like `swteam/#486/general` that broke zsh.
    arguments = re.findall(r'git push (.*)', command.output)[-1].strip()
    return replace_argument(" ".join(raw_parts), 'push',
                            'push {}'.format(quote_words(arguments)))
