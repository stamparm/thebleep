import pytest
from thebleep.rules.quotation_marks import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command("git commit -m \'My Message\"", ''),
    Command("git commit -am \"Mismatched Quotation Marks\'", ''),
    Command("echo \"hello\'", '')])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    # Both kinds of quote, and nothing wrong with it. The rule used to match
    # every one of these and rewrite the quotes into something broken:
    # `git commit -m "it"s fine"`.
    Command('git commit -m "it\'s fine"', ''),
    Command('echo "don\'t"', ''),
    Command('grep "a" \'b\' file', ''),
    # Malformed, but swapping the quotes does not make it parse.
    Command('echo "a \'b \'c', ''),
    # Only one kind of quote.
    Command("echo 'unclosed", ''),
    Command('echo "unclosed', ''),
])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command("git commit -m \'My Message\"", ''), "git commit -m \"My Message\""),
    (Command("git commit -am \"Mismatched Quotation Marks\'", ''), "git commit -am \"Mismatched Quotation Marks\""),
    (Command("echo \"hello\'", ''), "echo \"hello\"")])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
