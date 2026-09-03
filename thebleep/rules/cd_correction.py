"""Attempts to spellcheck and correct failed cd commands"""

import os
import re
from thebleep.specific.sudo import sudo_support
from thebleep.rules import cd_mkdir
from thebleep.shells import shell
from thebleep.utils import (command_word_index, for_app, get_close_matches,
                            replace_argument)

__author__ = "mmussomele"

MAX_ALLOWED_DIFF = 0.6


def _get_sub_dirs(parent):
    """Returns a list of the child directories of the given parent directory"""
    return [child for child in os.listdir(parent) if os.path.isdir(os.path.join(parent, child))]


@sudo_support
@for_app('cd')
def match(command):
    """The same question as cd_mkdir's, asked the same way."""
    return cd_mkdir.match(command)


@sudo_support
def get_new_command(command):
    """
    Attempt to rebuild the path string by spellchecking the directories.
    If it fails (i.e. no directories are a close enough match), then it
    defaults to the rules of cd_mkdir.
    Change sensitivity by changing MAX_ALLOWED_DIFF. Default value is 0.6
    """
    start = command_word_index(command.script_parts)
    typed = command.script_parts[start + 1]
    # Either separator on Windows, where people type both; and the one that
    # was typed is the one the correction is joined with, so `../Documnets`
    # comes back as `../Documents` there too.
    separator = ('/' if '/' in typed else os.sep) if os.name == 'nt' else '/'
    dest = re.split(r'[\\/]' if os.name == 'nt' else '/', typed)
    if dest[-1] == '':
        dest = dest[:-1]

    absolute = os.path.isabs(typed)
    if absolute:
        # `/x` splits to ['', 'x']; `C:\x` to ['C:', 'x'].
        cwd = (dest[0] + os.sep) if dest[0] else os.sep
        dest = dest[1:]
    else:
        cwd = os.getcwd()
    # What was typed, spelling fixed. `cd Documnets` used to come back as
    # `cd /home/me/projects/Documents`: right, and nothing like what anyone
    # would have typed. A relative destination stays relative.
    corrected = []
    for directory in dest:
        if directory == ".":
            corrected.append(directory)
            continue
        elif directory == "..":
            cwd = os.path.split(cwd)[0]
            corrected.append(directory)
            continue
        best_matches = get_close_matches(directory, _get_sub_dirs(cwd), cutoff=MAX_ALLOWED_DIFF)
        if best_matches:
            cwd = os.path.join(cwd, best_matches[0])
            corrected.append(best_matches[0])
        else:
            return cd_mkdir.get_new_command(command)
    fixed = cwd if absolute else separator.join(corrected)
    return replace_argument(command.script,
                            command.script_parts[start + 1],
                            shell.quote(fixed))
