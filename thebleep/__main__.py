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

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from thebleep.entrypoints.main import main

if __name__ == '__main__':
    main()
