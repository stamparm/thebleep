#!/usr/bin/env python3

"""Prepares a release and checks it. It does not publish one.

Usage: ./release.py 4.0.1

Needs an environment with the development requirements in it, and will not make
you one -- run it with the wrong interpreter and it says how, before writing
anything. That environment lives outside the checkout, at
`~/.cache/thebleep/release-venv` unless `THEBLEEP_RELEASE_VENV` says otherwise.

What it does: checks that this interpreter can do the job at all, runs the gates
against the tree as it stands, writes the version into the three places that say
it, builds both artifacts, checks their metadata and contents, installs the wheel
into a clean virtualenv and corrects a command with it. Then it stops and prints
the two git commands that make the release happen.

The order matters. Nothing is written until every check that can be made against
the unreleased tree has passed, and if a later step fails the three files are put
back -- so a release attempt that did not finish leaves `git status` clean and
there is nothing to remember to undo.

What it deliberately does not do is commit, tag, push or upload. Publishing runs
in CI, from the tag, over PyPI's trusted publishing -- see
.github/workflows/release.yml. That is one place with the authority to publish,
using no long-lived token, building the artifacts once and publishing those exact
files. A script on a laptop that pulls, commits, tags, pushes and uploads in one
go is a lot of irreversible authority to hand to a typo.

"""

import datetime
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Every file that states the version, and the line in it that does.
STATES_THE_VERSION = (
    ('setup.py', re.compile(r"(?m)^VERSION = '[^']+'$"),
     "VERSION = '{version}'"),
    ('README.md',
     re.compile(r'(?m)^(\[version-badge\]:\s+\S+/badge/version-)[\d.]+(-)'),
     None),
    ('CHANGELOG.md', re.compile(r'(?m)^## \S+ — .+$'),
     u'## {version} — {date}'),
)


def run(*command, **kwargs):
    print('$ %s' % ' '.join(command))
    subprocess.check_call(command, **kwargs)


def output(*command):
    return subprocess.check_output(command).decode('utf-8').strip()


def read(path):
    with io.open(os.path.join(HERE, path), encoding='utf-8') as handle:
        return handle.read()


def write(path, text):
    with io.open(os.path.join(HERE, path), 'w', encoding='utf-8') as handle:
        handle.write(text)


def today():
    """The date the release is being prepared, as the CHANGELOG writes it.

    This was `git log -1 --format=%cs`, which is the date of the last *commit* --
    so a release prepared on Tuesday from a tree last touched on Friday was dated
    Friday, and the CHANGELOG said a day the release did not happen on.

    Local time on purpose. A release is prepared by a person in a place, the
    CHANGELOG is read by people in other places, and there is no reading of
    "released on the 3rd" precise enough for UTC to be the more correct answer.

    """
    return datetime.date.today().isoformat()


def check_next_section_is_open(pattern, text, version='<next>'):
    """The CHANGELOG heading about to be relabelled must be the *next*
    release's.

    This script rewrites the *first* `## x — y` heading, which is only the next
    release when a section for it has been opened. With none open, the first
    heading belongs to the release that already shipped -- which is how a run of
    this script once put a new version and today's date on the previous
    release's security notes, caught afterwards by luck. Refusing costs one
    line in the CHANGELOG; relabelling history costs a rewrite of it.

    """
    found = pattern.search(text)
    if found is None or 'unreleased' not in found.group(0).lower():
        sys.exit("release.py: CHANGELOG.md's first heading is not the "
                 "unreleased section. Open one -- `## {} — unreleased` -- so "
                 "this relabels the release to come instead of the one that "
                 "already shipped.".format(version))


def set_version(version, date):
    """Puts the version in every file that states it."""
    # Read first, check first, write last: the guard below has to fire before
    # any file has been rewritten, not after setup.py already says a version
    # the CHANGELOG refuses to take.
    texts = {path: read(path) for path, _, _ in STATES_THE_VERSION}
    for path, pattern, _ in STATES_THE_VERSION:
        if path == 'CHANGELOG.md':
            check_next_section_is_open(pattern, texts[path], version)

    for path, pattern, replacement in STATES_THE_VERSION:
        text = texts[path]
        if replacement is None:
            # The badge, whose version sits in the middle of a URL.
            new, count = pattern.subn(r'\g<1>%s\g<2>' % version, text)
        else:
            new, count = pattern.subn(
                replacement.format(version=version, date=date), text, count=1)
        if count != 1:
            sys.exit('release.py: {} has {} lines stating the version, '
                     'wanted 1'.format(path, count))
        write(path, new)
        print('  {} says {}'.format(path, version))


MINIMUM_PYTHON = (3, 9)

