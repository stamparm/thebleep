# -*- encoding: utf-8 -*-

"""How the alias calls The Bleep back.

The alias is shell code that runs The Bleep again, so it has to name it. For an
installed copy the name is `thebleep`, the entry point on `PATH`, which is what
this returns and what was written into every alias before there was any choice
about it.

A clone was the case that had no answer. `python -m thebleep` from a checkout
runs the checkout, but the alias it printed still said `thebleep`, so the shell
went back to whatever was installed -- you could work on 4.0.3 all day and have
4.0.0 correcting your commands, with nothing to tell you. The fix is not another
installer: the alias now names the interpreter and the checkout it came from, so
a clone is a clone and a `git pull` is the whole upgrade.

    eval "$(python3 -m thebleep --alias)"     # in your startup file, from
                                              # anywhere the clone is importable

`THEBLEEP_COMMAND` overrides the lot. It goes into the shell code exactly as
written, which is what makes it the answer for a case this cannot work out --
a wrapper of your own, an interpreter that has to be reached in some particular
way, or a shell whose quoting is not the quoting used here.

"""

import os
import sys

# The name an installed copy is reached by, and the answer whenever there is no
# reason to think otherwise.
ENTRY_POINT = 'thebleep'

OVERRIDE_ENV = 'THEBLEEP_COMMAND'


def _started_from_the_package():
    """Whether this process was started as the package rather than the command.

    `python -m thebleep` and a path to `__main__.py` both put that file in
    `sys.argv[0]`; the installed entry point puts its own name there. Which one
    was used is the question worth asking, because it is the one the person
    asking has already answered: run it from the clone and the alias runs it
    from the clone, run `thebleep` and the alias says `thebleep`.

    Asking the files instead -- is there a `setup.py` beside the package --
    would take the choice away. An editable install has both, and its entry
    point is on `PATH` precisely so that it can be used.

    It has to be *this* `__main__.py`. Every `python -m anything` puts one in
    `sys.argv[0]`, and the first thing that turned up was the whole test suite,
    run as `python -m pytest`, quietly rewriting every alias it checked.

    """
    argv0 = sys.argv[0]
    if not argv0:
        return False

    return os.path.realpath(argv0) == os.path.realpath(_main_path())


def _main_path():
    """This package's `__main__.py`, the file that can be run by path."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '__main__.py')


def _checkout_root():
    """The checkout this package is part of, or `None` if it is installed.

    A checkout is a package directory with the `setup.py` that packages it
    sitting beside it. A copy in `site-packages` has no such neighbour, and
    `python -m thebleep` against one is an ordinary way to reach an installed
    tool -- so it keeps the ordinary answer.

    """
    package = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(package)
    return root if os.path.isfile(os.path.join(root, 'setup.py')) else None


def override():
    """`THEBLEEP_COMMAND`, or `None`. Used as written, quoting included."""
    return os.environ.get(OVERRIDE_ENV) or None


def parts():
    """The words the alias should run, or `None` for the installed command.

    Words, not shell code: quoting is the shell's own business and each shell
    class has a `quote` that knows its rules. Quoting here with `shlex.quote`
    instead -- as this did at first -- puts POSIX single quotes into PowerShell,
    where `'a'"'"'b'` is three arguments rather than one, and into a tcsh alias
    body, which is itself single-quoted and simply ends early.

    """
    if not _started_from_the_package():
        return None

    root = _checkout_root()
    if root is None or not sys.executable:
        return None

    # `-m thebleep` would need the checkout on `sys.path`, which means an
    # environment variable in front of the command and a cwd that cannot be
    # relied on. The file answers to a plain path instead: `__main__.py` puts
    # its own checkout on `sys.path` when it is run that way.
    main = _main_path()
    if not os.path.isfile(main):
        return None

    return [sys.executable, main]


def command():
    """The shell code the alias should run, quoted for POSIX shells.

    Kept for a shell that has no opinion of its own; `Generic._invocation`
    quotes with the shell's own `quote` and is what the aliases use.

    """
    from shlex import quote

    return override() or ' '.join(quote(word) for word in parts() or
                                  [ENTRY_POINT])
