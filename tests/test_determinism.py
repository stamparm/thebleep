# -*- coding: utf-8 -*-

"""The same command gets the same suggestions in the same order, every time.

Python randomises string hashing per process, so anything that goes through a
set comes out in a different order on every run. `organize_commands` used to,
and the consequence was that pressing the down arrow once gave you a different
suggestion each time -- which matters when one of the offered commands deletes
something and another does not.

These run subprocesses because `PYTHONHASHSEED` is read at interpreter startup.

"""

import os
import subprocess
import sys
import pytest

SEEDS = ['0', '1', '2', '12345', '4294967295']

ORDER = u"""
from thebleep.corrector import organize_commands
from thebleep.types import CorrectedCommand

# Several rules offering a suggestion at the same priority, which is the usual
# case: every rule is at DEFAULT_PRIORITY unless it says otherwise.
same = [CorrectedCommand(u'fix-%d' % i, None, 1000) for i in range(8)]
# And a couple that should sort in front of them wherever they turn up.
mixed = same[:3] + [CorrectedCommand(u'first', None, 10)] + same[3:]

for commands in (same, mixed):
    print(u' '.join(c.script for c in organize_commands(iter(commands))))

# A duplicate is dropped, and the one that stays is the first one seen.
duplicated = [CorrectedCommand(u'a', None, 1000),
              CorrectedCommand(u'b', None, 1000),
              CorrectedCommand(u'a', None, 1000),
              CorrectedCommand(u'c', None, 1000)]
print(u' '.join(c.script for c in organize_commands(iter(duplicated))))
"""


def _run(seed, source, root):
    environment = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(root))
    finished = subprocess.run([sys.executable, '-c', source],
                              env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
    assert finished.returncode == 0, finished.stderr.decode('utf-8', 'replace')
    return finished.stdout.decode('utf-8')


def test_suggestion_order_does_not_depend_on_the_hash_seed(source_root):
    results = {seed: _run(seed, ORDER, source_root) for seed in SEEDS}
    assert len(set(results.values())) == 1, results


def test_suggestion_order_is_the_order_the_rules_offered(source_root):
    lines = _run(SEEDS[0], ORDER, source_root).strip().split('\n')
    assert lines[0].split() == ['fix-%d' % i for i in range(8)]
    # The lower priority sorts in front of the rest, wherever it arrived.
    assert lines[1].split()[0] == 'fix-0'
    assert lines[1].split()[1] == 'first'
    assert lines[2].split() == ['a', 'b', 'c']


RULEPACK = u"""
import os
from thebleep import conf
conf.settings.init()
from thebleep.corrector import get_rules
from thebleep.types import Command

for script in (u'git brnch', u'brew instal x', u'sl -l', u'ls x'):
    rules = get_rules(Command(script, u'error: unknown command'))
    print(script + u': ' + u' '.join(rule.name for rule in rules))
"""


@pytest.mark.parametrize('disabled', ['true', 'false'])
def test_rule_order_does_not_depend_on_the_hash_seed(source_root, tmpdir,
                                                     disabled):
    """Both through the rule pack and through a full load of every rule."""
    results = {}
    for seed in SEEDS:
        home = tmpdir.mkdir('home-{}-{}'.format(disabled, seed))
        environment = dict(os.environ, PYTHONHASHSEED=seed,
                           PYTHONPATH=str(source_root),
                           XDG_CONFIG_HOME=str(home),
                           XDG_CACHE_HOME=str(home),
                           THEBLEEP_NO_RULE_PACK=disabled)
        finished = subprocess.run([sys.executable, '-c', RULEPACK],
                                  env=environment, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=300)
        assert finished.returncode == 0, \
            finished.stderr.decode('utf-8', 'replace')
        results[seed] = finished.stdout.decode('utf-8')
    assert len(set(results.values())) == 1, results
