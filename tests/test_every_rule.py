# -*- encoding: utf-8 -*-

"""What must be true of every rule, asked of every rule.

Three peer reviews found the same shape of bug over and over: a regex that
matched in `match` and did not in `get_new_command`, a `findall(...)[0]` on a
program whose wording had moved, a `script_parts[1]` on a command that has only
one word. Every one of them was invisible, because `Rule.is_match` and
`Rule.get_corrected_commands` catch what a rule raises -- so the only symptom is
a rule that quietly never fires, and the only way to notice is to read it.

So they are asked instead. These tests are deliberately not about any one rule:
they generate the awkward cases -- no output, empty output, output from a
different program, a command of one word, a command of none -- and hold every
rule in the package to surviving them.

`no_command` is the reason for `no_memoize` and for a `PATH` that is left alone:
these run against the real machine, which is the point.

"""

import pytest
from thebleep import const, types

# What a rule can be handed that it did not expect. Nothing exotic -- every one
# of these is something a real correction produces.
AWKWARD_OUTPUT = (
    '',
    '\n',
    'command not found',
    # The marker a rule matches on, with nothing after it that its regex wants.
    'No such command',
    'Did you mean',
    'usage:',
    'error: pathspec',
    "Unknown command '",
    'Invalid operation',
    'not found\n\n',
    # Something else's error entirely.
    'Traceback (most recent call last):\n  File "x", line 1\n',
    # Bytes that are not text, arriving as replacement characters.
    u'���',
)

AWKWARD_SCRIPTS = (
    # One word: every `script_parts[1]` is an IndexError here.
    'git', 'npm', 'apt', 'docker', 'hg', 'cargo', 'gem', 'yarn', 'go', 'pip',
    'sudo', 'ls',
    # A subcommand and nothing to work on.
    'git stash', 'npm run', 'docker image', 'apt install',
    # Shell syntax, quotes left open, and a name that is only punctuation.
    'echo "oops', "ls '", 'a && b', '--', '-', '...',
)


def _every_rule():
    """Every rule in the package, loaded the way a correction loads them."""
    from thebleep import corrector

    rules = corrector.get_rules()
    assert len(rules) > 100, 'the rules did not load, so this checked nothing'
    return rules


ALL_RULES = _every_rule()
BY_NAME = {rule.name: rule for rule in ALL_RULES}


@pytest.fixture(autouse=True)
def enabled(settings):
    """Every rule, including the ones off by default."""
    settings.rules = const.DEFAULT_RULES
    settings.exclude_rules = []
    settings.priority = {}


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('rule', ALL_RULES, ids=lambda rule: rule.name)
def test_no_rule_raises_on_awkward_input(rule, monkeypatch):
    """`match` and `get_new_command` both, on every combination.

    A rule is allowed to decline. It is not allowed to raise, because the
    framework hides that and the rule then never fires against the real input
    either -- `git_add`, `hostscli` and `git_rebase_merge_dir` had each been
    dead for releases before somebody read them.

    """
    # Nothing here may start a program: these are made-up commands, and a rule
    # asking the real `docker` what it can do would make this test slow and
    # dependent on what happens to be installed.
    def refuse(*args, **kwargs):
        raise AssertionError('a rule started a program from a fuzz case')

    monkeypatch.setattr('thebleep.utils.tool_lines', lambda *a, **k: [])
    monkeypatch.setattr('thebleep.utils.tool_output', lambda *a, **k: '')

    for script in AWKWARD_SCRIPTS:
        for output in AWKWARD_OUTPUT:
            command = types.Command(script, output)
            try:
                matched = rule.match(command)
            except Exception as error:                       # noqa: BLE001
                raise AssertionError(
                    u'{}.match({!r}, {!r}) raised {}: {}'.format(
                        rule.name, script, output,
                        type(error).__name__, error))

            if not matched:
                continue

            try:
                rule.get_new_command(command)
            except Exception as error:                       # noqa: BLE001
                raise AssertionError(
                    u'{} matched ({!r}, {!r}) and then'
                    u' get_new_command raised {}: {}'.format(
                        rule.name, script, output,
                        type(error).__name__, error))


@pytest.mark.parametrize('rule', ALL_RULES, ids=lambda rule: rule.name)
def test_a_rule_that_ignores_the_output_says_so(rule):
    """`requires_output` defaults to `True`, and a rule that does not need it
    and does not say so is switched off for no reason.

    Which is every correction where re-running the command was declined or was
    not possible -- so fourteen rules that read nothing but the command itself
    were unavailable in exactly the situation where they are the only thing that
    could have helped.

    Read off the module source, which is a blunt test and a sound one in the
    direction that matters: a module with no mention of `output` in it cannot be
    reading any.

    """
    if not rule.requires_output:
        return

    # By path rather than by import: one rule is called `test.py`, so its
    # module name is `thebleep.rules.test.py` and there is no importing that.
    import os

    # `encoding='utf-8'`, because a rule's source is UTF-8 and Windows
    # defaults to cp1252 -- `switch_lang` has Cyrillic and Korean in it, and
    # this failed there and nowhere else.
    with open(os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))),
            'thebleep', 'rules', rule.name + '.py'),
            encoding='utf-8') as handle:
        source = handle.read()

    # The decorators can read it on the rule's behalf, and two of them do.
    if 'git_support' in source or 'sudo_support' in source:
        return

    assert 'output' in source, (
        '{} declares requires_output but never mentions output, so it is'
        ' switched off whenever the output is unavailable for nothing'
        .format(rule.name))
