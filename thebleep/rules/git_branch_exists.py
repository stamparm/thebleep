import re
from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import eager


# git 2.38 and older:  fatal: A branch named 'x' already exists.
# git 2.39 and newer:  fatal: a branch named 'x' already exists
#
# The capital and the full stop both went, and this wanted both -- so the rule
# was dead on every git in current use while its test stayed green, because the
# fixture was written by hand from the old wording. Captured from git 2.30.2,
# 2.39.5 and 2.47.3.
ALREADY_EXISTS = re.compile(r"fatal: a branch named '(.+)' already exists\.?",
                            re.IGNORECASE)


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    if index == len(parts):
        return False

    subcommand = parts[index]
    arguments = parts[index + 1:]
    if subcommand == 'branch':
        # A plain positional name is the ordinary branch-creation form. The
        # listing/deletion/move forms can mention a branch name too, but do not
        # explain this diagnostic.
        creates_branch = bool(arguments) and not arguments[0].startswith('-')
    elif subcommand == 'checkout':
        creates_branch = any(
            flag in arguments for flag in ('-b', '-B', '--orphan'))
    elif subcommand == 'switch':
        creates_branch = any(flag in arguments for flag in (
            '-c', '-C', '--create', '--force-create'))
    else:
        creates_branch = False

    return creates_branch and bool(ALREADY_EXISTS.search(command.output))


@git_support
@eager
def get_new_command(command):
    branch_name = ALREADY_EXISTS.search(command.output).group(1)
    # `shell.quote`, not a hand-rolled `\'`: a backslash does not escape
    # anything inside single quotes, and the name was not inside quotes at all.
    # git accepts a branch called `feature;rm -rf ~`, so this went to the shell
    # as two commands.
    branch = shell.quote(branch_name)
    parts = command.script_parts
    switch = parts[git_subcommand_index(parts)] == 'switch'
    # The branch is there, so the likeliest want is to be on it -- in the verb
    # that was typed. Deleting it came first and `-D` third, which threw away
    # unmerged commits two keystrokes from the prompt; `-d` refuses to, and
    # then the command runs again as typed, start point and all.
    yield u'git {} {}'.format('switch' if switch else 'checkout', branch)
    yield shell.and_(u'git branch -d {}'.format(branch), command.script)
