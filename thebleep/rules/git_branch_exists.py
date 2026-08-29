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
    for template in ([u'git branch -d {0}', u'git branch {0}'],
                     [u'git branch -d {0}', u'git checkout -b {0}'],
                     [u'git branch -D {0}', u'git branch {0}'],
                     [u'git branch -D {0}', u'git checkout -b {0}'],
                     [u'git checkout {0}']):
        yield shell.and_(*[part.format(branch) for part in template])
