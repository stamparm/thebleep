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
    # Wait until readline has the terminal: a `\r` typed ahead of it reaches
    # a tty still in canonical mode, which turns it into a newline -- ctrl+j,
    # the key that is deliberately not bound. The marker's output comes after
    # readline read the line, so the prompt after it is readline's own.
    proc.sendline(u'echo READY_$(echo)NOW')
    assert proc.expect([TIMEOUT, u'READY_NOW'])
    assert proc.expect([TIMEOUT, u'\\$ '])
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
def xonsh(spawnu, TIMEOUT):
    proc = spawnu(*python_3)
    proc.sendline(u'mkdir -p ~/.config/xonsh; '
                  u'thebleep --shell xonsh --alias-loader --ambient '
                  u'> ~/.config/xonsh/rc.xsh')
    proc.sendline(u'xonsh')
    # xonsh loses what is typed while it starts up, and with an rc file it
    # prints no welcome: wait for the prompt, then prove it answers.
    assert proc.expect([TIMEOUT, u'@#'])
    proc.sendline(u'print("READY_" + "NOW")')
    assert proc.expect([TIMEOUT, u'READY_NOW'])
    assert proc.expect([TIMEOUT, u'@#'])
    return proc


@pytest.fixture
def elvish(spawnu, TIMEOUT):
    proc = spawnu(*python_3)
    proc.sendline(u'mkdir -p ~/.config/elvish; '
                  u'thebleep --shell elvish --alias-loader --ambient '
                  u'> ~/.config/elvish/rc.elv')
    proc.sendline(u'elvish')
    proc.sendline(u'echo READY_(echo)NOW')
    assert proc.expect([TIMEOUT, u'READY_NOW'])
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
def test_bash_runs_the_typo_and_offers_the_fix_at_the_next_prompt(
        bash, TIMEOUT):
    """Return is not bound in bash -- a `bind -x` on it redrew the prompt
    after every command -- so the typo runs, fails with bash's own message,
    and the fix is waiting at the next prompt."""
    bash.send(u'gti --version\r')
    assert bash.expect([TIMEOUT, u'gti: command not found'])
    assert bash.expect([TIMEOUT, u'\\$ git --version'])
    bash.send(u'\r')
    assert bash.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_bash_ctrl_j_runs_the_line_and_offers_the_fix_at_the_next_prompt(
        bash, TIMEOUT):
    """`sendline` ends with a newline, which is ctrl+j, which is not bound:
    the line runs and fails as it always did, and the handler underneath
    leaves the fix at the next prompt."""
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


wait_for_socket = (u'for i in 1 2 3 4 5 6 7 8 9 10; do '
                   u'[ -S ~/.cache/thebleep/serve/inline-{0}.sock ] '
                   u'&& break; sleep 1; done; '
                   u'[ -S ~/.cache/thebleep/serve/inline-{0}.sock ] '
                   u'&& echo SOCKET_$(echo)UP')


@pytest.mark.functional
def test_bash_asks_the_warm_server_through_the_bare_interpreter(bash,
                                                                TIMEOUT):
    """The container has neither `socat` nor `nc`, so once the socket is
    there the question goes through `python -S -I -c` and `serve.CLIENT`.
    The proof: `thebleep` itself is shadowed by a function that fails, so
    only the socket can have answered the second miss."""
    bash.sendline(u'gti --version')
    assert bash.expect([TIMEOUT, u'\\$ git --version'])
    bash.send(u'\r')
    assert bash.expect([TIMEOUT, u'git version'])
    bash.sendline(wait_for_socket.format(u'bash'))
    assert bash.expect([TIMEOUT, u'SOCKET_UP'])
    bash.sendline(u'thebleep() { return 1; }')
    bash.send(u'gti --version\r')
    assert bash.expect([TIMEOUT, u'gti: command not found'])
    assert bash.expect([TIMEOUT, u'\\$ git --version'])
    bash.send(u'\r')
    assert bash.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_bash_leaves_a_known_program_to_say_what_is_wrong(bash, TIMEOUT):
    """`git satus` runs and git says so: nothing in bash looks at a line
    before it runs any more."""
    bash.send(u'git satus\r')
    assert bash.expect([TIMEOUT, u"'satus' is not a git command"])


def typed(proc, text, pause=0.08):
    """Type `text` a character at a time, as a person does."""
    import time

    for character in text:
        proc.send(character)
        time.sleep(pause)


@pytest.mark.functional
def test_zsh_shows_the_fix_while_the_line_is_typed(zsh, TIMEOUT):
    """With the server up, the message is there before return is pressed,
    follows the line as it grows, and return takes the answer it already
    has."""
    zsh.send(u'gti --version\r')
    assert zsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'git version'])
    zsh.sendline(wait_for_socket.format(u'zsh'))
    assert zsh.expect([TIMEOUT, u'SOCKET_UP'])
    typed(zsh, u'gti --vers')
    assert zsh.expect([TIMEOUT, u'return runs `git --vers`'])
    typed(zsh, u'ion')
    assert zsh.expect([TIMEOUT, u'return runs `git --version`'])
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'ctrl\\+_ puts yours back'])
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'git version'])
    # The second word too.
    typed(zsh, u'git satus')
    assert zsh.expect([TIMEOUT, u'satus is not a git command; '
                                u'return runs `git status`'])
    zsh.send(u'\r')
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'not a git repository'])
    # A line the shell knows shows nothing and runs as typed.
    typed(zsh, u'echo un$(true)touched')
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'untouched'])


