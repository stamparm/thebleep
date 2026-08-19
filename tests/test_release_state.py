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


def test_the_release_date_is_today_and_not_the_last_commit(source_root):
    """`release.py` dated a release from `git log -1 --format=%cs`.

    Which is the date of the last commit, so a release prepared on Tuesday from
    a tree last touched on Friday said Friday -- a date the release did not
    happen on, in the one file people read to find out when it did.

    """
    import datetime
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'release_script', str(source_root.joinpath('release.py')))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.today() == datetime.date.today().isoformat()
    assert re.match(r'^\d{4}-\d{2}-\d{2}$', module.today())


def test_it_states_the_version_in_exactly_the_places_it_rewrites(source_root):
    """Every pattern in `release.py` has to rewrite exactly one line.

    Not "match exactly one line", which is what this asserted and which was only
    ever true while there had been one release: the CHANGELOG's heading pattern
    matches every heading in it, and gains one each time. What `release.py`
    depends on is what it actually does -- `subn(..., count=1)` -- so that is what
    is checked, and the first heading is the one that gets the new version.

    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'release_script', str(source_root.joinpath('release.py')))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, pattern, replacement in module.STATES_THE_VERSION:
        text = _read(source_root, name)
        if replacement is None:
            new, count = pattern.subn(r'\g<1>9.9.9\g<2>', text)
        else:
            new, count = pattern.subn(
                replacement.format(version='9.9.9', date='2099-01-01'),
                text, count=1)
        assert count == 1, \
            '{} has {} lines a release would rewrite, wanted 1'.format(
                name, count)
        assert '9.9.9' in new, '{} did not take the new version'.format(name)

    # And the one it rewrites in the CHANGELOG is the top one, not a historical
    # entry further down.
    changelog = _read(source_root, 'CHANGELOG.md')
    name, pattern, replacement = module.STATES_THE_VERSION[-1]
    assert name == 'CHANGELOG.md'
    rewritten = pattern.subn(
        replacement.format(version='9.9.9', date='2099-01-01'),
        changelog, count=1)[0]
    headings = CHANGELOG_HEADING.findall(rewritten)
    assert headings[0] == ('9.9.9', '2099-01-01'), headings[:2]
