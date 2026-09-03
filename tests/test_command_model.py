# -*- encoding: utf-8 -*-

import pytest

from thebleep.command_model import parse, replace_span


def test_top_level_segments_keep_source_spans_and_separators():
    script = 'cd foo && gti status | grep main'
    model = parse(script)

    assert model.complete
    commands = [(segment.command.text if segment.command else None,
                 segment.separator) for segment in model.segments]
    assert commands == [('cd', '&&'), ('gti', '|'), ('grep', None)]
    assert script[model.segments[1].start:model.segments[1].end] == (
        'gti status')
    assert model.segments[1].command.start == 10
    assert model.segments[1].command.end == 13


def test_quotes_comments_and_redirections_are_not_command_boundaries():
    model = parse("echo 'a; b' 2>log # comment\n; gti status")

    commands = [(segment.command.text if segment.command else None,
                 segment.separator) for segment in model.segments]
    assert commands == [('echo', '\n'), ('gti', None)]
    first = model.segments[0]
    assert [token.kind for token in first.tokens] == [
        'word', 'word', 'redirection', 'word', 'comment']


def test_nested_substitutions_have_their_own_segments():
    model = parse('echo $(gti status; grep main) && ls')
    nested = [token for token in model.segments[0].tokens
              if token.kind == 'substitution'][0]

    commands = [(segment.command.text if segment.command else None,
                 segment.separator) for segment in nested.children]
    assert commands == [('gti', ';'), ('grep', None)]
    assert model.segments[0].separator == '&&'


@pytest.mark.parametrize('script', [
    'echo "$(gti status; grep main)"',
    'echo `gti status; grep main`',
])
def test_nested_substitutions_inside_words_are_structured(script):
    model = parse(script)
    nested = [token for token in model.segments[0].tokens
              if token.kind == 'substitution'][0]

    assert [segment.command.text for segment in nested.children] == [
        'gti', 'grep']


def test_powershell_call_operator_is_not_a_background_separator():
    model = parse("& 'C:/Program Files/tool' ; gti status", 'powershell')

    commands = [(segment.command.text if segment.command else None,
                 segment.separator) for segment in model.segments]
    assert commands == [('&', ';'), ('gti', None)]


@pytest.mark.parametrize('shell_name, script', [
    ('posix', "echo 'unterminated"),
    ('powershell', 'Write-Output `'),
    ('posix', 'echo $(gti status'),
])
def test_incomplete_syntax_is_retained_and_marked(shell_name, script):
    model = parse(script, shell_name)

    assert not model.complete
    assert model.segments
    assert script[model.segments[0].start:model.segments[0].end]


def test_replacement_uses_the_original_span():
    model = parse("echo 'keep this' && gti  status")
    token = model.segments[1].command

    assert replace_span(model.script, token, 'git') == (
        "echo 'keep this' && git  status")


def test_non_string_scripts_are_rejected():
    with pytest.raises(TypeError):
        parse(['echo', 'hi'])


def test_a_substitution_inside_quotes_keeps_the_rest_of_the_word():
    """`echo "a $(b) c" && git st`: the ` c"` after the substitution used to be
    dropped, which left the first segment ending in an unbalanced quote."""
    from thebleep.command_model import parse

    model = parse('echo "a $(b) c" && git st', 'posix')
    assert model.complete
    first = model.segments[0]
    assert 'echo "a $(b) c"' == 'echo "a $(b) c" && git st'[first.start:first.end]
    assert [token.kind for token in first.tokens] == [
        'word', 'word', 'substitution', 'word']
