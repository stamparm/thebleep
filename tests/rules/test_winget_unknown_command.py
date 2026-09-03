# -*- encoding: utf-8 -*-

"""winget's usage text, in the shape it prints for a command it does not
know (Windows Package Manager 1.x)."""

import pytest
from thebleep.rules.winget_unknown_command import get_new_command, match
from thebleep.types import Command

USAGE = u"""Windows Package Manager v1.12.350
Copyright (c) Microsoft Corporation. All rights reserved.

The winget command line utility enables installing applications and other \
packages from the command line.

usage: winget  [<command>] [<options>]

The following commands are available:
  install    Installs the given package
  show       Shows information about a package
  source     Manage sources of packages
  search     Find and show basic info of packages
  list       Display installed packages
  upgrade    Shows and performs available upgrades
  uninstall  Uninstalls the given package
  hash       Helper to hash installer files
  validate   Validates a manifest file
  settings   Open settings or set administrator settings
  features   Shows the status of experimental features
  export     Exports a list of the installed packages
  import     Installs all the packages in a file
  pin        Manage package pins
  configure  Configures the system into a desired state
  download   Downloads the installer from a given package
  repair     Repairs the selected package

For more details on a specific command, pass it the help argument. [-?]

The following options are available:
  -v,--version                Display the version of the tool
  --info                      Display general info of the tool
  -?,--help                   Shows help about the selected command
  --wait                      Prompts the user to press any key before exiting
  --logs,--open-logs          Open the default logs location
  --verbose,--verbose-logs    Enables verbose logging for winget
  --nowarn,--ignore-warnings  Suppresses warning outputs
  --disable-interactivity     Disable interactive prompts
  --proxy                     Set a proxy to use for this execution
  --no-proxy                  Disable the use of proxy for this execution

More help can be found at: https://aka.ms/winget-command-help
"""


def test_match():
    assert match(Command('winget isntall vim', USAGE))
    assert match(Command('winget --verbose isntall vim', USAGE))


@pytest.mark.parametrize('script, output', [
    ('winget install vim', USAGE),
    ('winget isntall vim', u'No package found matching input criteria.'),
    ('winget', USAGE),
    ('apt isntall vim', USAGE),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, first', [
    ('winget isntall vim', 'winget install vim'),
    ('winget serach vim', 'winget search vim'),
    ('winget upgarde --all', 'winget upgrade --all'),
    ('winget lsit', 'winget list'),
])
def test_get_new_command(script, first):
    assert get_new_command(Command(script, USAGE))[0] == first
