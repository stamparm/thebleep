# -*- coding: utf-8 -*-

"""The repository's own account of what version it is.

Three places say it: setup.py, the README's badge and the CHANGELOG's top
heading. They have to agree, or one of them is lying to somebody -- and the
badge is the one a reader sees first.

The heading also says whether that version is out yet. Before it is published it
says `unreleased`, because a date in the future is a claim about something that
has not happened; `release.py` puts the date in when the release is prepared.

"""

import io
import re
import pytest

VERSION_IN_SETUP = re.compile(r"^VERSION = '([^']+)'$", re.MULTILINE)
VERSION_IN_BADGE = re.compile(
    r'^\[version-badge\]:\s+\S+/badge/version-([\d.]+)-', re.MULTILINE)
CHANGELOG_HEADING = re.compile(r'^## (\S+) — (.+)$', re.MULTILINE)
RELEASED = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _read(root, name):
    with io.open(str(root.joinpath(name)), encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture
def version(source_root):
    found = VERSION_IN_SETUP.search(_read(source_root, 'setup.py'))
    assert found, 'setup.py has no VERSION line'
    return found.group(1)


def test_the_badge_says_the_same_version(source_root, version):
    found = VERSION_IN_BADGE.search(_read(source_root, 'README.md'))
    assert found, "the README's version badge is not in the expected shape"
    assert found.group(1) == version


def test_the_changelog_leads_with_this_version(source_root, version):
    headings = CHANGELOG_HEADING.findall(_read(source_root, 'CHANGELOG.md'))
    assert headings, 'the CHANGELOG has no version headings'
    assert headings[0][0] == version


def test_the_changelog_says_unreleased_or_a_real_date(source_root):
    """Not a date in the future, which is what it said before this.

    A release that has not happened is `unreleased`. One that has says when.

    """
    headings = CHANGELOG_HEADING.findall(_read(source_root, 'CHANGELOG.md'))
    state = headings[0][1].strip()
    assert state == 'unreleased' or RELEASED.match(state), state


def test_every_released_version_has_a_date(source_root):
    headings = CHANGELOG_HEADING.findall(_read(source_root, 'CHANGELOG.md'))
    for name, state in headings[1:]:
        assert RELEASED.match(state.strip()), \
            '{} is not the top entry, so it should have a date'.format(name)
