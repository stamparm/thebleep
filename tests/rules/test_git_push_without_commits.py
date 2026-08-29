from thebleep.types import Command
from thebleep.rules.git_push_without_commits import get_new_command, match


def test_match():
    script = "git push -u origin master"
    output = "error: src refspec master does not match any\nerror: failed to..."
    assert match(Command(script, output))


def test_not_match():
    script = "git push -u origin master"
    assert not match(Command(script, "Everything up-to-date"))


def test_a_configuration_value_is_not_a_push():
    output = "error: src refspec master does not match any"
    assert not match(Command('git config push.default simple', output))


def test_get_new_command():
    script = "git push -u origin master"
    output = "error: src refspec master does not match any\nerror: failed to..."
    new_command = 'git commit -m "Initial commit" && git push -u origin master'
    assert get_new_command(Command(script, output)) == new_command


def test_global_options_are_preserved_for_the_initial_commit():
    script = 'git -C worktree push -u origin master'
    output = 'error: src refspec master does not match any'
    assert get_new_command(Command(script, output)) == (
        'git -C worktree commit -m "Initial commit" && '
        'git -C worktree push -u origin master')
