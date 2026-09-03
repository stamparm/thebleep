import pytest
from thebleep.rules.sed_unterminated_s import match, get_new_command
from thebleep.types import Command


@pytest.fixture(params=[
    "sed: -e expression #1, char 9: unterminated `s' command",
    "/usr/bin/sed: -e expression #1, char 9: unterminated 's' command",
    'sed: 1: "s/foo/bar": unescaped newline inside substitute pattern',
    "sed: unmatched '/'"])
def sed_unterminated_s(request):
    return request.param


def test_match(sed_unterminated_s):
    assert match(Command('sed -e s/foo/bar', sed_unterminated_s))
    assert match(Command('sed -es/foo/bar', sed_unterminated_s))
    assert match(Command('sed -e s/foo/bar -e s/baz/quz', sed_unterminated_s))
    assert not match(Command('sed -e s/foo/bar', ''))
    assert not match(Command('sed -es/foo/bar', ''))
    assert not match(Command('sed -e s/foo/bar -e s/baz/quz', ''))


def test_get_new_command(sed_unterminated_s):
    assert (get_new_command(Command('sed -e s/foo/bar', sed_unterminated_s))
            == 'sed -e s/foo/bar/')
    assert (get_new_command(Command('sed -es/foo/bar', sed_unterminated_s))
            == 'sed -es/foo/bar/')
    assert (get_new_command(Command(r"sed -e 's/\/foo/bar'", sed_unterminated_s))
            == r"sed -e 's/\/foo/bar/'")
    assert (get_new_command(Command(r"sed -e s/foo/bar -es/baz/quz", sed_unterminated_s))
            == r"sed -e s/foo/bar/ -es/baz/quz/")


def test_only_the_expression_changes():
    """Redirections and pipes stay shell syntax, and the user's quoting stays
    theirs: the line used to be split and every word re-quoted."""
    output = "sed: -e expression #1, char 9: unterminated `s' command"
    assert get_new_command(Command("sed 's/a/b' f > out", output)) == \
        "sed 's/a/b/' f > out"
    assert get_new_command(Command('sed s/a/b f | less', output)) == \
        'sed s/a/b/ f | less'
