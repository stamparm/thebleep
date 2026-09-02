"""Correcting a misspelled program without `bleep` being typed.

Each shell is set up with the alias loader and `--ambient`, then given `gti
--version`. What has to be proven, in a real terminal, is that the corrected
command is on the line before anything ran, and that return then runs it.

"""

import pytest

from tests.functional.plots import shown

python_3 = (u'thebleep/python3', u'', u'sh')

init_bashrc = u'''echo '
export SHELL=/bin/bash
export PS1="$ "
echo > $HISTFILE
eval "$(thebleep --alias-loader)"
eval "$(TB_SHELL=bash thebleep --ambient)"
' > ~/.bashrc'''

init_zshrc = u'''echo '
export SHELL=/usr/bin/zsh
export HISTFILE=~/.zsh_history
echo > $HISTFILE
export SAVEHIST=100
export HISTSIZE=100
eval "$(thebleep --alias-loader)"
eval "$(TB_SHELL=zsh thebleep --ambient)"
' > ~/.zshrc'''


@pytest.fixture
def bash(spawnu, TIMEOUT):
    proc = spawnu(*python_3)
    proc.sendline(init_bashrc)
    proc.sendline(u'bash')
    return proc


@pytest.fixture
def zsh(spawnu, TIMEOUT):
    proc = spawnu(*python_3)
    proc.sendline(init_zshrc)
    proc.sendline(u'zsh')
    return proc


init_zshrc_warm = init_zshrc.replace(
    u'eval "$(TB_SHELL=zsh thebleep --ambient)"',
    u'eval "$(THEBLEEP_WARM_SERVER=true TB_SHELL=zsh thebleep --ambient)"')


@pytest.fixture
def warm_zsh(spawnu, TIMEOUT):
    proc = spawnu(*python_3)
    proc.sendline(init_zshrc_warm)
    proc.sendline(u'zsh')
    return proc


@pytest.fixture
def fish(spawnu, TIMEOUT):
    proc = spawnu(u'thebleep/python3', u'', u'fish')
    proc.sendline(u'thebleep --alias-loader > ~/.config/fish/config.fish')
    proc.sendline(u'TB_SHELL=fish thebleep --ambient >> '
                  u'~/.config/fish/config.fish')
    proc.sendline(u'fish')
    return proc


@pytest.mark.functional
def test_bash_offers_the_fix_at_the_next_prompt(bash, TIMEOUT):
    bash.sendline(u'gti --version')
    assert bash.expect([TIMEOUT, u'gti: command not found'])
    # The corrected line, already in readline at the user's own prompt.
    assert bash.expect([TIMEOUT, u'\\$ git --version'])
    bash.send(u'\r')
    assert bash.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_bash_leaves_a_known_command_alone(bash, TIMEOUT):
    # `un$(true)touched`: the word appears in the output and not in the
    # echoed command line, so matching it means the command ran.
    bash.sendline(u'echo un$(true)touched')
    assert bash.expect([TIMEOUT, u'untouched'])


@pytest.mark.functional
def test_zsh_replaces_the_line_before_anything_runs(zsh, TIMEOUT):
    zsh.send(u'gti --version\r')
    assert zsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_zsh_leaves_a_known_command_alone(zsh, TIMEOUT):
    zsh.send(u'echo un$(true)touched\r')
    assert zsh.expect([TIMEOUT, u'untouched'])


@pytest.mark.functional
def test_fish_replaces_the_line_before_anything_runs(fish, TIMEOUT):
    fish.send(u'gti --version\r')
    assert fish.expect([TIMEOUT, u'bleep: gti is not a command'])
    assert fish.expect([TIMEOUT, shown(u'git --version')])
    fish.send(u'\r')
    assert fish.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_fish_leaves_a_known_command_alone(fish, TIMEOUT):
    # `(echo)` and not `(true)`: a fish substitution that prints nothing is
    # an empty list, and a word joined to an empty list is no word at all.
    fish.send(u'echo un(echo)touched\r')
    assert fish.expect([TIMEOUT, u'untouched'])


@pytest.mark.functional
def test_zsh_asks_the_warm_server_once_it_is_up(warm_zsh, TIMEOUT):
    """The first miss starts the server and is answered by Python; the socket
    is then there, and the second miss is answered over it."""
    warm_zsh.send(u'gti --version\r')
    assert warm_zsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    warm_zsh.send(u'\r')
    assert warm_zsh.expect([TIMEOUT, u'git version'])
    warm_zsh.sendline(u'for i in 1 2 3 4 5 6 7 8 9 10; do '
                      u'[[ -S ~/.cache/thebleep/serve/inline-zsh.sock ]] '
                      u'&& break; sleep 1; done; '
                      u'[[ -S ~/.cache/thebleep/serve/inline-zsh.sock ]] '
                      u'&& echo SOCKET_$(echo)UP')
    assert warm_zsh.expect([TIMEOUT, u'SOCKET_UP'])
    warm_zsh.send(u'gti --version\r')
    assert warm_zsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    warm_zsh.send(u'\r')
    assert warm_zsh.expect([TIMEOUT, u'git version'])
    # And the server, not a fresh Python, was what answered: the only
    # `--inline` process a hit could have started is none.
    warm_zsh.sendline(u'pgrep -fc "thebleep --serve" && echo SERVER_$(echo)RUNS')
    assert warm_zsh.expect([TIMEOUT, u'SERVER_RUNS'])
