# Report issues
If you have any issue with The Bleep, sorry about that, but we will do what we
can to fix that. Actually, maybe we already have, so first thing to do is to
update The Bleep and see if the bug is still there.

If it is (sorry again), check if the problem has not already been reported and
if not, just open an issue on [GitHub](https://github.com/stamparm/thebleep) with:

  - **the output of `thebleep --doctor`.** That is the version, the Python, the
    system, the shell and how it was worked out, where the alias is, which copy
    of `thebleep` your shell is finding, and whether the settings file loads —
    which is nearly always where the answer turns out to be. It is built to be
    pasted: it reports that a setting is set and never what it is set to, names
    nothing out of your environment but the handful of variables The Bleep itself
    defines, and folds your home directory back to `~`;
  - how to reproduce it: the command you typed, and what you expected instead;
  - if it is about a specific tool, what that tool printed and its version.

Two more, only when the above has not explained it:

  - the output with `THEBLEEP_DEBUG=true` exported;
  - if the bug only shows up with one of your own rules, that rule.

**Read what you are about to paste.** A failed command's output is the thing
being corrected from, so it is the thing an issue tends to end up containing —
and it can hold a host name, a path inside your employer, a repository URL or a
token a tool printed at you. Redact it. Debug output is longer and worth the same
second look. Do not paste your environment.

It's only with enough information that we can do something to fix the problem.

# Make a pull request
We gladly accept pull request on the [official
repository](https://github.com/stamparm/thebleep) for new rules, new features, bug
fixes, etc.

# Developing

In order to develop locally, there are two options:

- Develop using a local installation of Python 3 and setting up a virtual environment
- Develop using an automated VSCode Dev Container.

## Develop using local Python installation

[Create and activate a Python 3 virtual environment.](https://docs.python.org/3/tutorial/venv.html)

Install `The Bleep` for development:

```bash
pip install -r requirements.txt
pip install -e .
```

Run code style checks:

```bash
flake8
```

## Use the clone you are working on

Testing a change by hand means your shell has to run *this* checkout, and by
default it does not: `thebleep --alias` writes an alias that says `thebleep`,
which is whatever is on your `PATH`. If that is a release you installed once,
you will be developing one version and being corrected by another, and nothing
will tell you.

Run it as the package instead, and the alias names the clone:

```bash
eval "$(python3 /path/to/thebleep/thebleep/__main__.py --alias-loader)"
```

The interpreter you name there needs the two runtime dependencies —
`pip install psutil pyte`, or point the line at the virtual environment you
already installed them into. `requirements.txt` is the *development* set and does
not include them; `pip install -e .` is what normally brings them in.

Put that in your startup file and the clone is your *The Bleep* for good — no
install, and `git pull` is the whole upgrade. `THEBLEEP_COMMAND` overrides what
goes into the alias if you need something else in there.

If you would rather have `thebleep` on your `PATH` for real, `sh install.sh
--dev` installs the clone editable with whichever of `uv`, `pipx` or `pip` you
have. Either way, `thebleep --doctor` says which copy is answering — check it
after setting this up, and again whenever a correction behaves like an older
version, because that is usually exactly what has happened.

Run unit tests:

```bash
pytest
```

Run unit and functional tests (requires docker):

```bash
pytest --enable-functional
```

Redraw the README's demo, and rewrite its benchmark chart from the committed
benchmark run (do the second after recording a new one):

```bash
python assets/make_demo.py
python bench/chart.py
```

`python assets/make_demo.py /tmp/at.svg --at 3000` writes the demo frozen three
seconds into its animation, which is how to look at a single frame of it.

## Everything CI checks, in one command

```bash
flake8 && pytest -q && python bench/chart.py --check
```

Add `--enable-functional` to `pytest` for the tests that drive real shells and
a real PowerShell in docker. `pytest tests/test_rulepack_equivalence.py` is the
slow one and the one worth keeping: it proves the rule cache cannot change which
corrections exist.

`pytest -q -m "not slow"` skips the three suites that take tens of seconds — the
rule pack's equivalence corpus, the large-output sweep and the structural rule
checks — which takes the suite from about 46 seconds to about 10. That is for a
quick local loop only: CI runs everything on every Python version and every
operating system, because the pack marshals code objects and the structural
checks walk the syntax tree, and both of those differ between interpreters.

## Releasing

`release.py` prepares and checks a release. It does not publish one. It needs an
environment with the development requirements in it, and it will not make you
one: the first time, do this, from the root of the checkout.

```bash
python3 -m venv ~/.cache/thebleep/release-venv
~/.cache/thebleep/release-venv/bin/python -m pip install -U pip
~/.cache/thebleep/release-venv/bin/python -m pip install -r requirements.txt -e .
~/.cache/thebleep/release-venv/bin/python ./release.py 4.0.1
```

For the releases after that, the same environment is fine — refresh what is in it
first, in case the requirements have moved:

```bash
~/.cache/thebleep/release-venv/bin/python -m pip install -r requirements.txt -e .
~/.cache/thebleep/release-venv/bin/python ./release.py 4.0.2
```

It sits outside the checkout on purpose. A virtualenv in the working tree is
somebody else's Python inside your project: git has to be told to ignore it,
flake8 has to be told not to lint it, and `release.py` refuses to release past
anything it was not told about. Put it wherever you like with
`THEBLEEP_RELEASE_VENV`, and the recipe follows:

```bash
export THEBLEEP_RELEASE_VENV=~/Temp/thebleep-release-venv
```

Running `release.py` with an interpreter that cannot do the job stops before
writing anything and prints that recipe back at you, with the version and that
path filled in.

What it does, in order: checks this interpreter is Python 3.9 or newer and has
`flake8`, `pytest`, `build`, `twine` and The Bleep's own dependencies; checks the
tree is clean, on master, and that the tag is free; runs flake8 and the suite
**against the tree as it stands**; then writes the version into `setup.py`, the
README badge and the CHANGELOG heading; builds both artifacts, checks their
metadata and contents, installs the wheel into a clean virtualenv and corrects a
command with it. Then it prints the two git commands to run.

Nothing is written until every check that can be made against the unreleased tree
has passed, and if a later step fails those three files are put back — so an
attempt that did not finish leaves `git status` clean.

Pushing the version tag is what publishes. `.github/workflows/release.yml` builds
the artifacts again from the tag, checks that the tag, `setup.py`, the CHANGELOG
and the README badge agree, installs the wheel on Linux, macOS and Windows, and
uploads those exact files to PyPI through [trusted
publishing](https://docs.pypi.org/trusted-publishers/) — no API token exists.
Running that workflow by hand publishes to TestPyPI instead, which is how to
rehearse it; a manual run has no way to reach PyPI.

## Develop using Dev Container

A [dev container](https://containers.dev/) is included: Python 3.12, the shells
the functional tests drive, docker-in-docker for the ones that need it, and The
Bleep installed for development. No local Python setup required.

### Prerequisites

To use the container you require:
- [Docker](https://www.docker.com/products/docker-desktop)
- [VSCode](https://code.visualstudio.com/)
- [VSCode Remote Development Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack)
- [Windows Users Only]: [Installation of WSL2 and configuration of Docker to use it](https://docs.docker.com/docker-for-windows/wsl/)

Full notes about [installation are here](https://code.visualstudio.com/docs/remote/containers#_installation)

### Running the container

Assuming you have the prerequisites:

1. Open VSCode
1. Open command palette (CMD+SHIFT+P (mac) or CTRL+SHIFT+P (windows))
1. Select `Remote-Containers: Reopen in Container`.
1. Container will be built, install all pip requirements and your VSCode will mount into it automagically.
1. Your VSCode and container now essentially become a throw away environment.
