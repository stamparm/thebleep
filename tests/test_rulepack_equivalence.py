# -*- coding: utf-8 -*-

"""The rule pack's contract: it may cost time, never a correction.

The pack skips loading rules it can prove could not match. Everything about that
proof is an optimisation, so the corrections it produces have to be exactly the
corrections a full load of every rule produces -- the same commands, in the same
order, with the same side effects -- whatever state the cache is in and whatever
is in the user's own rules directory.

Everything here runs in a subprocess: `THEBLEEP_NO_RULE_PACK` and
`PYTHONHASHSEED` are read once, at startup.

"""

import json
import marshal
import os
import subprocess
import sys
import pytest

# A rule of somebody's own, decorated with something we know nothing about. The
# decorator ignores the `for_app` underneath it, so anything the pack concluded
# from that would be wrong -- which is why an unrecognised decorator has to stop
# it concluding anything.
UNKNOWN_DECORATOR = u'''# -*- coding: utf-8 -*-
from thebleep.utils import for_app


def whatever_i_like(fn):
    def wrapper(command):
        return 'anything' in command.output
    return wrapper


@whatever_i_like
@for_app('git')
def match(command):
    return False


def get_new_command(command):
    return u'from-the-unknown-decorator'
'''

PLAIN = u'''# -*- coding: utf-8 -*-
from thebleep.utils import for_app


@for_app('git')
def match(command):
    return 'brnch' in command.script


def get_new_command(command):
    return command.script.replace('brnch', 'branch')
'''

# Neither of these is a rule. The pack and the full loader have to agree about
# that too, and neither may take the run down with it.
BROKEN = u'''raise RuntimeError('this rule does not import')\n'''
HALF_A_RULE = u'''def match(command):\n    return True\n'''

CONTRIB = u'''# -*- coding: utf-8 -*-


def match(command):
    return 'contrib' in command.output


def get_new_command(command):
    return u'from-the-contrib-package'
'''

# What to ask about. Deliberately includes an empty output, a megabyte of it,
# and text that is not ASCII.
DRIVER = u'''# -*- coding: utf-8 -*-
import json
import sys
from thebleep import conf
conf.settings.init()
from thebleep.corrector import get_corrected_commands
from thebleep.types import Command

CASES = [
    (u'git brnch', u'git: brnch is not a git command'),
    (u'git brnch', u''),
    (u'git brnch', u'anything at all'),
    (u'brew instal x', u'anything at all'),
    (u'sl -l', u'sl: command not found'),
    (u'ls /nowhere', u'ls: /nowhere: No such file or directory'),
    (u'cd ..', u''),
    (u'apt-get instal vim', u'E: Invalid operation instal'),
    (u'x', u'contrib'),
    (u'git brnch', u'\\u00fcnic\\u00f8de \\u2014 anything'),
    (u'grep \\u00fc f', u'anything'),
    (u'git brnch', u'anything\\n' + u'noise ' * 200000),
    (u'git brnch', u'x' * 1000000),
]

out = []
for script, output in CASES:
    corrections = [(c.script, c.priority, c.side_effect is not None)
                   for c in get_corrected_commands(Command(script, output))]
    out.append([script, len(output), corrections])
json.dump(out, sys.stdout, sort_keys=True)
'''


@pytest.fixture
def tree(tmpdir, source_root):
    """A checkout, a user rules directory and a third-party rule package."""
    config = tmpdir.mkdir('config')
    rules = config.mkdir('thebleep').mkdir('rules')
    rules.join('user_plain.py').write_text(PLAIN, 'utf-8')
    rules.join('user_unknown_decorator.py').write_text(UNKNOWN_DECORATOR,
                                                       'utf-8')
    rules.join('user_broken.py').write_text(BROKEN, 'utf-8')
    rules.join('user_half.py').write_text(HALF_A_RULE, 'utf-8')

    contrib = tmpdir.mkdir('site').mkdir('thebleep_contrib_test')
    contrib.join('__init__.py').write_text(u'', 'utf-8')
    contrib.mkdir('rules').join('contrib_rule.py').write_text(CONTRIB, 'utf-8')

    driver = tmpdir.join('driver.py')
    driver.write_text(DRIVER, 'utf-8')

    cache = tmpdir.mkdir('cache')
    return {
        'driver': str(driver),
        'cache': str(cache),
        'environment': dict(
            os.environ,
            PYTHONPATH=os.pathsep.join([str(source_root),
                                        str(tmpdir.join('site'))]),
            XDG_CONFIG_HOME=str(config),
            XDG_CACHE_HOME=str(cache)),
    }


def _corrections(tree, pack=True, seed='0'):
    environment = dict(tree['environment'], PYTHONHASHSEED=seed)
    environment['THEBLEEP_NO_RULE_PACK'] = 'false' if pack else 'true'
    finished = subprocess.run([sys.executable, tree['driver']],
                              env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=600)
    assert finished.returncode == 0, \
        finished.stderr.decode('utf-8', 'replace')[-3000:]
    return json.loads(finished.stdout.decode('utf-8'))


