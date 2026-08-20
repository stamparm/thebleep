import pytest
from thebleep.rules.mkdir_p import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('mkdir foo/bar/baz', 'mkdir: foo/bar: No such file or directory'),
    Command('./bin/hdfs dfs -mkdir foo/bar/baz', 'mkdir: `foo/bar/baz\': No such file or directory'),
    Command('hdfs dfs -mkdir foo/bar/baz', 'mkdir: `foo/bar/baz\': No such file or directory')
])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('mkdir foo/bar/baz', ''),
    Command('mkdir foo/bar/baz', 'foo bar baz'),
    Command('hdfs dfs -mkdir foo/bar/baz', ''),
    Command('./bin/hdfs dfs -mkdir foo/bar/baz', ''),
    Command('', ''),
    # `'mkdir' in command.script` matched all of these and offered each of them
    # back unchanged.
    Command('echo mkdir', 'No such file or directory'),
    Command('git mkdir-x', 'No such file or directory'),
    Command('python mkdirs.py', 'No such file or directory'),
    Command('mkdir', 'No such file or directory'),
])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('mkdir foo/bar/baz', ''), 'mkdir -p foo/bar/baz'),
    (Command('hdfs dfs -mkdir foo/bar/baz', ''), 'hdfs dfs -mkdir -p foo/bar/baz'),
    (Command('./bin/hdfs dfs -mkdir foo/bar/baz', ''), './bin/hdfs dfs -mkdir -p foo/bar/baz'),
])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


class TestWhatItUsedToAnswer(object):
    """`No such file or directory` is a message half the tools on the machine
    print, and `mkdir` in a command is not the same as `mkdir` having failed."""

    def test_a_mkdir_that_worked_and_something_else_that_did_not(self):
        """The suggestion cannot even run: `mkdir -p -p`."""
        command = Command(
            'mkdir -p /tmp/q && rmdir /tmp/q/nope',
            "rmdir: failed to remove '/tmp/q/nope': No such file or directory")
        assert not match(command)

    @pytest.mark.parametrize('script', [
        'mkdir -p foo/bar', 'mkdir --parents foo/bar', 'mkdir -pv foo/bar',
        'mkdir -vp foo/bar',
    ])
    def test_the_flag_is_not_added_twice(self, script):
        output = "mkdir: cannot create directory 'foo/bar': " \
                 'No such file or directory'
        assert not match(Command(script, output))

    @pytest.mark.parametrize('output', [
        # GNU coreutils 9.x.
        "mkdir: cannot create directory 'foo/bar/baz':"
        ' No such file or directory',
        # Hadoop.
        "mkdir: `foo/bar/baz': No such file or directory",
        # Something else printed first, mkdir second.
        'warning: whatever\n'
        "mkdir: cannot create directory 'x': No such file or directory",
    ])
    def test_and_mkdirs_own_complaint_still_matches(self, output):
        assert match(Command('mkdir foo/bar/baz', output))
