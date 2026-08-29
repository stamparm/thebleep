import pytest
from thebleep.rules.git_help_aliased import match, get_new_command
from thebleep.types import Command


# Both quotings. git 2.30.2, 2.39.5 and 2.47.3 all print the plain-quote form;
# the backtick form is what git used to print and what the rule read by
# splitting on the backtick -- which on a current git raised IndexError and put
# a traceback in the user's terminal.
@pytest.mark.parametrize('script, output', [
    ('git help st', "'st' is aliased to 'status'"),
    ('git help ds', "'ds' is aliased to 'diff --staged'"),
    ('git help st', "`git st' is aliased to `status'"),
    ('git help ds', "`git ds' is aliased to `diff --staged'")])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('git help status', "GIT-STATUS(1)...Git Manual...GIT-STATUS(1)"),
    ('git help diff', "GIT-DIFF(1)...Git Manual...GIT-DIFF(1)")])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, output, new_command', [
    ('git help st', "`git st' is aliased to `status'", 'git help status'),
    ('git help ds', "`git ds' is aliased to `diff --staged'", 'git help diff')])
def test_get_new_command(script, output, new_command):
    assert get_new_command(Command(script, output)) == new_command


def test_a_word_in_an_argument_is_not_git_help():
    assert not match(Command('git config help.alias',
                             "'st' is aliased to 'status'"))


def test_global_options_do_not_hide_git_help():
    assert match(Command('git -C worktree help st',
                         "'st' is aliased to 'status'"))
