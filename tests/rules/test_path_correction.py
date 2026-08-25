import pytest
from thebleep.rules.path_correction import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def tree(tmp_path):
    etc = tmp_path / 'etc'
    etc.mkdir()
    (etc / 'passwd').write_text('')
    return tmp_path


@pytest.mark.usefixtures('no_memoize')
def test_match(tree):
    broken = str(tree / 'ec' / 'passwd')
    command = Command('cat {}'.format(broken),
                      'cat: {}: No such file or directory'.format(broken))

    assert match(command)


@pytest.mark.usefixtures('no_memoize')
def test_not_match_when_nothing_explains_the_typo(tree):
    broken = str(tree / 'nope' / 'passwd')
    command = Command('cat {}'.format(broken),
                      'cat: {}: No such file or directory'.format(broken))

    assert not match(command)


@pytest.mark.usefixtures('no_memoize')
def test_not_match_for_cd(tree):
    broken = str(tree / 'ec')
    command = Command('cd {}'.format(broken),
                      'cd: {}: No such file or directory'.format(broken))

    assert not match(command)


@pytest.mark.usefixtures('no_memoize')
def test_get_new_command(tree):
    broken = str(tree / 'ec' / 'passwd')
    fixed = str(tree / 'etc' / 'passwd')
    command = Command('cat {}'.format(broken),
                      'cat: {}: No such file or directory'.format(broken))

    assert get_new_command(command) == 'cat {}'.format(fixed)


@pytest.mark.usefixtures('no_memoize')
def test_get_new_command_fixes_the_last_segment_too(tree):
    broken = str(tree / 'etc' / 'psswd')
    fixed = str(tree / 'etc' / 'passwd')
    command = Command('cat {}'.format(broken),
                      'cat: {}: No such file or directory'.format(broken))

    assert get_new_command(command) == 'cat {}'.format(fixed)
