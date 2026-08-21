# -*- encoding: utf-8 -*-

"""bun says what it did not find and nothing else, so the list is ours.

Every fixture below was captured from bun 1.4.0 in a container, running the
failing command against a `package.json` with `build`, `test` and `start` in
it. The message is the same one whether or not `run` was typed, which is the
thing this rule is built around.

"""

import json
import pytest
from thebleep.rules import bun_script_not_found as rule
from thebleep.types import Command

# bun 1.4.0. One line, and no suggestion of its own.
RUN_SCRIPT = 'error: Script not found "buidl"\n'
BARE_COMMAND = 'error: Script not found "instal"\n'

# What `bun --help` prints, from `Commands:` to the first thing back at the
# left margin. The two-column layout and its wrapped example line are kept
# exactly as bun emits them: `lint` under `run` is an example of an argument,
# not a command, and reading it as one would offer `bun lint`.
HELP = '''Bun is a fast JavaScript runtime, package manager, bundler, and test runner.

Usage: bun <command> [...flags] [...args]

Commands:
  run       ./my-script.ts       Execute a file with Bun
            lint                 Run a package.json script
  test                           Run unit tests with Bun
  x         next                 Execute a package binary (CLI)
  repl                           Start a REPL session with Bun

  install                        Install dependencies for a package.json
  add       @zarfjs/zarf         Add a dependency to package.json
  remove    underscore           Remove a dependency from package.json

  build     ./a.ts ./b.jsx       Bundle TypeScript & JavaScript

  <command> --help               Print help text for command.

Flags:
      --silent                        Don't print the script command
  -v, --version                       Print version and exit
'''


@pytest.fixture(autouse=True)
def no_leftover_lists(monkeypatch):
    """`_scripts` and `_commands` are `eager`, not cached, but be sure."""
    monkeypatch.setattr(rule, 'tool_lines', lambda *a, **kw: [])
    yield


@pytest.fixture
def project(tmpdir, monkeypatch):
    """A directory with a `package.json` in it, and bun's own cwd."""
    def build(scripts, subdirectory=None):
        tmpdir.join('package.json').write(json.dumps(
            {'name': 'x', 'scripts': scripts}))
        where = tmpdir
        if subdirectory:
            where = tmpdir.mkdir(subdirectory)
        monkeypatch.chdir(where)
        return str(tmpdir)

    return build


@pytest.mark.parametrize('output', [RUN_SCRIPT, BARE_COMMAND])
def test_match(output):
    assert rule.match(Command('bun run buidl', output))


@pytest.mark.parametrize('script, output', [
    # bun printing something else entirely.
    ('bun run build', 'error: MODULE_NOT_FOUND\n'),
    ('bun install', 'error: FailedToOpenSocket\n'),
    ('bun run build', ''),
])
def test_not_match(script, output):
    assert not rule.match(Command(script, output))


def test_the_script_that_was_meant(project):
    project({'build': 'x', 'test': 'y', 'start': 'z'})
    assert rule.get_new_command(
        Command('bun run buidl', RUN_SCRIPT))[0] == 'bun run build'


def test_a_script_in_a_subdirectory_of_the_project(project):
    """bun walks up to find `package.json`, so this has to as well."""
    project({'build': 'x'}, subdirectory='src')
    assert rule.get_new_command(
        Command('bun run buidl', RUN_SCRIPT))[0] == 'bun run build'


def test_a_command_of_buns_own(project, monkeypatch):
    """`bun instal` is reported as a missing script; `install` answers it."""
    project({'build': 'x'})
    monkeypatch.setattr(rule, 'tool_lines',
                        lambda *a, **kw: HELP.splitlines())
    assert rule.get_new_command(
        Command('bun instal', BARE_COMMAND))[0] == 'bun install'


def test_only_scripts_are_offered_after_run(project, monkeypatch):
    """After `bun run` a command of bun's own cannot be what was meant.

    `bun run instal` does not run `bun install`, it looks for a script called
    `instal` -- so offering `bun run install` would be offering another
    failure. Only the project's scripts are candidates there.

    """
    project({'insta': 'x'})
    monkeypatch.setattr(rule, 'tool_lines',
                        lambda *a, **kw: HELP.splitlines())
    assert rule.get_new_command(
        Command('bun run instal', 'error: Script not found "instal"\n')) \
        == ['bun run insta']


def test_buns_commands_are_read_out_of_its_help(monkeypatch):
    monkeypatch.setattr(rule, 'tool_lines',
                        lambda *a, **kw: HELP.splitlines())
    commands = rule._commands()

    assert 'run' in commands
    assert 'install' in commands
    assert 'build' in commands

    # The wrapped example under `run`, at twelve spaces rather than two.
    assert 'lint' not in commands
    # The help describing itself, and the flags below the listing.
    assert '<command>' not in commands
    assert '--silent' not in commands
    assert '-v,' not in commands


def test_no_package_json_and_no_bun(tmpdir, monkeypatch):
    """Nothing to go on is no suggestion, not a crash."""
    monkeypatch.chdir(tmpdir.mkdir('empty'))
    monkeypatch.setattr(rule, '_package_json', lambda: None)
    assert rule.get_new_command(Command('bun run buidl', RUN_SCRIPT)) == []


def test_a_half_written_package_json(tmpdir, monkeypatch):
    """A `package.json` being edited is not a reason to raise at a prompt."""
    tmpdir.join('package.json').write('{"scripts": {"build"')
    monkeypatch.chdir(tmpdir)
    assert rule.get_new_command(Command('bun run buidl', RUN_SCRIPT)) == []


def test_a_package_json_with_no_scripts(tmpdir, monkeypatch):
    tmpdir.join('package.json').write('{"name": "x"}')
    monkeypatch.chdir(tmpdir)
    assert rule.get_new_command(Command('bun run buidl', RUN_SCRIPT)) == []


def test_a_script_name_that_needs_quoting(tmpdir, monkeypatch):
    """`package.json` accepts a script called anything; the shell does not.

    The suggestion is evaluated by the shell, so a name out of a file this tool
    did not write is quoted before it goes back there.

    """
    tmpdir.join('package.json').write(json.dumps(
        {'scripts': {'build; rm -rf ~': 'x'}}))
    monkeypatch.chdir(tmpdir)
    new = rule.get_new_command(Command('bun run buil', RUN_SCRIPT.replace(
        'buidl', 'buil')))

    assert new == ["bun run 'build; rm -rf ~'"]


def test_an_empty_name_is_not_a_suggestion():
    """bun prints `Script not found ""` for `bun run ''`."""
    assert rule.get_new_command(
        Command('bun run ""', 'error: Script not found ""\n')) == []
