from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import memoize, replace_argument


@memoize
def first_0flag(script_parts):
    return next((p for p in script_parts if len(p) == 2 and p.startswith("0")), None)


@git_support
def match(command):
    # `git` on its own is a thing people type, and `git_support` only says which
    # program this is, not that it has a subcommand.
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return (index < len(parts) and parts[index] == "branch"
            and first_0flag(parts[index + 1:]))


@git_support
def get_new_command(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    branch_name = first_0flag(parts[index + 1:])
    fixed_flag = branch_name.replace("0", "-")
    fixed_script = replace_argument(command.script, branch_name, fixed_flag)
    if "A branch named '" in command.output and "' already exists." in command.output:
        delete_branch = u" ".join(parts[:index + 1] + ['-D', branch_name])
        return shell.and_(delete_branch, fixed_script)
    return fixed_script
