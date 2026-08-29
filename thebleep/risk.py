# -*- encoding: utf-8 -*-

"""Conservative risk markers for structured suggestions.

This is a review hint, not a shell-security proof. A low result means that no
marker this small scanner knows about appeared in the suggested command; it
does not mean that running the command is safe.
"""

import re


_MARKERS = (
    ('privilege escalation', re.compile(r'\b(?:sudo|doas)\b', re.IGNORECASE)),
    ('destructive command', re.compile(
        r'\b(?:rm|rmdir|unlink|shred|mkfs|dd)\b', re.IGNORECASE)),
    ('safety bypass', re.compile(
        r'(?<![\w-])--(?:force|hard|no-verify|insecure|delete|purge)\b',
        re.IGNORECASE)),
)


def assess(corrected_command):
    """Return a conservative risk level and the markers behind it."""
    factors = ['side effect'] if corrected_command.side_effect else []
    factors.extend(label for label, marker in _MARKERS
                   if marker.search(corrected_command.script))
    return {'level': 'high' if factors else 'low', 'factors': factors}
