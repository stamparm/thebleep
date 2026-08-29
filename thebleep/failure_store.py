"""A small, bounded record of recent failed commands.

This is deliberately local and best-effort. It gives ``--pick`` a useful
memory without making the correction path depend on a writable cache or on a
second execution of the command that failed.
"""

import os
import time

from . import cachefile


FINGERPRINT = ('failure-ring', 1)
LIMIT = 5
MAX_OUTPUT = 1024 * 1024
MAX_SCRIPT = 32 * 1024
MAX_CWD = 4096
MAX_SHELL = 64


def _byte_length(value):
    """Return the size of text as it will be stored on disk."""
    return len(value.encode('utf-8'))


def _clip_output(output):
    """Keep the beginning and end of output while bounding the record."""
    if not isinstance(output, str) or _byte_length(output) <= MAX_OUTPUT:
        return output if isinstance(output, str) else ''
    marker = '\n...[output clipped]...\n'
    size = MAX_OUTPUT - _byte_length(marker)
    head = size // 2
    raw = output.encode('utf-8')
    beginning = raw[:head].decode('utf-8', 'ignore')
    ending = raw[-(size - head):].decode('utf-8', 'ignore')
    return beginning + marker + ending


def _valid(entry):
    """Whether a cache value has the shape this module writes."""
    return (isinstance(entry, dict)
            and isinstance(entry.get('script'), str)
            and entry['script'].strip()
            and len(entry['script']) <= MAX_SCRIPT
            and isinstance(entry.get('output'), str)
            and _byte_length(entry['output']) <= MAX_OUTPUT
            and isinstance(entry.get('cwd'), str)
            and len(entry['cwd']) <= MAX_CWD
            and isinstance(entry.get('shell'), str)
            and len(entry['shell']) <= MAX_SHELL
            and type(entry.get('exit')) is int
            and isinstance(entry.get('saved_at'), (int, float)))


def load():
    """Returns recent failures, newest first."""
    value = cachefile.load('failures', FINGERPRINT)
    if not isinstance(value, list):
        return []
    return [entry for entry in value if _valid(entry)][:LIMIT]


def record(script, output, exit_status, cwd=None, shell_name=None):
    """Records a failed command, quietly doing nothing when it cannot."""
    try:
        status = int(exit_status)
    except (TypeError, ValueError):
        return
    if (status == 0 or not isinstance(script, str) or not script.strip()
            or len(script) > MAX_SCRIPT):
        return

    if cwd is None:
        try:
            saved_cwd = os.getcwd()
        except OSError:
            saved_cwd = ''
    else:
        saved_cwd = (cwd if isinstance(cwd, str) and len(cwd) <= MAX_CWD
                     else '')
    saved_shell = (shell_name if isinstance(shell_name, str)
                   and len(shell_name) <= MAX_SHELL else '')
    entry = {'script': script,
             'output': _clip_output(output),
             'cwd': saved_cwd,
             'shell': saved_shell,
             'exit': status,
             'saved_at': time.time()}
    entries = load()
    if entries and all(entry[key] == entries[0][key]
                       for key in ('script', 'output', 'cwd', 'shell', 'exit')):
        entries.pop(0)
    cachefile.save('failures', FINGERPRINT, [entry] + entries[:LIMIT - 1])


def forget(number):
    """Removes one stored failure by its current list number."""
    entries = load()
    if type(number) is not int or number < 1 or number > len(entries):
        return False
    entries.pop(number - 1)
    cachefile.save('failures', FINGERPRINT, entries)
    return True


def print_recent(entries=None):
    """Prints a compact, stable list for a human choosing a failure."""
    def display(value):
        """Keep stored terminal input on one harmless, readable line."""
        from .utils import without_control_sequences

        value = without_control_sequences(value)
        return ''.join(
            char if ord(char) >= 0x20 and ord(char) != 0x7f
            else '\\n' if char == '\n'
            else '\\r' if char == '\r'
            else '\\t' if char == '\t'
            else '\\x{:02x}'.format(ord(char))
            for char in value)

    if entries is None:
        entries = load()
    if not entries:
        print('No recorded failures.')
        return
    print('Recent failures:')
    for index, entry in enumerate(entries, 1):
        print('{:>2}  {}  (exit {}, {})'.format(
            index, display(entry['script']), entry['exit'],
            display(entry['cwd'])))
