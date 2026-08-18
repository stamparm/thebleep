"""Installing the package a missing import needs -- off by default.

An import name is not a distribution name. `import yaml` wants PyYAML, `cv2`
wants opencv-python, `sklearn` wants scikit-learn, `bs4` wants beautifulsoup4,
`Crypto` wants pycryptodome. Nothing in the error message says which, and
nothing here can find out without asking an index.

So the name in `pip install <name>` is a guess, and the guess is fetched from a
public index and executed. When it is wrong the outcome ranges from "no such
package" to installing something entirely unrelated that somebody registered
under the name -- and a mistyped import (`import reqeusts`) turns the suggestion
into `pip install reqeusts`, which is exactly the shape a typosquat waits for.

That is not something to offer as a default one-keypress correction, so this
rule is off unless it is asked for:

    rules = ['DEFAULT_RULES', 'python_module_error']

With it on, the install goes through the interpreter that raised the error
rather than through whichever `pip` happens to be first on PATH, so the package
at least lands where the failing program will look for it.

"""

import re
from thebleep.shells import shell
from thebleep.utils import command_word_index

MISSING_MODULE = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")

enabled_by_default = False


def _interpreter(command):
    """The python that raised this, when the command says which."""
    parts = command.script_parts
    parts = parts[command_word_index(parts):]
    if parts and re.match(r'^(.*/)?python[\d.]*$', parts[0]):
        return parts[0]
    return None


def match(command):
    return MISSING_MODULE.search(command.output) is not None


def get_new_command(command):
    missing_module = MISSING_MODULE.search(command.output).group(1)
    interpreter = _interpreter(command)
    install = u'{} -m pip install {}'.format(
        shell.quote(interpreter), shell.quote(missing_module)) \
        if interpreter else \
        u'pip install {}'.format(shell.quote(missing_module))
    return shell.and_(install, command.script)
