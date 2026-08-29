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


def _clip_output(output):
    """Keep the beginning and end of output while bounding the record."""
    if not isinstance(output, str) or len(output) <= MAX_OUTPUT:
        return output if isinstance(output, str) else ''
    marker = '\n...[output clipped]...\n'
    size = MAX_OUTPUT - len(marker)
    head = size // 2
    return output[:head] + marker + output[-(size - head):]


def _valid(entry):
    """Whether a cache value has the shape this module writes."""
    return (isinstance(entry, dict)
            and isinstance(entry.get('script'), str)
            and isinstance(entry.get('output'), str)
            and isinstance(entry.get('cwd'), str)
            and isinstance(entry.get('shell'), str)
            and isinstance(entry.get('exit'), int)
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
    if status == 0 or not isinstance(script, str) or not script.strip():
        return

    entry = {'script': script,
             'output': _clip_output(output),
             'cwd': cwd if isinstance(cwd, str) else os.getcwd(),
             'shell': shell_name if isinstance(shell_name, str) else '',
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
    if entries is None:
        entries = load()
    if not entries:
        print('No recorded failures.')
        return
    print('Recent failures:')
    for index, entry in enumerate(entries, 1):
        print('{:>2}  {}  (exit {}, {})'.format(
            index, entry['script'], entry['exit'], entry['cwd']))
