from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import memoize, replace_argument


@memoize
def first_0flag(script_parts):
    return next((p for p in script_parts if len(p) == 2 and p.startswith("0")), None)


@git_support
def match(command):
    # `git` on its own is a thing people type, and `git_support` only says which
    # program this is, not that it has a subcommand.
    parts = command.script_parts
    return len(parts) > 1 and parts[1] == "branch" and first_0flag(parts)


@git_support
def get_new_command(command):
    branch_name = first_0flag(command.script_parts)
    fixed_flag = branch_name.replace("0", "-")
    fixed_script = replace_argument(command.script, branch_name, fixed_flag)
    if "A branch named '" in command.output and "' already exists." in command.output:
        delete_branch = u"git branch -D {}".format(branch_name)
        return shell.and_(delete_branch, fixed_script)
    return fixed_script
