import re
from thebleep.utils import for_app, replace_command
from thebleep.specific.npm import get_scripts, npm_available

enabled_by_default = npm_available

# npm used to write `missing script: build`; from npm 7 it is
# `Missing script: "build"`, and from npm 10 the `npm ERR!` prefix on the
# line became `npm error`.
MISSING_SCRIPT = re.compile(r'[Mm]issing script:\s*"?([^"\r\n]+?)"?\s*$',
                            re.MULTILINE)


@for_app('npm')
def match(command):
    return (any(part.startswith('ru') for part in command.script_parts)
            and MISSING_SCRIPT.search(command.output) is not None)


def get_new_command(command):
    misspelled_script = MISSING_SCRIPT.search(command.output).group(1)
    return replace_command(command, misspelled_script, get_scripts())
