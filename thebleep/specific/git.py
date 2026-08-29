import re
from ..utils import command_word_index, decorator, is_app, replace_argument
from ..shells import shell


_GIT_GLOBAL_OPTIONS = frozenset((
    '--version', '--help', '-p', '--paginate', '-P', '--no-pager',
    '--no-replace-objects', '--no-lazy-fetch', '--no-optional-locks',
    '--no-advice', '--bare', '--literal-pathspecs', '--glob-pathspecs',
    '--noglob-pathspecs', '--icase-pathspecs',
))
_GIT_TERMINAL_OPTIONS = frozenset(('--version', '--help'))
_GIT_GLOBAL_OPTIONS_WITH_ARGUMENT = frozenset((
    '-C', '-c', '--exec-path', '--git-dir', '--work-tree', '--namespace',
    '--super-prefix', '--config-env',
))
_GIT_GLOBAL_OPTION_PREFIXES = (
    '--exec-path=', '--git-dir=', '--work-tree=', '--namespace=',
    '--super-prefix=', '--config-env=', '--list-cmds=',
)


def git_subcommand_index(script_parts):
    """Return the index of Git's subcommand, or ``len(script_parts)``.

    Git accepts global options between its executable and subcommand. Looking
    for a word anywhere after ``git`` confuses those options and their values
    with the command itself; for example, ``git config --get-regexp pull`` is
    not a pull. Keep this parser deliberately limited to Git's global options,
    so an arbitrary unknown option is treated as the command and cannot make a
    rule guess past an invocation Git would reject.
    """
    index = command_word_index(script_parts)
    if index == len(script_parts):
        return index

    index += 1
    while index < len(script_parts):
        part = script_parts[index]
        if part == '--':
            return index + 1
        if part in _GIT_TERMINAL_OPTIONS:
            return len(script_parts)
        if part in _GIT_GLOBAL_OPTIONS_WITH_ARGUMENT:
            index += 2
            continue
        if ((part.startswith('-C') and part != '-C')
                or (part.startswith('-c') and part != '-c')):
            index += 1
            continue
        if part in _GIT_GLOBAL_OPTIONS or any(
                part.startswith(prefix) for prefix in _GIT_GLOBAL_OPTION_PREFIXES):
            index += 1
            continue
        return index

    return index


@decorator
def git_support(fn, command):
    """Resolves git aliases and supports testing for both git and hub."""
    # supports GitHub's `hub` command
    # which is recommended to be used with `alias git=hub`
    # but at this point, shell aliases have already been resolved
    if not is_app(command, 'git', 'hub'):
        return False

    # perform git aliases expansion
    if command.output and 'trace: alias expansion:' in command.output:
        search = re.search("trace: alias expansion: ([^ ]*) => ([^\n]*)",
                           command.output)
        if not search:
            return fn(command)

        alias = search.group(1)

        # by default git quotes everything, for example:
        #     'commit' '--amend'
        # which is surprising and does not allow to easily test for
        # eg. 'git commit'
        expansion = ' '.join(shell.quote(part)
                             for part in shell.split_command(search.group(2)))
        new_script = replace_argument(command.script, alias, expansion)

        command = command.update(script=new_script)

    return fn(command)
