# -*- coding: utf-8 -*-

"""What the artifact says about itself.

A pure-Python wheel is built once, on one machine, and installed on all of them.
So nothing about it may depend on the platform it was built on -- which is what
`if sys.platform == "win32":` in setup.py did, leaving the wheel PyPI serves to
Windows users carrying the POSIX entry points and none of the Windows ones.

These read setup.py rather than building, so they cost nothing; the build itself
is checked in CI, which inspects both artifacts and installs the wheel.

"""

import io
import re
import pytest


@pytest.fixture
def setup_py(source_root):
    with io.open(str(source_root.joinpath('setup.py')),
                 encoding='utf-8') as handle:
        return handle.read()


def test_nothing_is_decided_by_the_building_platform(setup_py):
    """No `sys.platform` outside the interpreter version check."""
    conditionals = re.findall(r'^\s*(?:el)?if .*sys\.platform.*:$', setup_py,
                              re.MULTILINE)
    assert conditionals == [], conditionals


def test_the_entry_points_are_the_same_everywhere(setup_py):
    assert "'thebleep = thebleep.entrypoints.main:main'" in setup_py
    assert "'bleep = thebleep.entrypoints.not_configured:main'" in setup_py
    # A `scripts=` list is installed as files rather than as generated
    # launchers, and there is nothing left that needs one.
    assert 'scripts=' not in setup_py


def test_the_version_is_written_once(setup_py):
    """`release.py` rewrites this line, so there has to be exactly one."""
    assert len(re.findall(r"^VERSION = '[^']+'$", setup_py, re.MULTILINE)) == 1


def test_every_runtime_dependency_is_imported_somewhere(setup_py, source_root):
    """A dependency nothing imports is a dependency to remove.

    `decorator` was one: `utils.decorator` is four lines of our own.

    """
    declared = re.search(r'^install_requires = \[([^\]]*)\]', setup_py,
                         re.MULTILINE).group(1)
    names = [re.split(r'[<>=!~\s]', name.strip().strip("'\""))[0]
             for name in declared.split(',') if name.strip()]
    assert names, 'no dependencies were found to check'

    sources = []
    for path in source_root.joinpath('thebleep').rglob('*.py'):
        with io.open(str(path), encoding='utf-8') as handle:
            sources.append(handle.read())
    everything = '\n'.join(sources)

    for name in names:
        assert re.search(r'\b(?:import|from)\s+{}\b'.format(re.escape(name)),
                         everything), \
            '{} is required but never imported'.format(name)


def test_windows_only_dependencies_are_marked_as_such(setup_py):
    """colorama is only needed by `system.win32`, to install a console handler.

    `logs` spells out the handful of escape codes it uses rather than importing
    it, so a POSIX install has no reason to carry it.

    """
    windows = re.search(r'^extras_require = \{([^}]*)\}', setup_py,
                        re.MULTILINE).group(1)
    assert "sys_platform=='win32'" in windows
    assert 'colorama' in windows


def test_the_obsolete_dependencies_are_gone(setup_py):
    """Checked against the declarations, not the comments explaining them."""
    declarations = '\n'.join(
        re.findall(r'^(?:install_requires|extras_require) = .*$', setup_py,
                   re.MULTILINE))
    assert declarations
    for gone, why in (
            ('decorator', 'utils.decorator replaced it'),
            ('win_unicode_console',
             'CPython speaks Unicode to the Windows console natively since '
             '3.6, and this requires 3.9')):
        assert gone not in declarations, why
