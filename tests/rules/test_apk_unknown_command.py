# -*- encoding: utf-8 -*-

"""What apk prints, taken from `alpine:latest` (apk-tools 3.0.6)."""

import pytest
from thebleep.rules.apk_unknown_command import (
    _parse_operations, get_new_command, match)
from thebleep.types import Command

# `apk isntall vim`, verbatim.
UNKNOWN = u"ERROR: 'isntall' is not an apk command. See 'apk --help'.\n"

# `apk --help`, abridged to two groups.
HELP = u"""apk-tools 3.0.6-r0, compiled for x86_64.

Usage: apk [<GLOBAL OPTIONS>...] COMMAND [<OPTIONS>...] [<ARGUMENTS>...]

Package installation and removal:
  add        Add or modify constraints in WORLD and commit changes
  del        Remove constraints from WORLD and commit changes

System maintenance:
  fix        Fix, reinstall or upgrade packages without modifying WORLD
  update     Update repository indexes
  upgrade    Install upgrades available from repositories
  cache      Manage the local package cache

Querying package information:
  query      Query information about packages by various criteria
  list       List packages matching a pattern or other criteria
  search     Search for packages by name or description
  info       Give detailed information about packages or repositories

This apk has coffee making abilities.
"""


@pytest.fixture(autouse=True)
def apk_help(mocker):
    mocker.patch('thebleep.rules.apk_unknown_command.tool_output',
                 return_value=HELP)


def test_match():
    assert match(Command('apk isntall vim', UNKNOWN))
    assert match(Command('sudo apk isntall vim', UNKNOWN))


def test_not_match():
    assert not match(Command('apk add vim', u'OK: 8 MiB in 20 packages'))
    assert not match(Command('apt isntall vim', UNKNOWN))


def test_parse_operations():
    assert _parse_operations(HELP) == [
        'add', 'del', 'fix', 'update', 'upgrade', 'cache', 'query', 'list',
        'search', 'info']


@pytest.mark.parametrize('script, first', [
    ('apk isntall vim', 'apk add vim'),
    ('apk install vim', 'apk add vim'),
    ('sudo apk install vim', 'sudo apk add vim'),
    ('apk remove vim', 'apk del vim'),
    ('apk serach vim', 'apk search vim'),
    ('apk upgrad', 'apk upgrade'),
])
def test_get_new_command(script, first):
    output = UNKNOWN.replace('isntall', script.split()[
        2 if script.startswith('sudo') else 1])
    assert get_new_command(Command(script, output))[0] == first


def test_the_synonym_comes_first_and_the_spelling_matches_follow():
    got = get_new_command(Command('apk instal vim',
                                  UNKNOWN.replace('isntall', 'instal')))
    assert got[0] == 'apk add vim'
    assert 'apk info vim' in got
