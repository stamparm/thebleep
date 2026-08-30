import os
import shlex
import mmap
import re
from shutil import get_terminal_size
from ..exceptions import ScriptNotInLog
from .. import const, logs


def _group_by_calls(log):
    ps1 = os.environ['PS1']
    ps1_newlines = ps1.count('\\n') + ps1.count('\n')
    ps1_counter = 0

    script_line = None
    lines = []
    for line in log:
        if const.USER_COMMAND_MARK in line or ps1_counter > 0:
            if script_line and ps1_counter == 0:
                yield script_line, lines

            if ps1_newlines > 0:
                if ps1_counter <= 0:
                    ps1_counter = ps1_newlines
                else:
                    ps1_counter -= 1

            script_line = line
            lines = [line]
        elif script_line is not None:
            lines.append(line)

    if script_line:
        yield script_line, lines


def _words(script):
    """The words of the command, for looking it up in the recording.

    `shlex.split` raises on an unbalanced quote, and an unbalanced quote is
    exactly the sort of thing somebody asks to have fixed -- so it cannot be a
    crash. `rerun.py` has had this guard for the same reason; this reader did
    not, and a command with a `#` comment in it, or a stray `\'`, put a
    traceback on the screen instead of a correction. Falling back to whitespace
    is fine: these words are only being looked for in a line of the recording.

    """
    try:
        return shlex.split(script)
    except ValueError:
        return script.split()


def _wrapped_together(script_line, lines, width):
    """`script_line` and the rows the terminal wrapped it onto.

    A command longer than the terminal is wide is echoed across several rows,
    and the recording keeps them as separate lines -- so looking for every word
    of the command in one line found nothing, and instant mode gave up and asked
    to re-run the command instead. At eighty columns that was every command over
    about seventy-five characters, which is not an unusual thing to type.

    A row the terminal filled completely is the signal: it holds exactly `width`
    characters and the next row continues it, with no separator between them.
    A row shorter than that ended because the text did.

    """
    # Two things in a recorded row are not columns on the screen, and both of
    # them made a full row look like a short one so that nothing was ever
    # rejoined: the mark instant mode puts in `PS1`, which is ten zero-width
    # spaces the terminal gives no width to, and the carriage return the
    # recording keeps at the end of every line.
    def _columns(row):
        return row.replace(const.USER_COMMAND_MARK, '').rstrip('\r')

    text = _columns(script_line)
    for line in lines[1:]:
        if not text or len(text) % width:
            break
        text += _columns(line)

    return text


def _get_script_group_lines(grouped, script):
    def _word_continues(character):
        return bool(character) and not character.isspace() \
            and character not in "'\";&|(){}<>"

    def _find_word(text, word, start):
        while True:
            position = text.find(word, start)
            if position == -1:
                return -1
            before = text[position - 1] if position else ''
            after_at = position + len(word)
            after = text[after_at] if after_at < len(text) else ''
            if not _word_continues(before) and not _word_continues(after):
                return position
            start = position + 1

    parts = _words(script)
    width = max(get_terminal_size().columns, 1)

    for script_line, lines in reversed(grouped):
        joined = _wrapped_together(script_line, lines, width)
        # A line editor redraws a command with cursor movement between words.
        # Fish 4, for example, records `gti \r\x1b[21Cstatus`; searching that
        # raw stream makes the `C` at the end of the movement look like part of
        # the word before `status`. Strip presentation controls for matching,
        # while keeping the original stream for pyte to render below.
        from ..utils import without_control_sequences

        searchable = without_control_sequences(joined)
        position = 0
        for part in parts:
            position = _find_word(searchable, part, position)
            if position == -1:
                break
            position += len(part)
        else:
            return lines

    raise ScriptNotInLog


