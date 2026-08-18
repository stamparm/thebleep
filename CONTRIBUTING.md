# Report issues
If you have any issue with The Bleep, sorry about that, but we will do what we
can to fix that. Actually, maybe we already have, so first thing to do is to
update The Bleep and see if the bug is still there.

If it is (sorry again), check if the problem has not already been reported and
if not, just open an issue on [GitHub](https://github.com/stamparm/thebleep) with
the following basic information:
  - the output of `thebleep --version` (something like `The Bleep 4.0.0 using
    Python 3.12.3 and Bash 5.2.21(1)-release`);
  - your shell and its version (`bash`, `zsh`, *Windows PowerShell*, etc.);
  - your system (Debian 7, ArchLinux, Windows, etc.);
  - how to reproduce the bug;
  - the output of The Bleep with `THEBLEEP_DEBUG=true` exported (typically execute
    `export THEBLEEP_DEBUG=true` in your shell before The Bleep);
  - if the bug only appears with a specific application, the output of that
    application and its version;
  - anything else you think is relevant.

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

`release.py` prepares and checks a release. It does not publish one.

```bash
./release.py 4.0.1
```

That writes the version into `setup.py`, the README badge and the CHANGELOG
heading, runs the gates, builds both artifacts, checks their metadata and
contents, installs the wheel into a clean virtualenv and corrects a command with
it. Then it prints the two git commands to run.

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
