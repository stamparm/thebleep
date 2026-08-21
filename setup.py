#!/usr/bin/env python
from setuptools import setup, find_packages
import io
import os
import re
import sys


version = sys.version_info[:2]
if version < (3, 9):
    print('thebleep requires Python version 3.9 or later' +
          ' ({}.{} detected).'.format(*version))
    sys.exit(-1)

VERSION = '4.0.4'

REPOSITORY = 'https://github.com/stamparm/thebleep'
IMAGES = ('.svg', '.png', '.gif', '.jpg', '.jpeg')


def for_pypi(markdown):
    """Points the README's relative links at the repository.

    They are relative so that they work on GitHub from any branch, fork or
    checkout -- including a private one, where raw.githubusercontent.com
    serves nothing at all. PyPI has no repository to resolve them against, so
    for the page there they are made absolute, and pinned to this release's
    tag rather than to master, so that a release's page keeps showing what that
    release said.

    Markdown has two ways to write a link and this used to know about one of
    them. `[text](target)` was rewritten; a reference definition at the foot of
    the file, `[name]: target`, was not -- so the first badge on the PyPI page,
    whose `[version-link]` resolves to `CHANGELOG.md`, was a dead relative link
    on a page with nothing to resolve it against.

    """
    blob = '%s/blob/%s/' % (REPOSITORY, VERSION)
    raw = 'https://raw.githubusercontent.com/stamparm/thebleep/%s/' % VERSION

    def resolved(target):
        """`target` as it has to be written for a page outside the repository.

        An anchor stays an anchor -- PyPI renders the headings, so `#settings`
        still goes to the right place -- and anything already absolute is left
        exactly as it is.

        """
        if target.startswith(('http:', 'https:', 'mailto:', '#')):
            return None
        return (raw if target.endswith(IMAGES) else blob) + target

    def inline(match):
        target = resolved(match.group(1))
        return match.group(0) if target is None else '](%s)' % target

    def reference(match):
        target = resolved(match.group(2))
        return match.group(0) if target is None \
            else '%s%s' % (match.group(1), target)

    markdown = re.sub(r'\]\(([^)]+)\)', inline, markdown)
    # A reference definition: `[name]: target` at the start of a line, with the
    # optional title left alone by only taking the first word as the target.
    return re.sub(r'(?m)^(\[[^\]]+\]:\s+)(\S+)$', reference, markdown)


# The CI badge where it is used, and the two reference definitions behind it.
# Both have to go: a definition nobody references renders as nothing, but it is
# still a dead line sitting in the page's source.
CI_BADGE = re.compile(r' *\[!\[Build Status\]\[workflow-badge\]\]'
                      r'\[workflow-link\]')
CI_BADGE_LINKS = re.compile(r'(?m)^\[workflow-(?:badge|link)\]:.*\n')


def without_ci_badge(markdown):
    """Takes the build badge out of the page on PyPI.

    It belongs on GitHub, where it tells a contributor whether master is passing.
    On a release page it is worse than nothing: the badge image is served live
    from the default branch, so every version's PyPI page reads out whatever
    master happens to be doing today. A red master puts "build failing" on the
    page for a release that was green when it was made.

    Pinning it to the tag instead was the other option and it is not better --
    `?branch=4.0.2` on a branch that does not exist renders as an error. The
    honest answer is that somebody deciding whether to `pip install` this is not
    asking about our branch, so they are not shown a claim about it.

    """
    return CI_BADGE_LINKS.sub('', CI_BADGE.sub('', markdown, count=1))


# The README is the PyPI page. Read with an explicit encoding: it has em dashes
# and arrow keys in it, and a build on a machine whose default encoding is not
# UTF-8 would fail on them.
here = os.path.dirname(os.path.abspath(__file__))
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as readme:
    long_description = without_ci_badge(for_pypi(readme.read()))

# What the package needs at run time.
#
# `decorator` is gone: `utils.decorator` is four lines of our own and nothing
# imports the package any more. `colorama` is Windows-only: `logs` spells out the
# handful of escape codes it uses, and only `system.win32` needs the real thing,
# to install a console handler. `win_unicode_console` is gone as well -- CPython
# has spoken Unicode to the Windows console natively since 3.6 (PEP 528 and 529)
# and this package requires 3.9.
#
# The floors are versions the test suite has actually been run against, not
# guesses; see the minimum-dependencies job in .github/workflows/test.yml.
install_requires = ['psutil>=5.9.0', 'pyte>=0.8.0']
extras_require = {":sys_platform=='win32'": ['colorama>=0.4.6']}

# One wheel, the same everywhere.
#
# These used to be chosen by `sys.platform` while the package was being *built*,
# which decides nothing useful: a pure-Python wheel is `py3-none-any` and is
# installed on Windows without setup.py running again. So the wheel PyPI serves
# to a Windows user had the POSIX entry points in it and none of the Windows
# ones, whichever machine happened to build it.
#
# What went with the branch was `scripts/bleep.bat` and `scripts/bleep.ps1`.
# `bleep.bat` drove a correction loop for cmd.exe, which is not one of the shells
# this supports and which nothing tested; and under PATHEXT a `bleep.exe` from
# the entry point below is found before a `bleep.bat` anyway, so it could not
# have run. `bleep.ps1` printed first-use instructions, which is what
# `not_configured` does, while writing an obsolete PYTHONIOENCODING line into
# the user's $PROFILE.
#
# On Windows `bleep` becomes `bleep.exe`, and PowerShell resolves a function
# before an external command, so the alias shadows it once configured -- and
# before that it is exactly the first-use message it should be.
entry_points = {'console_scripts': [
    'thebleep = thebleep.entrypoints.main:main',
    'bleep = thebleep.entrypoints.not_configured:main']}

setup(name='thebleep',
      version=VERSION,
      description='Corrects your previous console command. The maintained'
                  ' successor to The Fuck.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Miroslav Stampar',
      author_email='miroslav.stampar@gmail.com',
      url='https://github.com/stamparm/thebleep',
      project_urls={
          'Source': 'https://github.com/stamparm/thebleep',
          'Issues': 'https://github.com/stamparm/thebleep/issues',
          'Changelog':
              'https://github.com/stamparm/thebleep/blob/master/CHANGELOG.md',
      },
      license='MIT',
      keywords='shell console command correction typo cli productivity',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'Operating System :: MacOS',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: 3.12',
          'Programming Language :: Python :: 3.13',
          'Programming Language :: Python :: 3.14',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Software Development',
          'Topic :: Terminals',
          'Topic :: Utilities',
      ],
      packages=find_packages(exclude=['ez_setup', 'examples',
                                      'tests', 'tests.*', 'release']),
      include_package_data=True,
      zip_safe=False,
      python_requires='>=3.9',
      install_requires=install_requires,
      extras_require=extras_require,
      entry_points=entry_points)
