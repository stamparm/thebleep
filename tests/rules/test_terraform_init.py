import pytest
from thebleep.rules.terraform_init import match, get_new_command
from thebleep.types import Command


# Terraform 1.15.8, for the two ways a fresh checkout fails: the providers it
# needs have no version selected yet, and the versions selected in the lock
# file have not been downloaded. Neither says "initialization required".
inconsistent_lock_file = '''\
Error: Inconsistent dependency lock file

The following dependency selections recorded in the lock file are
inconsistent with the current configuration:
  - provider registry.terraform.io/hashicorp/random: required by this configuration but no version is selected

To make the initial dependency selections that will initialize the
dependency lock file, run:
  terraform init
'''

plugins_not_installed = '''\
Error: Required plugins are not installed

The installed provider plugins are not consistent with the packages
selected in the dependency lock file:
  - registry.terraform.io/hashicorp/random: there is no package for registry.terraform.io/hashicorp/random 3.6.0 cached in .terraform/providers

Terraform uses external plugins to integrate with a variety of different
infrastructure services. To download the plugins required for this
configuration, run:
  terraform init
'''

backend_not_configured = '''\
Error: Backend initialization required, please run "terraform init"

Reason: Initial configuration of the requested backend "local"
'''


@pytest.mark.parametrize('script, output', [
    ('terraform plan', 'Error: Initialization required. '
                       'Please see the error message above.'),
    ('terraform plan', 'This module is not yet installed. Run "terraform init" '
                       'to install all modules required by this configuration.'),
    ('terraform apply', 'Error: Initialization required. '
                        'Please see the error message above.'),
    ('terraform apply', 'This module is not yet installed. Run "terraform init" '
                        'to install all modules required by this configuration.'),
    ('terraform plan', inconsistent_lock_file),
    ('terraform apply', inconsistent_lock_file),
    ('terraform plan', plugins_not_installed),
    ('terraform apply', plugins_not_installed),
    ('terraform plan', backend_not_configured)])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('terraform --version', 'Terraform v0.12.2'),
    ('terraform plan', 'No changes. Infrastructure is up-to-date.'),
    ('terraform apply', 'Apply complete! Resources: 0 added, 0 changed, 0 destroyed.'),
    # Already an init: running one again would fix nothing.
    ('terraform init', plugins_not_installed),
    ('terraform init -upgrade', inconsistent_lock_file),
])
def test_not_match(script, output):
    assert not match(Command(script, output=output))


@pytest.mark.parametrize('command, new_command', [
    (Command('terraform plan', ''), 'terraform init && terraform plan'),
    (Command('terraform apply', ''), 'terraform init && terraform apply'),
])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