def _decode(raw):
    """The recording as text, from a window that can start anywhere.

    Two things make a plain `.decode()` wrong here, and both of them reach the
    user as a traceback rather than as a missed correction.

    The recording is a ring: once it is full, reading the last megabyte of it
    starts at whatever byte is a megabyte back, which lands in the middle of a
    character as often as the output has multibyte characters in it. The leading
    continuation bytes belong to a character whose first byte was overwritten, so
    they are dropped -- deliberately, and only at the front, where a partial
    character is the one thing the window's own boundary can create.

    Anything else undecodable is output that was never UTF-8: a command that
    printed a JPEG, a `cat` of a binary. Those bytes are replaced rather than
    raised on. Neither can invent or destroy a command boundary -- the mark
    instant mode puts in `PS1` is ten zero-width spaces, and a run of bytes that
    does not decode is not that.

    """
    start = 0
    while start < len(raw) and 0x80 <= raw[start] <= 0xbf:
        start += 1
    return raw[start:].decode('utf-8', 'replace')


def _get_output_lines(script, log_file):
    # Imported here because rendering a terminal is only needed in instant
    # mode, and pyte is one of the slowest imports we have.
    import pyte

    data = _decode(log_file.read())
    data = re.sub(r'\x00+$', '', data)
    lines = data.split('\n')
    grouped = list(_group_by_calls(lines))
    script_lines = _get_script_group_lines(grouped, script)
    screen = pyte.Screen(get_terminal_size().columns, len(script_lines))
    stream = pyte.Stream(screen)
    stream.feed('\n'.join(script_lines))
    return screen.display


def _skip_old_lines(log_file):
    size = os.path.getsize(os.environ['THEBLEEP_OUTPUT_LOG'])
    if size > const.LOG_SIZE_IN_BYTES:
        log_file.seek(size - const.LOG_SIZE_IN_BYTES)


def get_output(script):
    """Reads script output from log.

    :type script: str
    :rtype: str | None

    """
    if 'THEBLEEP_OUTPUT_LOG' not in os.environ:
        logs.warn("Output log isn't specified")
        return None

    if const.USER_COMMAND_MARK not in os.environ.get('PS1', ''):
        logs.warn(
            "PS1 doesn't contain user command mark, please ensure "
            "that PS1 is not changed after The Bleep alias initialization")
        return None

    try:
        with logs.debug_time(u'Read output from log'):
            # `access=ACCESS_READ` rather than `MAP_SHARED, PROT_READ`: it is
            # the same read-only shared mapping, spelled the way that exists on
            # both platforms. Neither of those constants is defined on Windows,
            # so this raised AttributeError there -- which nothing noticed,
            # because instant mode needs a pty and so is never switched on on
            # Windows, and until there was a test for this reader nothing called
            # it at all.
            #
            # Both handles are closed on the way out, which they were not. A
            # correction exits immediately afterwards so nothing leaked for long
            # -- but on Windows an open mapping keeps the file locked, and the
            # recording is a file somebody else is still writing to.
            fd = os.open(os.environ['THEBLEEP_OUTPUT_LOG'], os.O_RDONLY)
            try:
                # As much of the recording as there is, not as much as there
                # should be. The logger pre-writes the file to its full size
                # before using it, so a logger killed in between -- or a
                # recording from a version that sized it differently -- leaves
                # a file shorter than `LOG_SIZE_IN_BYTES`. Asking `mmap` for
                # more than the file holds raises `ValueError`, which nothing
                # here catches; asking for a region the file has not actually
                # been extended to is worse than that, because touching it
                # raises `SIGBUS` and kills the process outright.
                size = min(os.fstat(fd).st_size, const.LOG_SIZE_IN_BYTES)
                if size <= 0:
                    logs.warn("Output log is empty")
                    return None

                with mmap.mmap(fd, size, access=mmap.ACCESS_READ) as buffer:
                    _skip_old_lines(buffer)
                    lines = _get_output_lines(script, buffer)
            finally:
                os.close(fd)
            output = '\n'.join(lines).strip()
            logs.debug(u'Received output: {}'.format(output))
            return output
    except OSError:
        logs.warn("Can't read output log")
        return None
    except ScriptNotInLog:
        logs.warn("Script not found in output log")
        return None
