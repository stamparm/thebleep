# -*- encoding: utf-8 -*-

"""`pip install` into an interpreter the operating system maintains.

Since PEP 668, a distribution can mark its Python as externally managed, and
Debian, Ubuntu, Fedora and Arch all do. Installing into it anyway leaves the
package manager's idea of what is installed and reality disagreeing, which is
why pip refuses:

    error: externally-managed-environment

    × This environment is externally managed
    ╰─> To install Python packages system-wide, try apt install python3-xyz...
        If you wish to install a non-Debian-packaged Python package, create a
        virtual environment using python3 -m venv path/to/venv...
        If you wish to install a non-Debian packaged Python application, it may
        be easiest to use pipx install xyz...

    note: ... You can override this, at the risk of breaking your Python
    installation or OS, by passing --break-system-packages.

What is suggested is what the message itself recommends, in that order: `pipx`
for an application, a virtual environment for anything else.

What is deliberately not suggested is `--break-system-packages`. It is in the
message, it is one word, and it would make this rule look clever -- and it is
the one outcome the error exists to prevent. A correction is a command somebody
accepts in half a second from a prompt, which is not where that decision
belongs. Nor is `sudo pip install`, for the same reason `pip_install` stopped
offering it.

`--user` is not offered either, and would not help: PEP 668 marks the user site
as externally managed too, so on Debian it fails with this same message.

Refs: nvbn/thefuck#1553

"""

import re
from thebleep.shells import shell
from thebleep.utils import which

# The marker pip prints, and the marker of the operation. Both, because the
# same message comes out of `pip download` and `pip wheel`, where creating a
# virtual environment to hold the answer is not what anybody wants.
EXTERNALLY_MANAGED = 'externally-managed-environment'

# `pip install`, `pip3 install`, `python -m pip install`, `python3.12 -m pip
# install`, and the same behind `sudo` -- which the wrapper model has already
# peeled off by the time a rule sees it, but a command typed with `python -m`
# still has to be recognised here.
PIP_INSTALL = re.compile(
    r'(^|\s)(pip[0-9.]*|python[0-9.]*\s+-m\s+pip)\s+install(\s|$)')

# What is being installed, as opposed to how.
NOT_A_PACKAGE = re.compile(r'^-')

# Options that mean this is not one named package going in, so `pipx` -- which
# installs one application -- is not the answer.
NOT_FOR_PIPX = frozenset({'-r', '--requirement', '-e', '--editable',
                          '--target', '-t', '--prefix', '--root'})

# Where a virtual environment goes when the user has not said. `.venv` is what
# every tool that makes one for you uses, and what every `.gitignore` already
# has in it.
VENV = '.venv'


def match(command):
    return (EXTERNALLY_MANAGED in command.output
            and bool(PIP_INSTALL.search(command.script)))


def _packages(parts):
    """The names being installed, and whether pipx could install them."""
    try:
        start = parts.index('install') + 1
    except ValueError:
        return [], False

    rest = parts[start:]
    if any(part in NOT_FOR_PIPX for part in rest):
        return [], False

    names = [part for part in rest if not NOT_A_PACKAGE.match(part)]
    return names, len(names) == 1


def get_new_command(command):
    parts = command.script_parts
    names, one_application = _packages(parts)

    suggestions = []
    if one_application and which('pipx'):
        # An application, into an environment pipx keeps for it. This is the
        # message's own first suggestion for anything you meant to *run*.
        suggestions.append(u'pipx install {}'.format(shell.quote(names[0])))

    # And the answer for everything else, which is also the message's: a
    # virtual environment, named the way every tool that makes one names it.
    #
    # The arguments are re-quoted rather than re-joined. `script_parts` is the
    # command already split, so joining it with spaces hands the shell
    # something different from what it was given: `pip install
    # 'requests[security]'` came back with the brackets bare, which is a glob,
    # and `pip install ./my package` came back as two arguments.
    if 'install' in parts:
        what = ' '.join(shell.quote(part)
                        for part in parts[parts.index('install') + 1:])
    else:
        what = ''

    suggestions.append(
        u'python3 -m venv {venv} && {venv}/bin/pip install {what}'.format(
            venv=VENV, what=what).rstrip())

    return suggestions
