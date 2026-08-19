"""`python -m thebleep`, which runs exactly what the `thebleep` command runs.

Worth having on its own -- it is how you reach a tool installed into an
environment whose `Scripts` or `bin` directory is not on `PATH` -- and it
matters most on Windows. There the installed `thebleep.exe` is a launcher stub
that starts a second process to do the work, and starting a process is the
dearest thing that platform does -- an interpreter takes several times longer to
start there than on Linux, and the stub pays it twice. This reaches the same
entry point without the stub.

"""

from .entrypoints.main import main

if __name__ == '__main__':
    main()
