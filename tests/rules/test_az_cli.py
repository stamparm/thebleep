import pytest

from thebleep.rules.az_cli import match, get_new_command
from thebleep.types import Command


no_suggestions = '''\
az provider: error: the following arguments are required: _subcommand
usage: az provider [-h] {list,show,register,unregister,operation} ...
'''


# azure-cli 2.44.1, and the same wording in azure-cli's current sources.
misspelled_group = '''\
ERROR: 'vmm' is misspelled or not recognized by the system.
Did you mean 'vm' ?

Examples from AI knowledge base:
az vm list
List all VMs.

https://aka.ms/cli_ref
Read more about the command in reference docs
'''

misspelled_command = '''\
ERROR: 'lst' is misspelled or not recognized by the system.
Did you mean 'list' ?

Examples from AI knowledge base:
az vm list
List all VMs.

https://aka.ms/cli_ref
Read more about the command in reference docs
'''

# knack's wording, which `az` printed before azure-cli took the message over.
legacy_misspelled_group = '''\
az: 'providers' is not in the 'az' command group. See 'az --help'.

The most similar choice to 'providers' is:
    provider
'''

legacy_misspelled_command = '''\
az provider: 'lis' is not in the 'az provider' command group. See 'az provider --help'.

The most similar choice to 'lis' is:
    list
'''


@pytest.mark.parametrize('command', [
    Command('az vmm list', misspelled_group),
    Command('az vm lst', misspelled_command),
    Command('az providers', legacy_misspelled_group),
    Command('az provider lis', legacy_misspelled_command)])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('az provider', no_suggestions),
    # `az` knows the word is wrong but has nothing to offer instead.
    Command('az zzzz', "ERROR: 'zzzz' is misspelled or not recognized by "
                       "the system.\n")])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, result', [
    (Command('az vmm list', misspelled_group), ['az vm list']),
    (Command('az vm lst', misspelled_command), ['az vm list']),
    (Command('az providers list', legacy_misspelled_group),
     ['az provider list']),
    (Command('az provider lis', legacy_misspelled_command),
     ['az provider list'])
])
def test_get_new_command(command, result):
    assert get_new_command(command) == result