def _packs(tree):
    directory = os.path.join(tree['cache'], 'thebleep')
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, name)
            for name in os.listdir(directory) if name.endswith('.pack')]


class TestEquivalence(object):
    def test_a_cold_pack_agrees_with_a_full_load(self, tree):
        assert _corrections(tree, pack=True) == _corrections(tree, pack=False)

    def test_a_warm_pack_agrees_with_a_full_load(self, tree):
        _corrections(tree, pack=True)
        assert _packs(tree), 'no pack was written, so this proves nothing'
        assert _corrections(tree, pack=True) == _corrections(tree, pack=False)

    @pytest.mark.parametrize('seed', ['0', '1', '987654321'])
    def test_the_hash_seed_changes_nothing(self, tree, seed):
        assert _corrections(tree, pack=True, seed=seed) == \
            _corrections(tree, pack=False, seed='0')

    def test_an_unknown_decorator_does_not_lose_a_rule(self, tree):
        """The decorator ignores the `for_app` under it and matches on output.

        Reading that `for_app` and skipping the rule for anything but git would
        lose the correction for `brew instal x` entirely.

        """
        expected = _corrections(tree, pack=False)
        assert _corrections(tree, pack=True) == expected
        flat = json.dumps(expected)
        assert 'from-the-unknown-decorator' in flat

    def test_a_contrib_package_is_found_either_way(self, tree):
        assert 'from-the-contrib-package' in json.dumps(
            _corrections(tree, pack=True))


class TestADamagedPack(object):
    """A cache that has gone wrong may cost time. It may not lose a rule."""

    def test_one_corrupt_code_blob(self, tree):
        expected = _corrections(tree, pack=False)
        _corrections(tree, pack=True)

        path = _packs(tree)[0]
        with open(path, 'rb') as handle:
            pack = marshal.load(handle)
        for key in pack['entries']:
            pack['entries'][key]['code'] = b'not a code object'
        with open(path, 'wb') as handle:
            marshal.dump(pack, handle)

        assert _corrections(tree, pack=True) == expected

    @pytest.mark.parametrize('metadata, value', [
        ('apps', 'not even a tuple'),
        ('apps', (b'not a string',)),
        ('apps', 42),
        ('output', 'not a tuple of clauses'),
        ('output', (('a needle, but not in a clause', False),)),
        ('output', ((),)),
        ('enabled', 'not a boolean'),
        ('priority', 'not an integer'),
        ('requires_output', 'not a boolean'),
        ('name', 'wrong-name'),
        ('code', 'not even bytes'),
        ('mtime', 'not a number'),
        ('size', 'not a number'),
    ])
    def test_metadata_of_the_wrong_type(self, tree, metadata, value):
        """Dispatch believes the pack, so a wrong type there is a wrong answer.

        `apps` holding a string makes the intersection compare characters, and a
        `name` belonging to another file decides enablement by somebody else's
        settings. Each of these is treated as a missing entry and built again.

        """
        expected = _corrections(tree, pack=False)
        _corrections(tree, pack=True)

        path = _packs(tree)[0]
        with open(path, 'rb') as handle:
            pack = marshal.load(handle)
        for key in pack['entries']:
            pack['entries'][key][metadata] = value
        try:
            with open(path, 'wb') as handle:
                marshal.dump(pack, handle)
        except ValueError:
            pytest.skip('{!r} is not marshallable'.format(value))

        # Either it notices and falls back, or it produces the same answer. What
        # it must not do is produce a different one.
        assert _corrections(tree, pack=True) == expected

    def test_a_truncated_pack(self, tree):
        expected = _corrections(tree, pack=False)
        _corrections(tree, pack=True)

        path = _packs(tree)[0]
        with open(path, 'rb') as handle:
            head = handle.read(64)
        with open(path, 'wb') as handle:
            handle.write(head)

        assert _corrections(tree, pack=True) == expected

    def test_an_edited_rule_is_noticed(self, tree, tmpdir):
        """What stands behind a well-formed entry: the file's size and mtime.

        A pack whose entry says something false but says it in the right shape
        is indistinguishable from a valid one, so the guarantee is that an entry
        stops being used the moment its file changes.

        """
        _corrections(tree, pack=True)
        rules = os.path.join(tree['environment']['XDG_CONFIG_HOME'],
                             'thebleep', 'rules')
        with open(os.path.join(rules, 'user_plain.py'), 'a') as handle:
            handle.write(u'\n\npriority = 42\n')

        got = _corrections(tree, pack=True)
        assert got == _corrections(tree, pack=False)
        assert 42 in [priority
                      for _, _, corrections in got
                      for _, priority, _ in corrections]

    def test_an_unwritable_cache(self, tree, tmpdir):
        expected = _corrections(tree, pack=False)
        blocked = tmpdir.join('no-cache-here')
        blocked.write('not a directory')
        tree['environment']['XDG_CACHE_HOME'] = str(blocked)
        assert _corrections(tree, pack=True) == expected
