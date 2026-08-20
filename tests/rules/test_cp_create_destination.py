# -*- encoding: utf-8 -*-

"""Making the destination directory before copying into it.

Every fixture here was printed by a real `cp` or `mv` -- GNU coreutils 9.x and
busybox 1.37. The ones this replaces were not, and both of them were wrong in a
way that mattered:

- `cp: directory foo does not exist` is printed by no `cp` anybody could find.
  GNU reports errno (`No such file or directory`, or `Not a directory` for a
  trailing slash) and busybox says `can't create`.
- a fixture of the bare string `No such file or directory`, with no path in it,
  let the rule be written to take the destination from the end of the command
  line instead of from the message -- which is how `cp a.txt dir/a.txt` came to
  suggest `mkdir -p dir/a.txt`, making a *directory* named after the file.

"""

import pytest
from thebleep.rules.cp_create_destination import match, get_new_command
from thebleep.types import Command

# The destination is what is missing. This is the rule's case.
GNU_CP = ("cp: cannot create regular file '{}': "
          'No such file or directory\n')
GNU_CP_DIR = "cp: cannot create directory '{}': No such file or directory\n"
GNU_MV = "mv: cannot move '{}' to '{}': No such file or directory\n"
BUSYBOX_CP = "cp: can't create '{}': No such file or directory\n"

# The *source* is what is missing, so there is nothing to make and the copy
# would fail again. Firing here left a directory named after the destination.
GNU_STAT = "cp: cannot stat '{}': No such file or directory\n"
BUSYBOX_STAT = "cp: can't stat '{}': No such file or directory\n"
# busybox `mv` prints this whether the source or the destination is missing,
# so it cannot be told apart and is not acted on.
BUSYBOX_MV = "mv: can't rename '{}': No such file or directory\n"


class TestTheDestinationIsMissing(object):
    @pytest.mark.parametrize('script, output', [
        ('cp a.txt nodir/a.txt', GNU_CP.format('nodir/a.txt')),
        ('cp -r adir nodir/adir', GNU_CP_DIR.format('nodir/adir')),
        ('mv a.txt nodir/a.txt', GNU_MV.format('a.txt', 'nodir/a.txt')),
        ('cp a.txt nodir/a.txt', BUSYBOX_CP.format('nodir/a.txt')),
    ])
    def test_it_matches(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output, expected', [
        ('cp a.txt nodir/a.txt', GNU_CP.format('nodir/a.txt'),
         'mkdir -p nodir && cp a.txt nodir/a.txt'),
        ('cp a.txt deep/er/still/a.txt',
         GNU_CP.format('deep/er/still/a.txt'),
         'mkdir -p deep/er/still && cp a.txt deep/er/still/a.txt'),
        ('mv a.txt nodir/a.txt', GNU_MV.format('a.txt', 'nodir/a.txt'),
         'mkdir -p nodir && mv a.txt nodir/a.txt'),
        ('cp a.txt nodir/a.txt', BUSYBOX_CP.format('nodir/a.txt'),
         'mkdir -p nodir && cp a.txt nodir/a.txt'),
    ])
    def test_it_makes_the_directory_holding_the_destination(
            self, script, output, expected):
        """Not the destination itself, which is a file.

        `mkdir -p nodir/a.txt && cp a.txt nodir/a.txt` exits 0 and leaves a
        directory called `a.txt` with the file inside it, so nothing tells you
        it went wrong.

        """
        assert get_new_command(Command(script, output)) == expected

    def test_a_destination_that_is_itself_a_directory(self):
        command = Command('cp a.txt nodir/', GNU_CP.format('nodir/'))
        assert get_new_command(command) == 'mkdir -p nodir && cp a.txt nodir/'


class TestNotTheDestination(object):
    @pytest.mark.parametrize('script, output', [
        # The source does not exist. Nothing to make.
        ('cp typoo.txt b.txt', GNU_STAT.format('typoo.txt')),
        ('mv typoo.txt b.txt', GNU_STAT.format('typoo.txt')),
        ('cp typoo.txt b.txt', BUSYBOX_STAT.format('typoo.txt')),
        # busybox `mv` says the same thing either way, so it cannot be read.
        ('mv a.txt nodir/a.txt', BUSYBOX_MV.format('a.txt')),
        # GNU's trailing-slash message, which `cp x realfile/` also prints --
        # and `mkdir -p realfile` would fail.
        ('cp a.txt nodir/',
         "cp: cannot create regular file 'nodir/': Not a directory\n"),
        # Nothing printed at all.
        ('cp a.txt b.txt', ''),
        ('mv a.txt b.txt', ''),
    ])
    def test_it_does_not_match(self, script, output):
        assert not match(Command(script, output))

    def test_somebody_elses_command(self):
        assert not match(Command('ls nodir', GNU_STAT.format('nodir')))
