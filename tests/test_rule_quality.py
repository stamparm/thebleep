# -*- coding: utf-8 -*-

"""Structural checks over the whole rule corpus.

Not a static analyser. Each check here is one that has already caught a real
mistake in this repository, and each one is cheap enough to run on every commit.

"""

import ast
import io
import os
import subprocess
import pytest
from thebleep import rulepack
from thebleep import rules as rules_package
from thebleep.types import Command, Rule

pytestmark = pytest.mark.slow


RULES_DIRECTORY = os.path.dirname(os.path.abspath(rules_package.__file__))


def rule_paths():
    return sorted(
        os.path.join(RULES_DIRECTORY, name)
        for name in os.listdir(RULES_DIRECTORY)
        if name.endswith('.py') and name != '__init__.py')


def rule_names():
    return [os.path.basename(path)[:-3] for path in rule_paths()]


@pytest.fixture(scope='module')
def loaded():
    """Every bundled rule, loaded once."""
    return [(os.path.basename(path)[:-3], Rule.from_path(path))
            for path in rule_paths()]


def test_every_rule_loads(loaded):
    broken = [name for name, rule in loaded if rule is None]
    assert broken == []


def test_every_rule_has_both_halves(loaded):
    for name, rule in loaded:
        assert callable(rule.match), '{} has no match'.format(name)
        assert callable(rule.get_new_command), \
            '{} has no get_new_command'.format(name)


def test_rule_names_are_unique():
    names = rule_names()
    assert len(names) == len(set(names))


# Rules that change something besides running the suggestion. Adding to this
# list should be a deliberate act, because a side effect is a thing the user
# does not see in the command they agree to -- which is why `dirty_untar`,
# `dirty_unzip` and `ssh_known_hosts` no longer have one.
RULES_WITH_SIDE_EFFECTS = set()


def test_no_new_hidden_side_effects(loaded):
    have = {name for name, rule in loaded if rule.side_effect is not None}
    assert have == RULES_WITH_SIDE_EFFECTS


# ---------------------------------------------------------------------------
# Nothing raises a programming error on a command it was not expecting


def declared_apps():
    """Every app name any rule says it is about.

    `git_support` is one of the ways of saying it, and saying it that way is why
    a bare `git` went untested for so long.

    """
    apps = set(app for apps in rulepack.APP_DECORATORS.values()
               for app in apps)
    apps.update(('hub', 'sudo'))
    for path in rule_paths():
        with io.open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, 'id', None) == 'for_app'):
                continue
            for argument in node.args:
                if isinstance(argument, ast.Constant) \
                        and isinstance(argument.value, str):
                    apps.add(argument.value)
    return sorted(apps)


# Output that says a bit of everything a rule might be looking for, so that as
# many rules as possible get past `match` and reach their parsing.
BUSY_OUTPUT = u"""error: unknown command 'x'
Did you mean this?
        install
fatal: not a git repository
Permission denied
is a directory
No such file or directory
command not found
error: pathspec 'x' did not match
Unknown command: brew x
usage: prog [-h]
ERROR:  While executing gem ... (Gem::UnknownCommandError)
    Unknown command x
"""


def awkward_commands():
    """Commands a rule has to survive, whether or not it can help with them."""
    for app in declared_apps():
        # An app with no subcommand at all. This is what found the crashes in
        # `composer`, `go` and `touch`: a rule reaching for script_parts[1] or
        # for a group in a regex that had not matched.
        yield Command(app, BUSY_OUTPUT)
        yield Command(u'sudo ' + app, BUSY_OUTPUT)
    for script in (u'sudo', u'cd', u'rm', u'python', u'man', u'"unbalanced',
                   u'FOO=bar', u'FOO=bar ls', u'./x', u'/usr/bin/x',
                   # A megabyte of one line, and a line of unusual characters.
                   u'grep x ' + u'y' * 1000,
                   u'ls ünïcødé-ñåme'):
        yield Command(script, BUSY_OUTPUT)


# A rule may fail because the tool it is about is not installed here. That is
# the environment, not the rule. Anything else -- IndexError from an
# ungated script_parts, AttributeError from a regex that did not match,
# TypeError from a None passed on -- is a mistake in the rule.
ENVIRONMENT = (OSError, subprocess.SubprocessError)


@pytest.mark.parametrize('name', rule_names())
def test_a_rule_does_not_raise_on_a_command_it_cannot_help_with(name, loaded):
    rule = dict(loaded)[name]
    for command in awkward_commands():
        try:
            matched = rule.match(command)
        except ENVIRONMENT:
            continue
        except Exception as error:
            raise AssertionError(
                u'{}.match({!r}) raised {}: {}'.format(
                    name, command.script, type(error).__name__, error))

        if not matched:
            continue

        try:
            rule.get_new_command(command)
        except ENVIRONMENT:
            continue
        except Exception as error:
            raise AssertionError(
                u'{}.get_new_command({!r}) raised {}: {}'.format(
                    name, command.script, type(error).__name__, error))


def test_every_for_app_names_its_apps_where_the_pack_can_read_them():
    """`@for_app(*names)` is a name the rule pack cannot resolve.

    It reads the app names out of the syntax tree without executing anything, so
    a starred argument means "app unknown", and the rule is then consulted for
    every command there is. `ssh_known_hosts` and `scm_correction` were, which
    is two extra rules loaded and run on every correction.

    A rule of somebody's own may of course write it any way it likes; this is
    about the ones shipped here.

    """
    starred = []
    for path in rule_paths():
        with io.open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, 'id', None) == 'for_app'):
                continue
            if any(isinstance(argument, ast.Starred)
                   for argument in node.args):
                starred.append(os.path.basename(path))
    assert starred == []
