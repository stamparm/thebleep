# -*- encoding: utf-8 -*-

"""Every fixture here came off a real kubectl, v1.36.3.

The hand-written ones this replaces were close but not right, in a way that
mattered: `kubectl gat` was written as suggesting only `get`, and kubectl in fact
suggests `set`, `get` and `wait` -- three of them, with the useful one second. A
rule built against invented output is how most of the rules inherited from The
Fuck came to stop matching.

"""

import pytest
from thebleep.rules.kubectl_unknown_command import (
    _get_suggestions, get_new_command, match)
from thebleep.types import Command

# `kubectl gat pods`. Three suggestions, tab-indented, and `get` is not first.
MANY = ('error: unknown command "gat" for "kubectl"\n'
        '\n'
        'Did you mean this?\n'
        '\tset\n'
        '\tget\n'
        '\twait\n'
        '\n')

# `kubectl decsribe pod my-pod`.
ONE = ('error: unknown command "decsribe" for "kubectl"\n'
       '\n'
       'Did you mean this?\n'
       '\tdescribe\n'
       '\n')

# `kubectl aply -f deploy.yaml`.
APPLY = ('error: unknown command "aply" for "kubectl"\n'
         '\n'
         'Did you mean this?\n'
         '\tapply\n'
         '\n')

# `kubectl zzzzzz pods` -- nothing is close enough, so kubectl offers nothing.
NOTHING = 'error: unknown command "zzzzzz" for "kubectl"\n'


class TestReadingTheSuggestions(object):
    def test_several(self):
        assert _get_suggestions(MANY) == ['set', 'get', 'wait']

    def test_one(self):
        assert _get_suggestions(ONE) == ['describe']

    def test_none_offered(self):
        assert _get_suggestions(NOTHING) == []

    def test_the_rest_of_the_message_is_not_read_as_a_suggestion(self):
        """Anything non-blank that is not indented ends the block."""
        output = (MANY.rstrip('\n') + '\nSee "kubectl --help" for more.\n'
                  '    not-a-suggestion\n')
        assert _get_suggestions(output) == ['set', 'get', 'wait']


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('kubectl gat pods', MANY),
        ('kubectl decsribe pod my-pod', ONE),
        ('kubectl aply -f deploy.yaml', APPLY),
    ])
    def test_an_unknown_subcommand(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('kubectl get pods', ''),
        ('kubectl get pods', 'NAME     READY   STATUS\nmy-pod   1/1     Running'),
        # Somebody else's unknown command.
        ('vim gat', MANY),
        # A bare `kubectl` has no subcommand to be wrong, and `get_new_command`
        # reads `script_parts[1]`; this is what keeps it from being asked.
        ('kubectl', NOTHING),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_the_closest_suggestion_comes_first(self):
        """kubectl's own order puts `set` before `get` for `gat`."""
        assert get_new_command(Command('kubectl gat pods', MANY)) == [
            'kubectl get pods', 'kubectl wait pods', 'kubectl set pods']

    def test_one_suggestion(self):
        assert get_new_command(
            Command('kubectl decsribe pod my-pod', ONE)) == [
                'kubectl describe pod my-pod']

    def test_the_flags_are_kept(self):
        assert get_new_command(
            Command('kubectl aply -f deploy.yaml', APPLY)) == [
                'kubectl apply -f deploy.yaml']

    def test_a_flag_after_the_subcommand_is_kept(self):
        assert get_new_command(
            Command('kubectl decsribe pod my-pod -n kube-system', ONE)) == [
                'kubectl describe pod my-pod -n kube-system']

    def test_nothing_to_suggest(self):
        assert get_new_command(Command('kubectl zzzzzz pods', NOTHING)) == []

    def test_a_suggestion_is_quoted(self):
        """It came out of another program's output, and the result is eval'd.

        kubectl's own command list is not something an attacker reaches, so this
        is correctness by construction rather than a live hole -- the same reason
        every other rule that reads a name out of output quotes it.

        """
        # No space in the payload: a suggestion is one word, so a payload with
        # a space in it is not read as one and the test would prove nothing.
        hostile = MANY.replace('\tget\n', '\tget;>PWNED\n')
        suggestions = get_new_command(Command('kubectl gat pods', hostile))
        assert "kubectl 'get;>PWNED' pods" in suggestions
        assert 'kubectl get;>PWNED pods' not in suggestions
