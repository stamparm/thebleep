# -*- coding: utf-8 -*-

"""Every rule, against a megabyte of the most awkward output we can think of.

A failed build prints megabytes, and a rule that reads that output with a
backtracking regex or copies it once per pattern turns a correction into a hang.
One such regex was found by accident, from the benchmark; this is that discovery
made permanent.

The guard was a ratio -- "sixteen times the input took roughly sixteen times as
long" -- and that turned out to be the flaky one. On a CI runner the 64 KB
measurement for a fast rule comes back as 0.0 ms, and a ratio against zero fails
whatever the large measurement is. It failed on macOS and on Linux for two
different rules, neither of which is superlinear.

So the guard is an absolute ceiling with a very large margin, which the shape of
this particular bug allows: the regex that started all this took *minutes* on a
megabyte, and the slowest rule in the corpus takes about 25 ms. A second and a
half is fifty times the honest worst case and a fraction of the dishonest one,
which is not a threshold anybody has to tune. The ratio is still checked, but
only when both measurements are big enough for one to mean anything.

"""

import ast
import io
import os
import time
import pytest
from thebleep import rules as rules_package
from thebleep.types import Command, Rule

pytestmark = pytest.mark.slow

RULES_DIRECTORY = os.path.dirname(os.path.abspath(rules_package.__file__))

SMALL = 64 * 1024
LARGE = 16 * SMALL          # a megabyte

# No rule may take longer than this to read a megabyte. The slowest in the
# corpus takes about 25 ms on this machine; the quadratic regex this test exists
# for took minutes.
CEILING_MS = 1500

# Below this, a measurement is timer noise and a ratio built on it means
# nothing -- which is how the ratio guard managed to fail for rules that are
# perfectly linear.
MEASURABLE_MS = 5.0

# How much worse than linear counts as a problem, when the ratio is meaningful
# at all. Generous: the point is to catch quadratic, not to police a factor of
# two.
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


def _once(rule, command):
    started = time.perf_counter()
    try:
        if rule.match(command):
            rule.get_new_command(command)
    except Exception:
        # Whether a rule raises is `test_rule_quality`'s subject. Here it only
        # matters how long it took to get there.
        pass
    return (time.perf_counter() - started) * 1000


def _slowest(rule, output):
    """The worst time this rule takes over any of the scripts, in ms.

    Each script is timed twice and the quicker of the two kept: a runner that
    descheduled us once should not be reported as a slow rule.

    """
    worst = 0.0
    for script in SCRIPTS:
        command = Command(script, output)
        worst = max(worst, min(_once(rule, command), _once(rule, command)))
    return worst


@pytest.mark.parametrize('name', rule_names())
def test_a_rule_reads_a_megabyte_in_proportion(name, loaded):
    rule = loaded[name]
    if rule is None:
        pytest.skip('{} did not load'.format(name))

    small_shapes = dict(shapes(SMALL))
    large_shapes = dict(shapes(LARGE))

    for shape in small_shapes:
        large = _slowest(rule, large_shapes[shape])

        assert large <= CEILING_MS, (
            '{} took {:.0f} ms to read {} KB of {}, and the ceiling is {} ms. '
            'Something in it is not reading the output once.'.format(
                name, large, LARGE // 1024, shape, CEILING_MS))

        small = _slowest(rule, small_shapes[shape])
        if small < MEASURABLE_MS:
            # Too quick at 64 KB for a ratio to say anything.
            continue

        linear = small * (LARGE / float(SMALL))
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
