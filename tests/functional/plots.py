def _set_confirmation(proc, require):
    proc.sendline(u'mkdir -p ~/.thebleep')
    proc.sendline(
        u'echo "require_confirmation = {}" > ~/.thebleep/settings.py'.format(
            require))


def with_confirmation(proc, TIMEOUT):
    """Ensures that command can be fixed when confirmation enabled."""
    _set_confirmation(proc, True)

    proc.sendline(u'ehco test')

    proc.sendline(u'bleep')
    assert proc.expect([TIMEOUT, u'echo test'])
    assert proc.expect([TIMEOUT, u'enter'])
    assert proc.expect_exact([TIMEOUT, u'ctrl+c'])
    proc.send('\n')

    assert proc.expect([TIMEOUT, u'test'])


def history_changed(proc, TIMEOUT, *to):
    """Ensures that history changed."""
    proc.send('\033[A')
    pattern = [TIMEOUT]
    pattern.extend(to)
    assert proc.expect(pattern)


def history_not_changed(proc, TIMEOUT):
    """Ensures that history not changed."""
    proc.send('\033[A')
    assert proc.expect([TIMEOUT, u'bleep'])


def select_command_with_arrows(proc, TIMEOUT):
    """Ensures that command can be selected with arrow keys."""
    _set_confirmation(proc, True)

    proc.sendline(u'git h')
    assert proc.expect([TIMEOUT, u"git: 'h' is not a git command."])

    proc.sendline(u'bleep')
    # `git h` is not something we can show is harmless, so unless the output
    # was recorded as it ran — which is what instant mode does — running it
    # again has to be agreed to first.
    asked = proc.expect([TIMEOUT, u'Run it', u'git show'])
    assert asked
    if asked == 1:
        proc.send(u'y')
        assert proc.expect([TIMEOUT, u'git show'])
    proc.send('\033[B')
    assert proc.expect([TIMEOUT, u'git push'])
    proc.send('\033[B')
    assert proc.expect([TIMEOUT, u'git help', u'git hook'])
    proc.send('\033[A')
    assert proc.expect([TIMEOUT, u'git push'])
    proc.send('\033[B')
    assert proc.expect([TIMEOUT, u'git help', u'git hook'])
    proc.send('\n')

    assert proc.expect([TIMEOUT, u'usage', u'fatal: not a git repository'])


def refuse_with_confirmation(proc, TIMEOUT):
    """Ensures that fix can be refused when confirmation enabled."""
    _set_confirmation(proc, True)

    proc.sendline(u'ehco test')

    proc.sendline(u'bleep')
    assert proc.expect([TIMEOUT, u'echo test'])
    assert proc.expect([TIMEOUT, u'enter'])
    assert proc.expect_exact([TIMEOUT, u'ctrl+c'])
    proc.send('\003')

    assert proc.expect([TIMEOUT, u'Aborted'])


def without_confirmation(proc, TIMEOUT):
    """Ensures that command can be fixed when confirmation disabled."""
    _set_confirmation(proc, False)

    proc.sendline(u'ehco test')

    proc.sendline(u'bleep')
    assert proc.expect([TIMEOUT, u'echo test'])
    assert proc.expect([TIMEOUT, u'test'])


def how_to_configure(proc, TIMEOUT):
    proc.sendline(u'bleep')
    assert proc.expect([TIMEOUT, u"alias isn't configured"])
