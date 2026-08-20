import pytest
from thebleep.rules.no_such_file import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('mv foo bar/foo', "mv: cannot move 'foo' to 'bar/foo': No such file or directory"),
    Command('mv foo bar/', "mv: cannot move 'foo' to 'bar/': No such file or directory"),
])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('mv foo bar/', ""),
    Command('mv foo bar/foo', "mv: permission denied"),
])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('mv foo bar/foo', "mv: cannot move 'foo' to 'bar/foo': No such file or directory"), 'mkdir -p bar && mv foo bar/foo'),
    (Command('mv foo bar/', "mv: cannot move 'foo' to 'bar/': No such file or directory"), 'mkdir -p bar && mv foo bar/'),
])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


class TestWhatItUsedToGetWrong(object):
    """This was the weaker copy of `cp_create_destination`, in three ways."""

    def test_a_destination_with_no_directory_in_it(self):
        """`file[0:file.rfind('/')]` on a bare filename is `''`, so this used
        to suggest `mkdir -p  && mv a.txt b.txt` -- `mkdir` with no argument,
        which fails with its own usage message."""
        command = Command(
            'mv a.txt b.txt',
            "mv: cannot move 'a.txt' to 'b.txt': No such file or directory")
        assert get_new_command(command) == []

    def test_a_source_that_is_missing_is_somebody_elses_business(self):
        """It fired on `No such file or directory` however it arose, so a
        mistyped *source* was answered by making a directory named after the
        destination -- which fails, and leaves the directory behind."""
        command = Command('mv typoo.txt newname.txt',
                          "mv: cannot stat 'typoo.txt': No such file or directory")
        assert not match(command)

    def test_a_trailing_slash_onto_a_file(self):
        """`cp x realfile/` where `realfile` is a file prints `Not a directory`,
        which this matched -- and `mkdir -p realfile` fails too."""
        command = Command('cp x realfile/',
                          "cp: cannot create regular file 'realfile/': Not a directory")
        assert not match(command)

    def test_it_and_its_sibling_answer_the_same(self):
        """One place decides what a destination is; this defers to it."""
        from thebleep.rules import cp_create_destination

        output = ("cp: cannot create regular file 'nodir/a.txt':"
                  ' No such file or directory')
        command = Command('cp a.txt nodir/a.txt', output)
        assert get_new_command(command) \
            == cp_create_destination.get_new_command(command)
