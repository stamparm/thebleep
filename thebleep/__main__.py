"""`python -m thebleep`, which runs exactly what the `thebleep` command runs.

Worth having on its own -- it is how you reach a tool installed into an
environment whose `Scripts` or `bin` directory is not on `PATH` -- and it
matters most on Windows. There the installed `thebleep.exe` is a launcher stub
that starts a second process to do the work, and starting a process is the
dearest thing that platform does -- an interpreter takes several times longer to
start there than on Linux, and the stub pays it twice. This reaches the same
entry point without the stub.

A path to this file runs too, and has to: it is what the alias of a clone names,
so that working on a checkout needs no install at all. Run that way there is no
package to be relative to, so the checkout goes on `sys.path` first and the
import is an ordinary one.

"""

if __package__:
    from .entrypoints.main import main
else:
    import os
    import sys

    # Running a file puts *that file's own directory* on `sys.path`, and here
    # that is the package directory -- so `thebleep/types.py` answers for the
    # standard library's `types`, and the next thing to want `enum`, `re` or
    # `pathlib` dies on an import that has nothing to do with any of them. It
    # has to come off, not merely be outranked by the checkout.
    #
    # Whether it bites at all depends on which modules the interpreter had
    # already imported by the time we get here, which is why this looked fine on
    # one machine and failed on the next.
    _package = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [entry for entry in sys.path
                   if os.path.abspath(entry or os.curdir) != _package]
    sys.path.insert(0, os.path.dirname(_package))
    from thebleep.entrypoints.main import main

if __name__ == '__main__':
    main()
