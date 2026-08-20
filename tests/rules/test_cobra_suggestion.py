# -*- encoding: utf-8 -*-

"""One rule for every tool built with cobra.

Captured from gh 2.63.2, helm 3.16.3 and kubectl 1.31.0. `gh` and `helm` have no
rule of their own in this project; they are corrected because the rule reads
cobra rather than reading a tool.

"""

import pytest
from thebleep.rules.cobra_suggestion import match, get_new_command
from thebleep.types import Command

# gh writes no prefix at all.
GH = (
    'unknown command "reop" for "gh"\n'
    '\n'
    'Did you mean this?\n'
    '\trepo\n'
    '\n'
    'Usage:  gh <command> <subcommand> [flags]\n'
)

# ...and offers several, one per line.
GH_MANY = (
    'unknown command "ise" for "gh"\n'
    '\n'
    'Did you mean this?\n'
    '\tgist\n'
    '\tissue\n'
    '\n'
    'Usage:  gh <command> <subcommand> [flags]\n'
)

# helm writes `Error:`.
HELM = (
    'Error: unknown command "instal" for "helm"\n'
    '\n'
    'Did you mean this?\n'
    '\tinstall\n'
    '\n'
    "Run 'helm --help' for usage.\n"
)

# kubectl writes `error:`.
KUBECTL = (
    'error: unknown command "gat" for "kubectl"\n'
    '\n'
    'Did you mean this?\n'
    '\tget\n'
    '\tset\n'
)

# cobra offers nothing for a mistyped flag, so there is nothing to read.
UNKNOWN_FLAG = 'Error: unknown flag: --al\n'


class TestEveryPrefixInTheWild(object):
    @pytest.mark.parametrize('script, output, expected', [
        ('gh reop list', GH, 'gh repo list'),
        ('helm instal mychart', HELM, 'helm install mychart'),
        ('kubectl gat pods', KUBECTL, 'kubectl get pods'),
    ])
    def test_bare_capital_and_lowercase(self, script, output, expected):
        """`unknown command`, `Error: unknown command` and `error: unknown
        command` are all in use, and the program's own name is ignored."""
        command = Command(script, output)
        assert match(command)
        assert get_new_command(command)[0] == expected


class TestSeveralSuggestions(object):
    def test_each_is_offered(self):
        suggestions = get_new_command(Command('gh ise list', GH_MANY))
        assert 'gh gist list' in suggestions
        assert 'gh issue list' in suggestions

    def test_the_list_ends_at_the_blank_line(self):
        """`Usage:` follows the suggestions, and is not one of them."""
        assert not any('Usage' in suggestion for suggestion
                       in get_new_command(Command('gh ise list', GH_MANY)))


class TestNotMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('helm ls --al', UNKNOWN_FLAG),
        ('helm ls', ''),
        # A clap tool, which `clap_suggestion` owns.
        ('ruff chekc .', "error: unrecognized subcommand 'chekc'\n\n"
                         "  tip: a similar subcommand exists: 'check'\n"),
    ])
    def test_it_says_nothing(self, script, output):
        assert not match(Command(script, output))


def test_a_suggestion_is_quoted():
    """Read out of output, handed to a shell. See `tests/test_injection.py`."""
    hostile = HELM.replace('install', 'install;>PWNED')
    suggestions = get_new_command(Command('helm instal mychart', hostile))
    assert "helm 'install;>PWNED' mychart" in suggestions
    assert 'helm install;>PWNED mychart' not in suggestions
