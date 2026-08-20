import pytest
from thebleep.rules.long_form_help import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('output', [
    'Try \'grep --help\' for more information.'])
def test_match(output):
    assert match(Command('grep -h', output))


def test_not_match():
    assert not match(Command('', ''))


@pytest.mark.parametrize('before, after', [
    ('grep -h', 'grep --help'),
    ('tar -h', 'tar --help'),
    ('docker run -h', 'docker run --help'),
    ('cut -h', 'cut --help')])
def test_get_new_command(before, after):
    assert get_new_command(Command(before, '')) == after


@pytest.mark.parametrize('output, expected', [
    # As git spells it.
    ("Try 'git --help' for more information.", 'git --help'),
    # As busybox, curl and a good many others spell it -- lowercase. `match`
    # searched with `re.I` and `get_new_command` did not, so all of these
    # matched and then produced no suggestion at all.
    ("try 'curl --help' for more information.", 'curl --help'),
    ("run 'ls --help' for details.", 'ls --help'),
    ("TRY 'x --help' FOR MORE INFORMATION.", 'x --help'),
])
def test_every_case_it_matches_it_also_answers(output, expected):
    command = Command('git commit -h', output)
    assert match(command)
    assert get_new_command(command) == expected