# What this script runs, and what it needs to be there to run it. Checked by
# whether the module can be found rather than by importing it: `python -m pytest`
# is how each of these is invoked, and finding it is the same question, without
# executing anybody's `__init__`.
NEEDS = (
    ('flake8', 'the style gate'),
    ('pytest', 'the test suite'),
    ('build', 'building the wheel and the sdist'),
    ('twine', 'checking the built metadata'),
    ('psutil', 'the suite, which imports The Bleep'),
    ('pyte', 'the suite, which imports The Bleep'),
    ('thebleep', 'the suite; `pip install -e .` puts it here'),
)


# Where the release environment goes, and it is not in the checkout. A
# virtualenv in the working tree is somebody else's Python sitting in your
# project: `git status` has to be told to ignore it, flake8 has to be told not to
# lint it, and `check_working_tree` below refuses to release past anything it was
# not told about. It is a build tool rather than part of the project, so it lives
# where build tools live.
#
# `~` and not the expanded path: this string is printed for somebody to paste
# into a shell, and the shell is what expands it.
DEFAULT_VENV = '~/.cache/thebleep/release-venv'

# Where a virtualenv keeps its interpreter, which is not the same on both. The
# POSIX one is what CONTRIBUTING documents, because a document has to pick one.
POSIX_VENV_PYTHON = DEFAULT_VENV + '/bin/python'


def release_venv():
    """Asked each time rather than read once while this was being imported.

    A module-level `os.environ.get` is a value frozen at import, which is both
    surprising to change and awkward to test.

    """
    return os.environ.get('THEBLEEP_RELEASE_VENV') or DEFAULT_VENV


def venv_python(venv=None):
    return '{}/{}/python'.format(venv or release_venv(),
                                 'Scripts' if os.name == 'nt' else 'bin')


def bootstrap(version='<version>', python=None):
    """The one recipe, for an interpreter that cannot do this.

    Printed rather than run. Creating a virtualenv and installing into it is a
    decision about somebody's machine, and a release script is the last place to
    be making those on their behalf.

    `python` is which interpreter path to write into it, and it exists so that
    the test which holds CONTRIBUTING to this recipe can ask for the POSIX
    spelling on any platform. Left alone it is this platform's, at `VENV`.

    Forward slashes even on Windows: every line here is for a shell, and both
    cmd and PowerShell take `/` in a path. `os.path.join` would put a backslash
    in a line somebody is about to paste.

    """
    if python is None:
        python = venv_python()
    return ('    python3 -m venv {venv}\n'
            '    {python} -m pip install -U pip\n'
            '    {python} -m pip install -r requirements.txt -e .\n'
            '    {python} ./release.py {version}\n'.format(
                venv=release_venv(), python=python,
                version=version))


def check_python(version='<version>'):
    if sys.version_info[:2] < MINIMUM_PYTHON:
        sys.exit('release.py: needs Python {}.{} or newer; this is {}.\n\n{}'
                 .format(MINIMUM_PYTHON[0], MINIMUM_PYTHON[1],
                         '.'.join(str(part) for part in sys.version_info[:3]),
                         bootstrap(version)))


def check_dependencies(version='<version>'):
    """Everything the gates need, before anything has been written.

    This used to be found out one gate at a time, after the version had already
    been written into three files -- so an interpreter without pytest left a
    half-prepared release behind and a `git checkout` to work out.

    """
    import importlib.util

    missing = []
    for name, why in NEEDS:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):                # pragma: no cover
            found = False
        if not found:
            missing.append('{} ({})'.format(name, why))

    if missing:
        sys.exit('release.py: {} cannot prepare a release.\n  missing: {}\n\n'
                 'Make an environment that can, and use it:\n\n{}'
                 .format(sys.executable, '\n           '.join(missing),
                         bootstrap(version)))


def check_working_tree():
    if output('git', 'status', '--porcelain'):
        sys.exit('release.py: the working tree has changes; commit or stash '
                 'them first, so that what gets released is what is committed')
    branch = output('git', 'rev-parse', '--abbrev-ref', 'HEAD')
    if branch != 'master':
        sys.exit('release.py: on {}, not master'.format(branch))


def check_tag_is_free(version):
    tags = output('git', 'tag', '--list', version).split()
    if tags:
        sys.exit('release.py: tag {} already exists'.format(version))


