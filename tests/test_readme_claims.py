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
