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
    _answer(proc, TIMEOUT, u'\n', u'test')


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


def _answer(proc, TIMEOUT, key, expected, attempts=5, patience=8):
    """Sends an answer until the interactive process acknowledges it.

    Enter and Ctrl+C can arrive before raw mode is ready, just like the `y`
    used for replay. The terminal drops that first byte when it flushes its
    input queue, so a single send makes these tests depend on scheduling.
    """
    for _ in range(attempts):
        proc.send(key)
        if proc.expect([TIMEOUT, expected], timeout=patience):
            return
    raise AssertionError(
        'no {!r} after sending {!r} {} times'.format(
            expected, key, attempts))


def _agree(proc, TIMEOUT, expected, attempts=5, patience=8):
    """Answers the replay question, and keeps answering until it is heard.

    The first `y` can be thrown away, and that is deliberate on The Bleep's part
    rather than a bug to work around here. Reading the answer means putting the
    terminal into raw mode, and `tty.setraw` discards whatever was typed before
    it -- so a keystroke that arrived before the question was drawn is not read
    as consent to run a command again that "will change anything it changes
    twice". A person cannot answer a question they have not been shown yet; a
    test can, and does, in the fraction of a second between the prompt being
    flushed and raw mode being entered. On a loaded two-core runner that window
    is wide enough to lose in.

    The alternative -- flushing before drawing the prompt instead of after --
    was measured and rejected: it closes this window and opens the one that
    matters, where a keystroke from before the question *is* taken as the answer.

    So the fix belongs here, and it is to ask again.

    """
    _answer(proc, TIMEOUT, u'y', expected, attempts, patience)


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
        _agree(proc, TIMEOUT, u'git show')
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
    _answer(proc, TIMEOUT, u'\003', u'Aborted')


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
