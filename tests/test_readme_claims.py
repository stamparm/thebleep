# -*- coding: utf-8 -*-

"""The README is part of the product, so its strong claims are checked here.

Not its prose -- its numbers and its lists, which are the parts that go out of
step with the code without anybody noticing. A README that counts thirty fixes
and links twenty-six is worse than one that counts nothing.

"""

import io
import re
import pytest

WORDS = {
    'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27,
    'twenty-eight': 28, 'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31,
    'thirty-two': 32, 'thirty-three': 33,
}

UPSTREAM_ISSUE = re.compile(r'nvbn/thefuck/issues/(\d+)')


@pytest.fixture
def readme(source_root):
    with io.open(str(source_root.joinpath('README.md')),
                 encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture
def linked(readme):
    return set(UPSTREAM_ISSUE.findall(readme))


def test_the_number_of_fixed_issues_is_the_number_it_links(readme, linked):
    """Two places say how many, in digits and in words. Both have to be it."""
    stated = re.search(r'\*\*(\d+) issues from \*The Fuck\*', readme)
    assert stated, "the README no longer says how many issues are fixed"
    assert int(stated.group(1)) == len(linked)

    in_words = re.search(r'rather than a claim in a README\.\s+(\S+)\n',
                         readme)
    assert in_words, 'the "What\'s fixed" wording changed shape'
    word = in_words.group(1).lower()
    assert word in WORDS, 'unrecognised number word: {}'.format(word)
    assert WORDS[word] == len(linked)


def test_the_changelog_links_the_same_issues(source_root, linked):
    """Anything the README claims should be in the changelog too.

    The changelog is what a person reads to find out what changed; three of the
    thirty are about the test suite rather than the tool, so it is the README
    that carries those.

    """
    with io.open(str(source_root.joinpath('CHANGELOG.md')),
                 encoding='utf-8') as handle:
        changelog = set(UPSTREAM_ISSUE.findall(handle.read()))
    missing = linked - changelog
    assert missing <= {'1344', '1523', '1550', '798'}, sorted(missing)


def test_the_python_versions_are_the_ones_setup_py_allows(readme, source_root):
    with io.open(str(source_root.joinpath('setup.py')),
                 encoding='utf-8') as handle:
        setup = handle.read()
    classified = set(re.findall(
        r"'Programming Language :: Python :: (\d+\.\d+)'", setup))
    assert classified, 'setup.py classifies no Python versions'

    table = re.search(r'\|\s+\*\*Python\*\*\s+\|([^|]+)\|', readme)
    assert table, "the README's Python row changed shape"
    promised = set(re.findall(r'\d+\.\d+', table.group(1)))
    assert promised == classified

    floor = re.search(r"python_requires='>=(\d+\.\d+)'", setup)
    assert floor and floor.group(1) == min(classified, key=lambda v: [
        int(part) for part in v.split('.')])


def test_the_shells_it_claims_are_the_shells_it_has(readme):
    from thebleep import shells

    table = re.search(r'\|\s+\*\*Shells\*\*\s+\|([^|]+)\|', readme)
    assert table, "the README's Shells row changed shape"
    promised = {word.strip().strip('*`').lower()
                for word in re.split(r',|and', table.group(1))
                if word.strip()}
    # `csh` and `pwsh` are the same drivers under other names.
    known = {name.lower() for name in shells.shells} | {'powershell'}
    assert promised <= known, sorted(promised - known)


def test_the_settings_it_documents_are_the_settings_there_are(readme):
    """A documented setting that does not exist is a setting that does nothing.

    Read from the Settings section alone: the rule list is a bulleted list of
    backticked names too, and those are rules rather than settings.

    """
    from thebleep import const

    section = readme[readme.index('\n## Settings'):]
    section = section[:section.index('\n## ', 1)]
    documented = set(re.findall(r'^\* `([a-z_]+)`', section, re.MULTILINE))
    assert documented, 'no settings were found to check'
    assert documented <= set(const.DEFAULT_SETTINGS), \
        sorted(documented - set(const.DEFAULT_SETTINGS))


def test_every_setting_is_documented(readme):
    from thebleep import const

    section = readme[readme.index('\n## Settings'):]
    section = section[:section.index('\n## ', 1)]
    documented = set(re.findall(r'`([a-z_]+)`', section))
    assert set(const.DEFAULT_SETTINGS) <= documented, \
        sorted(set(const.DEFAULT_SETTINGS) - documented)


def test_the_environment_variables_it_documents_exist(readme):
    from thebleep import const

    documented = set(re.findall(r'`(THEBLEEP_[A-Z_]+)`', readme))
    real = set(const.ENV_TO_ATTR) | {'THEBLEEP_OVERRIDDEN_ALIASES',
                                     'THEBLEEP_ARGUMENT_PLACEHOLDER',
                                     'THEBLEEP_OUTPUT_LOG',
                                     'THEBLEEP_NO_RULE_PACK'}
    assert documented <= real, sorted(documented - real)


def _heading_anchors(readme):
    """The anchors GitHub makes from the README's own headings.

    Lowercased, punctuation dropped, spaces hyphenated -- which is the rule
    GitHub applies, and the reason a heading is a better link target than a
    hand-written `<a name=...>`.

    """
    anchors = set()
    for heading in re.findall(r'^#{1,6} +(.+?) *$', readme, re.MULTILINE):
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        anchors.add(slug)
    return anchors


def test_the_readme_links_the_package_prints_go_somewhere(source_root, readme):
    """`logs` tells people to read a section of this README.

    It used to name `#manual-installation`, which was not a heading at all: the
    README carried a hand-written `<a name='manual-installation'>#</a>` for it,
    which rendered as a stray `#` above the heading it was standing in for.

    """
    anchors = _heading_anchors(readme)
    fragments = set()
    for path in source_root.joinpath('thebleep').rglob('*.py'):
        with io.open(str(path), encoding='utf-8') as handle:
            fragments.update(re.findall(
                r'github\.com/stamparm/thebleep#([\w-]+)', handle.read()))

    assert fragments, 'no README links were found in the package to check'
    assert fragments <= anchors, sorted(fragments - anchors)


def test_the_readme_does_not_hand_write_anchors(readme):
    """A hand-written anchor renders as a stray `#` and needs maintaining."""
    assert '<a name=' not in readme
    assert "<a href='#" not in readme
