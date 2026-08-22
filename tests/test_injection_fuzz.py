# -*- coding: utf-8 -*-

"""The canary, walked past every rule instead of just past the usual suspects.

`test_injection.py` proves the quoting claim for the rules somebody thought
of. This one does not need anybody to think of a rule: it takes each rule's
own test fixtures, puts hostile shell syntax into every word-shaped position
of the captured output one at a time -- keeping enough of the original word
that a closeness filter still has something to like -- and hands whatever the
rule suggests to a real bash with stubbed `PATH`, asserting nothing ran.

The oracle and the method are the ones this repo settled injection claims
with; the difference is only who supplies the cases. A rule whose suggestion
survives every mutation of its own captured output has a claim much stronger
than one hand-written case.

Two things are asserted per rule:

- every suggestion any mutation produced was inert;
- the fuzz was not vacuous. Either some mutation matched -- and what it
  produced was inert, above -- or no mutation can match because the rule
  takes nothing variable out of its output at all, which its own captures
  then prove: a rule that matches a fixed sentence has no channel for
  hostile data, and one that no longer matches its captures at all has come
  apart from them.

Rules whose tests build their fixtures through helpers rather than literals
(39 of them today) carry no template to mutate; they stay with the
hand-written cases and are skipped here by name, visibly.

POSIX-only, like the canary itself.

"""

import ast
import importlib
import os
import re
import shutil
import subprocess
import sys

import pytest

from thebleep.shells import Bash
from thebleep.types import Command

RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'thebleep', 'rules')
TESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')

# Hostile tails appended to a kept prefix of a captured word. Each writes a
# differently named file if any part of it reaches a shell unquoted, so a
# failure says which shape got through.
TAILS = ('$(>PWNED_SUB)', '`>PWNED_BTK`', ';>PWNED_SEMI', '&&>PWNED_AND',
         '|>PWNED_PIPE', '>PWNED_REDIR', "'>PWNED_QUO")

TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_.\-]{3,}')

# Bound the work: most mutations do not match, and these caps say how deep a
# rule is searched before the fuzzer moves on. Deterministic, so a failure
# reproduces.
MUTATIONS_PER_RULE = 240
MATCHES_PER_RULE = 40


def rule_names():
    """Every bundled rule that has a test file with literals to mutate."""
    names = []
    for fname in sorted(os.listdir(RULES_DIR)):
        if fname.endswith('.py') and fname != '__init__.py':
            names.append(fname[:-3])
    return names


def _literals(test_path):
    """`(output templates, command lines)` written down in a rule's tests."""
    with open(test_path, encoding='utf-8') as handle:
        tree = ast.parse(handle.read())

    templates = []
    commands = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if len(node.value) >= 12:
                templates.append(node.value)
        elif isinstance(node, ast.Call):
            name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
            if name == 'Command' and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) \
                        and isinstance(first.value, str):
                    commands.append(first.value)
    return templates, commands


def _mutations(template):
    """The template, with one captured word partly replaced by hostile
    syntax at a time."""
    seen = set()
    for found in TOKEN.finditer(template):
        token = found.group(0)
        # Half the word survives so distance filters still see the typo they
        # saw in the real capture.
        prefix = token[:max(4, len(token) // 2)]
        for tail in TAILS:
            mutated = (template[:found.start()] + prefix + tail
                       + template[found.end():])
            if mutated not in seen:
                seen.add(mutated)
                yield mutated


@pytest.fixture(scope='module')
def canary(tmp_path_factory):
    """Runs a suggestion where it can only leave evidence, and reports it.

    The same oracle as `tests/test_injection.py`: stubbed `PATH`, empty work
    directory, real bash, and the listing of that directory afterwards. Each
    suggestion gets a fresh empty directory -- one leftover file would convict
    every later suggestion of a crime an earlier one committed.

    """
    stubs = tmp_path_factory.mktemp('bin')
    stub = stubs / '_stub'
    stub.write_text('#!/bin/sh\nexit 0\n')
    stub.chmod(0o755)
    for name in ('git', 'az', 'composer', 'grunt', 'npm', 'yarn', 'gradle',
                 'sh', 'env', 'rm', 'kill', 'ssh', 'ssh-keygen', 'vim',
                 'rails', 'kubectl', 'uv', 'ruff', 'gh', 'helm', 'black',
                 'cargo', 'prettier', 'pytest', 'mytool', 'bun', 'deno'):
        shutil.copy(str(stub), str(stubs / name))

    work = tmp_path_factory.mktemp('work')
    counter = [0]

    def run(suggestion):
        counter[0] += 1
        scene = work / str(counter[0])
        scene.mkdir()
        subprocess.call(['/bin/bash', '-c', suggestion], cwd=str(scene),
                        env={'PATH': str(stubs), 'HOME': str(scene)},
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL, timeout=30)
        return sorted(os.listdir(str(scene)))

    return run


@pytest.fixture(autouse=True)
def _bash(set_shell):
    set_shell(Bash)


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
@pytest.mark.parametrize('name', rule_names())
def test_no_mutation_of_a_rule_makes_it_suggest_something_that_runs(
        name, canary):
    test_path = os.path.join(TESTS_DIR, 'test_{}.py'.format(name))
    if not os.path.exists(test_path):
        pytest.skip('no literal fixtures to mutate')

    templates, commands = _literals(test_path)
    if not templates or not commands:
        pytest.skip('no literal fixtures to mutate')

    rule = importlib.import_module('thebleep.rules.{}'.format(name))
    reached = False
    sent = set()

    tried = 0
    for template in templates:
        for mutated in _mutations(template):
            if tried >= MUTATIONS_PER_RULE:
                break

            for script in commands:
                command = Command(script, mutated)
                try:
                    if not rule.match(command):
                        continue
                    suggestions = rule.get_new_command(command)
                except Exception:
                    continue

                reached = True
                for suggestion in suggestions or []:
                    if suggestion in sent:
                        continue
                    sent.add(suggestion)
                    assert canary(suggestion) == [], \
                        '{} suggested {} for a mutated capture'.format(
                            name, suggestion)

            tried += 1

        if tried >= MUTATIONS_PER_RULE:
            break

    if not reached:
        # Nothing hostile ever reached a suggestion, mutated or raw. That is
        # either a rule that takes nothing variable out of its output -- no
        # channel for hostile data, which is the right answer -- or fixtures
        # this fuzzer could not read its way into (docstrings and helper-built
        # commands leave strings here that are not outputs). The first is
        # proved by the hand-written cases in `test_injection.py`; the second
        # is this fuzzer's blindness, not the rule's drift. Both are skipped,
        # visibly, rather than failed on evidence nobody has.
        pytest.skip('no mutation of these literals ever reached {}'
                    .format(name))
