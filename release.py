#!/usr/bin/env python

"""Prepares a release and checks it. It does not publish one.

Usage: ./release.py 4.0.1

What it does: writes the version into the three places that say it, runs the
gates, builds both artifacts, checks their metadata and contents, installs the
wheel into a clean virtualenv and corrects a command with it. Then it stops and
prints the two git commands that make the release happen.

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


def set_version(version, date):
    """Puts the version in every file that states it."""
    for path, pattern, replacement in STATES_THE_VERSION:
        text = read(path)
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
    if len(argv) != 2 or not re.match(r'^\d+\.\d+(\.\d+)?$', argv[1]):
        sys.exit(__doc__.strip())
    version = argv[1]
    date = today()

    check_working_tree()
    check_tag_is_free(version)

    print('\n== version ==')
    set_version(version, date)

    print('\n== gates ==')
    run(sys.executable, '-m', 'flake8')
    run(sys.executable, '-m', 'pytest', '-q')

    print('\n== build ==')
    shutil.rmtree(os.path.join(HERE, 'dist'), ignore_errors=True)
    run(sys.executable, '-m', 'build')
    run(sys.executable, '-m', 'twine', 'check', '--strict',
        os.path.join(HERE, 'dist', '*'))

    print('\n== artifacts ==')
    check_artifacts(version)

    print('\n== installed copy ==')
    smoke_test(version)

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
