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

import os
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


# Suggestions that cannot be taken back. Every one of these is something a rule
# in this package really offers, and each is right in its own place -- what must
# never happen is one being offered on no evidence.
DESTRUCTIVE = ('rm -rf', 'rm -r ', 'reset --hard', 'reset HEAD~', 'clean -f',
               '--force', '--no-verify', 'git branch -D', 'git branch -d',
               'checkout .', 'push -f', 'mkfs', 'chmod 777')

# Ordinary commands, none of which is a request to undo anything.
ORDINARY = ('git commit -m x', 'git status', 'git push', 'git pull', 'ls',
            'cd /tmp', 'cp a b', 'mv a b', 'ln -s a b', 'mkdir x',
            'tar -xf a', 'git tag v1', 'git checkout main', 'git stash',
            'git rebase main', 'npm install', 'pip install x', 'docker ps',
            'make', 'echo hi', 'git branch main', 'git merge main',
            'git am patch')

# Errors that say nothing about what went wrong, which is the common case for a
# command whose output nobody has.
VAGUE = (None, '', '\n', 'error: something went wrong\n', 'fatal: whatever\n',
         'permission denied\n')


@pytest.mark.usefixtures('no_memoize')
def test_nothing_irreversible_is_offered_on_no_evidence(os_environ):
    """The class that produced the two worst bugs this project has had.

    `git_commit_reset` fired on any failed command containing `commit` and
    answered `git reset HEAD~`, which throws a commit away -- and every failed
    commit is a commit that has not happened, so what it offered to undo was the
    one before it. `ln_s_order` took the first argument that existed and moved
    it to the end, which for `ln -s /etc/hostname /tmp/link` -- both existing --
    is a suggestion that puts a symlink on top of `/etc/hostname`.

    Both had tests. Neither had a test for *this*: that a command which failed,
    with output that explains nothing, is never answered with something
    irreversible. A rule that wants to offer one has to have read a reason.

    The previous command *failed* here, which is the whole point. `git commit`
    that succeeded is exactly when `git reset HEAD~` is the right answer, and
    that case is `tests/rules/test_git_commit_reset.py`.

    """
    from thebleep import corrector, replay

    os_environ[replay.EXIT_ENV] = '1'

    offered = set()
    for script in ORDINARY:
        for output in VAGUE:
            for corrected in corrector.get_corrected_commands(
                    types.Command(script, output)):
                for marker in DESTRUCTIVE:
                    if marker in corrected.script:
                        offered.add((script, repr(output),
                                     corrected.rule.name, corrected.script))

    assert not offered, sorted(offered)


def test_no_rule_starts_a_program_by_itself():
    """One subprocess API, and rules go through it.

    Twenty rules used to call `Popen` or `check_output` directly, and not one of
    them had a timeout: `lsof` against a wedged NFS mount, `docker` against a
    dead daemon, `gradle` waiting on a daemon of its own. A rule that raises is
    caught by `Rule.get_corrected_commands`; a rule that never returns is The
    Bleep frozen at the prompt, and there is nothing to catch.

    `utils.tool_lines` and `utils.tool_output` have the timeout, the process
    kill, the bounded read, the `/dev/null` stderr and the replacement-character
    decoding in one place. This is what stops the twenty coming back one at a
    time -- a review found four still outside it after the first sweep, which is
    what a rule this cheap is for.

    `specific/` is included: a helper a rule calls can hang exactly as well as
    the rule can.

    """
    import re

    banned = re.compile(r'\b(?:Popen|check_output|check_call|subprocess\.run)\b')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    offenders = []
    for directory in ('rules', 'specific'):
        where = os.path.join(root, 'thebleep', directory)
        for name in sorted(os.listdir(where)):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(where, name), encoding='utf-8') as handle:
                for number, line in enumerate(handle, 1):
                    if line.lstrip().startswith('#'):
                        continue
                    if banned.search(line):
                        offenders.append('{}/{}:{}: {}'.format(
                            directory, name, number, line.strip()))

    assert not offenders, (
        'these start a program without the shared timeout; use'
        ' utils.tool_lines or utils.tool_output:\n  '
        + '\n  '.join(offenders))
