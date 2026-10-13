import pytest
from thebleep.rules import package_name_typo
from thebleep.rules.package_name_typo import get_new_command, match
from thebleep.types import Command

# apt 3.3.3 (debian:testing) and dnf5 5.4.3.0 (fedora:latest), verbatim.
APT_GET = ('Reading package lists...\nBuilding dependency tree...\n'
           'Reading state information...\nE: Unable to locate package pyhton3\n')
APT = APT_GET.replace('E: ', 'Error: ')
DNF = ('Repositories loaded.\nFailed to resolve the transaction:\n'
       'No match for argument: pyhton3\nYou can try to add to command line:\n'
       '  --skip-unavailable to skip unavailable packages\n')


@pytest.fixture(autouse=True)
def index(mocker):
    return mocker.patch.object(package_name_typo, 'tool_lines', return_value=[
        'python3', 'python3-pip', 'pythia8', 'python-is-python3', 'pyhton'])


@pytest.mark.parametrize('script, output, fixed', [
    ('apt-get install pyhton3', APT_GET, 'apt-get install python3'),
    ('sudo apt install -y pyhton3', APT, 'sudo apt install -y python3'),
    ('dnf install pyhton3', DNF, 'dnf install python3'),
    ('yum install pyhton3', DNF, 'yum install python3'),
])
def test_a_misspelt_package(script, output, fixed):
    command = Command(script, output)
    assert match(command)
    assert get_new_command(command)[0] == fixed


def test_the_index_is_asked_by_first_letter(index):
    get_new_command(Command('apt-get install pyhton3', APT_GET))
    assert index.call_args[0][0] == ['apt-cache', 'pkgnames', 'p']
    get_new_command(Command('dnf install pyhton3', DNF))
    assert index.call_args[0][0][:2] == ['dnf', 'repoquery']


def test_nothing_near_is_nothing(index):
    index.return_value = ['zsh', 'zstd']
    assert get_new_command(Command('apt-get install pyhton3', APT_GET)) == []


def test_not_an_install_failure():
    assert not match(Command('apt-get install python3', 'Setting up python3'))
