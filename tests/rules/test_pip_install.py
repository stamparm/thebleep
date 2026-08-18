# -*- coding: UTF-8 -*-
from thebleep.rules.pip_install import match, get_new_command
from thebleep.types import Command


def test_match():
    response1 = """
    Could not install packages due to an EnvironmentError: [Errno 13] Permission denied: '/Library/Python/2.7/site-packages/entrypoints.pyc'
Consider using the `--user` option or check the permissions.
"""
    assert match(Command('pip install -r requirements.txt', response1))

    response2 = """
Collecting bacon
  Downloading https://files.pythonhosted.org/packages/b2/81/19fb79139ee71c8bc4e5a444546f318e2b87253b8939ec8a7e10d63b7341/bacon-0.3.1.zip (11.0MB)
    100% |████████████████████████████████| 11.0MB 3.0MB/s
Installing collected packages: bacon
  Running setup.py install for bacon ... done
Successfully installed bacon-0.3.1
"""
    assert not match(Command('pip install bacon', response2))

    # pip3 is what most people type.
    assert match(Command('pip3 install -r requirements.txt', response1))

    # `--user` already tried, so there is nothing left for this rule to add.
    assert not match(Command('pip install --user bacon', response1))


def test_no_sudo_pip():
    """`sudo pip install` is not a thing to suggest.

    It writes into the interpreter the operating system maintains, leaving the
    package manager's idea of what is installed and reality disagreeing, and it
    runs a package's own setup code as root.

    """
    import io
    from thebleep import rules
    from thebleep.system import Path

    source = io.open(str(Path(rules.__file__).parent.joinpath('pip_install.py')),
                     encoding='utf-8').read()
    assert 'sudo {}' not in source

    # Whatever the command was, the suggestion does not gain a sudo it did not
    # already have. A sudo the user typed themselves is theirs to keep.
    for script in ('pip install bacon', 'pip install -r req.txt',
                   'sudo pip install bacon'):
        command = Command(script, 'Permission denied')
        fixed = get_new_command(command)
        assert fixed.startswith('sudo ') == script.startswith('sudo ')


def test_get_new_command():
    assert get_new_command(Command('pip install -r requirements.txt', '')) == 'pip install --user -r requirements.txt'
    assert get_new_command(Command('pip install bacon', '')) == 'pip install --user bacon'
    assert get_new_command(Command('pip3 install bacon', '')) == 'pip3 install --user bacon'