@pytest.mark.functional
def test_zsh_corrects_the_second_word_once_the_server_is_up(zsh, TIMEOUT):
    """`git satus`: git is a command, so the shell's own check passes; the
    warm server reads git's manual pages in the container and answers."""
    zsh.send(u'gti --version\r')
    assert zsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    zsh.send(u'\r')
    assert zsh.expect([TIMEOUT, u'git version'])
    zsh.sendline(wait_for_socket.format(u'zsh'))
    assert zsh.expect([TIMEOUT, u'SOCKET_UP'])
    zsh.send(u'git satus\r')
    assert zsh.expect([TIMEOUT, u'bleep: satus is not a git command'])
    zsh.send(u'\r')
    # `git status` ran, outside any repository.
    assert zsh.expect([TIMEOUT, u'not a git repository'])
    # A line git has is accepted as it was.
    zsh.send(u'git version\r')
    assert zsh.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_fish_corrects_the_second_word_once_the_server_is_up(fish, TIMEOUT):
    fish.send(u'gti --version\r')
    assert fish.expect([TIMEOUT, u'bleep: gti is not a command'])
    fish.send(u'\r')
    assert fish.expect([TIMEOUT, u'git version'])
    fish.sendline(u'sh -c ' + repr(wait_for_socket.format(u'fish')))
    assert fish.expect([TIMEOUT, u'SOCKET_UP'])
    fish.send(u'git satus\r')
    assert fish.expect([TIMEOUT, u'bleep: satus is not a git command'])
    assert fish.expect([TIMEOUT, shown(u'git status')])
    fish.send(u'\r')
    assert fish.expect([TIMEOUT, u'not a git repository'])
    fish.send(u'git version\r')
    assert fish.expect([TIMEOUT, u'git version'])


@pytest.mark.functional
def test_xonsh_puts_the_fix_in_the_next_prompt(xonsh, TIMEOUT):
    """`on_transform_command` runs nothing for the typo, prints the message
    and fills the next prompt through `$XONSH_PROMPT_NEXT_CMD`; return then
    runs the fix. With the server up, the second word too."""
    xonsh.send(u'gti --version\r')
    assert xonsh.expect([TIMEOUT, u'bleep: gti is not a command'])
    xonsh.send(u'\r')
    assert xonsh.expect([TIMEOUT, u'git version'])
    xonsh.sendline(u'echo un$(true)touched')
    assert xonsh.expect([TIMEOUT, u'untouched'])
    xonsh.sendline(u'$(sh -c ' + repr(wait_for_socket.format(u'xonsh')) + u')')
    assert xonsh.expect([TIMEOUT, u'SOCKET_UP'])
    xonsh.send(u'git satus\r')
    assert xonsh.expect([TIMEOUT, u'bleep: satus is not a git command'])
    xonsh.send(u'\r')
    assert xonsh.expect([TIMEOUT, u'not a git repository'])
    # Python stays Python.
    xonsh.sendline(u'x = 20 + 1')
    xonsh.sendline(u'print(x * 2)')
    assert xonsh.expect([TIMEOUT, u'42'])


@pytest.mark.functional
def test_elvish_replaces_the_line_before_anything_runs(elvish, TIMEOUT):
    elvish.send(u'gti --version\r')
    assert elvish.expect([TIMEOUT, u'bleep: gti is not a command'])
    elvish.send(u'\r')
    assert elvish.expect([TIMEOUT, u'git version'])
    elvish.sendline(u'sh -c ' + repr(wait_for_socket.format(u'elvish')))
    assert elvish.expect([TIMEOUT, u'SOCKET_UP'])
    elvish.send(u'git satus\r')
    assert elvish.expect([TIMEOUT, u'bleep: satus is not a git command'])
    elvish.send(u'\r')
    assert elvish.expect([TIMEOUT, u'not a git repository'])
    elvish.send(u'echo un(echo)touched\r')
    assert elvish.expect([TIMEOUT, u'untouched'])


@pytest.mark.functional
def test_fish_asks_the_warm_server_through_the_bare_interpreter(fish,
                                                                TIMEOUT):
    fish.send(u'gti --version\r')
    assert fish.expect([TIMEOUT, u'bleep: gti is not a command'])
    fish.send(u'\r')
    assert fish.expect([TIMEOUT, u'git version'])
    fish.sendline(u'sh -c ' + repr(wait_for_socket.format(u'fish')))
    assert fish.expect([TIMEOUT, u'SOCKET_UP'])
    fish.sendline(u'function thebleep; return 1; end')
    fish.send(u'gti --version\r')
    assert fish.expect([TIMEOUT, u'bleep: gti is not a command'])
    fish.send(u'\r')
    assert fish.expect([TIMEOUT, u'git version'])