def check_artifacts(version):
    """What is in the wheel, and what its metadata says."""
    wheel = os.path.join(HERE, 'dist',
                         'thebleep-{}-py3-none-any.whl'.format(version))
    sdist = os.path.join(HERE, 'dist', 'thebleep-{}.tar.gz'.format(version))
    for path in (wheel, sdist):
        if not os.path.exists(path):
            sys.exit('release.py: {} was not built'.format(path))

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = archive.read(
            'thebleep-{}.dist-info/METADATA'.format(version)).decode('utf-8')
        entry_points = archive.read(
            'thebleep-{}.dist-info/entry_points.txt'.format(version)
        ).decode('utf-8')

    problems = []
    if 'Version: {}\n'.format(version) not in metadata:
        problems.append('the wheel metadata does not say version {}'
                        .format(version))
    if 'github.com/stamparm/thebleep' not in metadata:
        problems.append('the wheel metadata has no repository URL')
    for wanted in ('thebleep = thebleep.entrypoints.main:main',
                   'bleep = thebleep.entrypoints.not_configured:main'):
        if wanted not in entry_points:
            problems.append('the wheel is missing the entry point {!r}'
                            .format(wanted))
    for unwanted in ('tests/', 'thefuck', '.egg-info/', 'bench/', 'assets/'):
        found = [name for name in names if unwanted in name]
        if found:
            problems.append('the wheel contains {}: {}'
                            .format(unwanted, found[:3]))
    if not any(name.endswith('/rules/git_add.py') for name in names):
        problems.append('the wheel has no rules in it')

    if problems:
        sys.exit('release.py:\n  ' + '\n  '.join(problems))
    print('  wheel: {} files, version and entry points as expected'
          .format(len(names)))


def smoke_test(version):
    """Installs the built wheel somewhere clean and corrects a command."""
    wheel = os.path.join(HERE, 'dist',
                         'thebleep-{}-py3-none-any.whl'.format(version))
    directory = tempfile.mkdtemp(prefix='thebleep-release-')
    try:
        run(sys.executable, '-m', 'venv', os.path.join(directory, 'venv'))
        pip = os.path.join(directory, 'venv', 'bin', 'pip')
        binary = os.path.join(directory, 'venv', 'bin', 'thebleep')
        if not os.path.exists(pip):    # Windows
            pip = os.path.join(directory, 'venv', 'Scripts', 'pip.exe')
            binary = os.path.join(directory, 'venv', 'Scripts', 'thebleep.exe')
        run(pip, 'install', '--quiet', wheel)

        environment = dict(os.environ,
                           TB_SHELL='bash',
                           XDG_CONFIG_HOME=os.path.join(directory, 'config'),
                           XDG_CACHE_HOME=os.path.join(directory, 'cache'))
        reported = subprocess.check_output(
            [binary, '--version'], env=environment,
            stderr=subprocess.STDOUT).decode('utf-8')
        if version not in reported:
            sys.exit('release.py: the installed copy reports {!r}'
                     .format(reported.strip()))

        alias = subprocess.check_output([binary, '--alias'],
                                        env=environment).decode('utf-8')
        if 'thebleep' not in alias:
            sys.exit('release.py: --alias produced nothing usable')

        corrected = subprocess.check_output(
            [binary, '--yes', 'ehco', 'hello'], env=environment).decode('utf-8')
        if 'echo hello' not in corrected:
            sys.exit('release.py: a correction did not come back: {!r}'
                     .format(corrected))
        print('  installed from the wheel, corrected `ehco hello`')
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def main(argv):
    # Every gate and the build run in the current directory; the files are
    # read from HERE. Make the two the same place.
    os.chdir(HERE)
    if len(argv) != 2 or not re.match(r'^\d+\.\d+(\.\d+)?$', argv[1]):
        sys.exit(__doc__.strip())
    version = argv[1]
    date = today()

    print('== can this interpreter do it ==')
    check_python(version)
    check_dependencies(version)
    print('  {}'.format(sys.executable))

    check_working_tree()
    check_tag_is_free(version)

    # Before anything is written, and against the tree as it is committed. A
    # release that is going to fail its own gates should fail without having
    # touched a file.
    print('\n== gates ==')
    run(sys.executable, '-m', 'flake8')
    run(sys.executable, '-m', 'pytest', '-q')

    print('\n== version ==')
    before = {path: read(path) for path, _, _ in STATES_THE_VERSION}
    set_version(version, date)

    try:
        print('\n== build ==')
        shutil.rmtree(os.path.join(HERE, 'dist'), ignore_errors=True)
        run(sys.executable, '-m', 'build')
        run(sys.executable, '-m', 'twine', 'check', '--strict',
            os.path.join(HERE, 'dist', '*'))

        print('\n== artifacts ==')
        check_artifacts(version)

        print('\n== installed copy ==')
        smoke_test(version)
    except BaseException:
        # Put the three files back. Whatever went wrong, the tree is not left
        # saying it is a version that was never released -- there is nothing to
        # notice and nothing to undo, and the next attempt starts from a clean
        # tree the way this one insists on.
        for path, text in before.items():
            write(path, text)
        print('\nrelease.py: that did not finish. {} put back as they were.'
              .format(', '.join(sorted(before))))
        raise

    print("""
Ready. Nothing has been committed, tagged, pushed or published.

    git commit -am 'Release {version}'
    git push
    git tag {version} && git push origin {version}

Pushing the tag is what publishes: .github/workflows/release.yml builds the
artifacts again from it, runs the checks, and uploads to PyPI through trusted
publishing. Rehearse against TestPyPI first by running that workflow by hand --
a manual run goes to TestPyPI and cannot go anywhere else.
""".format(version=version))


if __name__ == '__main__':
    main(sys.argv)
