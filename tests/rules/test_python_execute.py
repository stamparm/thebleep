import pytest
from thebleep.rules.python_execute import match, get_new_command
from thebleep.types import Command

# Captured from CPython 3.12.
OPEN_FAILED = ("python: can't open file '/tmp/foo': "
               "[Errno 2] No such file or directory\n")


@pytest.mark.parametrize('command', [
    Command('python foo', OPEN_FAILED),
    Command('python bar', OPEN_FAILED.replace('/tmp/foo', '/tmp/bar'))])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    # A missing module is not a filename that lost `.py`. This was answered
    # with `python -c 'import nonexistent_zz'.py`.
    Command("python -c 'import nonexistent_zz'",
            "Traceback (most recent call last):\n"
            '  File "<string>", line 1, in <module>\n'
            "ModuleNotFoundError: No module named 'nonexistent_zz'\n"),
    # Nor is a syntax error in a file that exists.
    Command('python x.py',
            '  File "x.py", line 3\n    x=\n     ^\n'
            'SyntaxError: invalid syntax\n'),
    # The file is named `.py` already; whatever went wrong is not this.
    Command('python foo.py', OPEN_FAILED)])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('python foo', OPEN_FAILED), 'python foo.py')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
