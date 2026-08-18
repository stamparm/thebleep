"""Our own standard streams, whatever the machine's locale says.

The rules quote file names, branch names and package names back to the user,
and those are as likely to be `Résumé.pdf` as not. The alias used to arrange
for that by exporting `PYTHONIOENCODING=utf-8` before calling us, which had two
costs: every command we then ran again to read its output inherited a variable
that was not in the environment when it originally ran, and putting the old
value back afterwards turned an unset `PYTHONIOENCODING` into an exported empty
one. Setting the encoding on our own streams is the same thing, here, where it
belongs.

"""

import sys


def use_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is None:
            # Replaced by something that is not a text wrapper: a capturing
            # buffer under a test runner, or colorama's console proxy.
            continue
        try:
            reconfigure(encoding='utf-8')
        except (ValueError, OSError):
            # Detached or already closed. Nothing to write on it either way.
            pass
