import os

from thebleep.utils import for_app, replace_argument, which
from thebleep.utils import command_word_index


@for_app("choco", "cinst")
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    app = os.path.basename(parts[start]) if start < len(parts) else None
    return ((len(parts) > start + 1 and
             ((app == 'choco' and parts[start + 1] == 'install')
              or app == 'cinst'))
            and 'Installing the following packages' in command.output)


def get_new_command(command):
    # Find the argument that is the package name
    for script_part in command.script_parts:
        if (
            script_part not in ["choco", "cinst", "install"]
            # Need exact match (bc chocolatey is a package)
            and not script_part.startswith('-')
            # Leading hyphens are parameters; some packages contain them though
            and '=' not in script_part and '/' not in script_part
            # These are certainly parameters
        ):
            fixed = replace_argument(command.script, script_part,
                                     script_part + ".install")
            if fixed != command.script:
                return fixed
    return []


enabled_by_default = bool(which("choco")) or bool(which("cinst"))
