# -*- coding: utf-8 -*-

"""Every rule, against a megabyte of the most awkward output we can think of.

A failed build prints megabytes, and a rule that reads that output with a
backtracking regex or copies it once per pattern turns a correction into a hang.
One such regex was found by accident, from the benchmark; this is that discovery
made permanent.

The guard is deliberately relative. An absolute millisecond threshold across
whatever machine CI hands us is a flake, but "sixteen times the input took
roughly sixteen times as long" holds on a fast laptop and a loaded runner alike.
Only rules slow enough for the comparison to mean anything are judged, so noise
on the small size cannot fail the build.

"""

import ast
import io
import os
import time
import pytest
from thebleep import rules as rules_package
from thebleep.types import Command, Rule

RULES_DIRECTORY = os.path.dirname(os.path.abspath(rules_package.__file__))

SMALL = 64 * 1024
LARGE = 16 * SMALL          # a megabyte

# Only look at rules that take long enough for a ratio to mean something.
WORTH_JUDGING_MS = 15

# How much worse than linear counts as a problem. Generous: the point is to
# catch quadratic, not to police a factor of two.
SLACK = 4.0


def shapes(size):
    """Output shaped to make a matcher work as hard as it can.

    A long run with no newline to stop a `.*` early, a long run of one repeated
    token, something that looks like the beginning of many patterns without ever
    finishing one, and text that is not ASCII, where `str.lower` has no fast
    path.

    """
    return [
        ('one-long-line', u'a' * size),
        ('no-newline-spaces', u'word ' * (size // 5)),
        ('repeated-lines', u'error: something went wrong\n' * (size // 28)),
        ('looks-like-a-match',
         u"error: unknown command 'x'\nDid you mean this?\n\t"
         + u'y' * (size - 50)),
        ('tabs-and-quotes', u"\t'" * (size // 2)),
        ('not-ascii', u'ü—' * (size // 4)),
    ]


SCRIPTS = [u'git brnch', u'brew instal x', u'npm run x', u'ls x', u'sudo x',
           u'unzip x.zip', u'python x.py', u'grep x f', u'cd x', u'man x']


def rule_names():
    return sorted(name[:-3] for name in os.listdir(RULES_DIRECTORY)
                  if name.endswith('.py') and name != '__init__.py')


@pytest.fixture(scope='module')
def loaded():
    return {name: Rule.from_path(os.path.join(RULES_DIRECTORY, name + '.py'))
            for name in rule_names()}


def _slowest(rule, output):
    """The worst time this rule takes over any of the scripts, in ms."""
    worst = 0.0
    for script in SCRIPTS:
        command = Command(script, output)
        started = time.perf_counter()
        try:
            if rule.match(command):
                rule.get_new_command(command)
        except Exception:
            # Whether a rule raises is `test_rule_quality`'s subject. Here it
            # only matters how long it took to get there.
            pass
        worst = max(worst, (time.perf_counter() - started) * 1000)
    return worst


@pytest.mark.parametrize('name', rule_names())
def test_a_rule_reads_a_megabyte_in_proportion(name, loaded):
    rule = loaded[name]
    if rule is None:
        pytest.skip('{} did not load'.format(name))

    for shape, _ in shapes(SMALL):
        small = _slowest(rule, dict(shapes(SMALL))[shape])
        large = _slowest(rule, dict(shapes(LARGE))[shape])
        if large < WORTH_JUDGING_MS:
            continue
        linear = max(small, 0.05) * (LARGE / float(SMALL))
        assert large <= linear * SLACK, (
            '{} took {:.1f} ms on {} KB of {} and {:.1f} ms on {} KB, which is '
            '{:.1f}x worse than reading it in proportion'.format(
                name, small, SMALL // 1024, shape, large, LARGE // 1024,
                large / linear))


def _lowers_the_output(node):
    """`command.output.lower()`, and the same of `stdout` and `stderr`."""
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'lower'
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr in ('output', 'stdout', 'stderr'))


REPEATS = (ast.For, ast.While, ast.comprehension, ast.GeneratorExp,
           ast.ListComp, ast.SetComp, ast.DictComp)


@pytest.mark.parametrize('name', rule_names())
def test_the_output_is_not_lowered_once_per_pattern(name):
    """`str.lower` on a megabyte is not free, and it was inside a loop.

    `sudo` has twenty-eight messages it looks for and lowered the whole output
    for each of them: 66 ms on a megabyte of text that is not ASCII, down to
    4.6 ms with the call lifted out. `cd_mkdir` wrote its three as a tuple
    passed to `any`, whose elements are all evaluated before `any` sees the
    first one, so it lowered a megabyte three times to answer one question.

    Checked on the syntax rather than by timing, because timing a few
    milliseconds on somebody else's build machine is a flake.

    """
    with io.open(os.path.join(RULES_DIRECTORY, name + '.py'),
                 encoding='utf-8') as handle:
        source = handle.read()
    tree = ast.parse(source, filename=name)

    assert len([node for node in ast.walk(tree)
                if _lowers_the_output(node)]) <= 1, (
        '{} lowers the whole output more than once; lower it into a variable '
        'and use that'.format(name))

    for node in ast.walk(tree):
        if not isinstance(node, REPEATS):
            continue
        inside = [child for child in ast.walk(node)
                  if _lowers_the_output(child)]
        assert not inside, (
            '{} lowers the whole output inside a loop, so it is copied once '
            'per pattern; lower it into a variable first'.format(name))
