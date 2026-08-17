"""The alias loader keeps Python out of shell startup, so what has to be
proven is that a shell set up this way still corrects commands: the stub has to
replace itself with the real alias and pass the arguments along, in a real
shell, for each shell we generate one for.
"""

import pytest
from tests.functional.plots import with_confirmation, without_confirmation, \
    history_changed

python_3 = (u'thebleep/python3', u'', u'sh')

init_bashrc = u'''echo '
export SHELL=/bin/bash
export PS1="$ "
echo > $HISTFILE
eval "$(thebleep --alias-loader)"
' > ~/.bashrc'''

init_zshrc = u'''echo '
export SHELL=/usr/bin/zsh
export HISTFILE=~/.zsh_history
echo > $HISTFILE
export SAVEHIST=100
export HISTSIZE=100
eval "$(thebleep --alias-loader)"
setopt INC_APPEND_HISTORY
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


@pytest.fixture
def fish(spawnu, TIMEOUT):
    proc = spawnu(u'thebleep/python3', u'', u'fish')
    proc.sendline(u'thebleep --alias-loader > ~/.config/fish/config.fish')
    proc.sendline(u'fish')
    return proc


@pytest.mark.functional
def test_bash_corrects_after_loading(bash, TIMEOUT):
    with_confirmation(bash, TIMEOUT)
    history_changed(bash, TIMEOUT, u'echo test')


@pytest.mark.functional
def test_bash_corrects_twice(bash, TIMEOUT):
    """The second correction uses the alias the first one defined."""
    without_confirmation(bash, TIMEOUT)
    without_confirmation(bash, TIMEOUT)


@pytest.mark.functional
def test_zsh_corrects_after_loading(zsh, TIMEOUT):
    with_confirmation(zsh, TIMEOUT)
    history_changed(zsh, TIMEOUT, u'echo test')


@pytest.mark.functional
def test_fish_corrects_after_loading(fish, TIMEOUT):
    with_confirmation(fish, TIMEOUT)
