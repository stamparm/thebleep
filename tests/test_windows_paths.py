# -*- coding: utf-8 -*-

"""A Windows path, pushed through every seam a correction passes through.

Four CI failures in a row, all Windows-only, all in one rule -- and three of
the four were nothing Windows-specific at all. `shlex` eating backslashes,
`re.sub` reading `\\U` as a backreference, `shlex.quote` wrapping anything
with a backslash in quotes: every one of those behaves identically here. The
only thing Windows contributed was the *input* -- paths with backslashes in
them -- and the only reason the bugs shipped is that no test on this side ever
supplied one.

So this module supplies one. The filesystem is faked over `PureWindowsPath`,
which builds and joins `C:\\...` paths on any OS; what cannot be faked this
way (a real `WindowsPath` with a real drive) is exactly the part that was
never broken.

"""

import pytest

from pathlib import PureWindowsPath

from thebleep.rules import path_correction
from thebleep.types import Command
from thebleep.utils import replace_argument


# What exists on the pretend drive: path -> 'dir' or 'file'. Filled by the
# fixture; keyed by the backslashed string form `str(PureWindowsPath)` gives.
FILESYSTEM = {}


class WindowsishPath(PureWindowsPath):
    """A `C:\\...` path that answers the three questions the walk asks."""

    def exists(self):
        return str(self) in FILESYSTEM

    def is_dir(self):
        return FILESYSTEM.get(str(self)) == 'dir'

    def iterdir(self):
        for path in FILESYSTEM:
            child = WindowsishPath(path)
            if child != self and child.parent == self:
                yield child


@pytest.fixture
def c_drive(monkeypatch):
    """`C:\\Users\\you\\etc\\passwd`, and a rule that sees Windows paths.

    Faked at the rule's two entry points for paths -- `Path` and `expanduser`
    -- rather than by setting `os.name`, for the same reason
    `test_windows_names` does not: the rest of the interpreter is not under
    test, and `pathlib` here cannot build a concrete `WindowsPath`.

    """
    FILESYSTEM.clear()
    FILESYSTEM.update({
        'C:\\Users': 'dir',
        'C:\\Users\\you': 'dir',
        'C:\\Users\\you\\etc': 'dir',
        'C:\\Users\\you\\etc\\passwd': 'file',
    })
    monkeypatch.setattr(path_correction, 'Path', WindowsishPath)
    monkeypatch.setattr(path_correction, 'expanduser', WindowsishPath)


@pytest.mark.usefixtures('no_memoize', 'c_drive')
def test_a_windows_path_comes_back_corrected_and_unmangled():
    """The whole pipeline, backslashes in, backslashes out.

    This is the test the four CI failures were, replayed at home: the
    absolute-path gate has to recognise a drive letter, the argument has to
    be taken from the script with its separators intact, the corrected path
    has to survive `replace_argument`, and nothing may quote it on the way
    out.

    """
    broken = 'C:\\Users\\you\\ec\\passwd'
    command = Command('cat {}'.format(broken),
                      'cat: {}: No such file or directory'.format(broken))

    assert path_correction.match(command)
    assert path_correction.get_new_command(command) == \
        'cat C:\\Users\\you\\etc\\passwd'


@pytest.mark.usefixtures('no_memoize', 'c_drive')
def test_a_windows_path_with_nothing_to_fix_stays_silent():
    fine = 'C:\\Users\\you\\etc\\passwd'
    command = Command('cat {}'.format(fine),
                      'cat: {}: Permission denied'.format(fine))

    assert not path_correction.match(command)


def test_replace_argument_takes_a_windows_path_verbatim():
    """The seam every path-fixing rule shares.

    `re.sub` reads its replacement string for backreferences, so `\\U` --
    the opening of most Windows user paths -- used to raise `re.error: bad
    escape` out of any rule that put one through here. In both positions,
    because the two are different code paths: at the end of the script and in
    the middle of it.

    """
    assert replace_argument('cat C:\\old', 'C:\\old', 'C:\\Users\\new') == \
        'cat C:\\Users\\new'
    assert replace_argument('cat C:\\old --number', 'C:\\old',
                            'C:\\Users\\new') == 'cat C:\\Users\\new --number'
