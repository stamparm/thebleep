#!/usr/bin/env python

"""Publishes a release: build, check, tag, push, upload.

Usage: ./release.py 4.0.1

The version is given rather than guessed. The old script incremented the minor
part of a two-part version, which silently dropped the patch part of anything
three-part, and it tagged and pushed before finding out whether the artifacts
were any good.

"""

import io
import re
import subprocess
import sys


def run(*command):
    print('$ %s' % ' '.join(command))
    subprocess.check_call(command)


def set_version(version):
    with io.open('setup.py', encoding='utf-8') as handle:
        source = handle.read()

    replaced, count = re.subn(r"(?m)^VERSION = '[^']+'$",
                              "VERSION = '%s'" % version, source)
    if count != 1:
        sys.exit('release.py: found %d VERSION lines in setup.py, wanted 1'
                 % count)

    with io.open('setup.py', 'w', encoding='utf-8') as handle:
        handle.write(replaced)


def main(argv):
    if len(argv) != 2 or not re.match(r'^\d+\.\d+(\.\d+)?$', argv[1]):
        sys.exit(__doc__.strip())
    version = argv[1]

    # Everything that can fail without anybody noticing goes first.
    run('git', 'pull')
    set_version(version)
    run('python', '-m', 'flake8')
    run('python', '-m', 'pytest', '-q')
    run('rm', '-rf', 'dist')
    run('python', '-m', 'build')
    run('python', '-m', 'twine', 'check', '--strict', 'dist/*')

    # Then the parts that are public and hard to take back.
    run('git', 'commit', '-am', 'Bump to %s' % version)
    run('git', 'tag', version)
    run('git', 'push')
    run('git', 'push', '--tags')
    run('python', '-m', 'twine', 'upload', 'dist/*')

    print('\nthebleep %s is out.' % version)


if __name__ == '__main__':
    main(sys.argv)
