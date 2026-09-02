# -*- coding: utf-8 -*-

"""The README is part of the product, so its strong claims are checked here.

Not its prose -- its numbers and its lists, which are the parts that go out of
step with the code without anybody noticing. A README that counts thirty fixes
and links twenty-six is worse than one that counts nothing.

"""

import io
import re
import subprocess
import pytest

WORDS = {
    'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27,
    'twenty-eight': 28, 'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31,
    'thirty-two': 32, 'thirty-three': 33,
}

# Both forms, because half of the thirty are pull requests nobody merged rather
# than issues, and a link that calls a pull request an issue is the sort of thing
# the README is checked for here. GitHub redirects either way, so nothing was
# broken -- it was just wrong.
UPSTREAM_ITEM = re.compile(r'nvbn/thefuck/(issues|pull)/(\d+)')


def _linked(text):
    return {number for _, number in UPSTREAM_ITEM.findall(text)}


def _read(source_root, name):
    with io.open(str(source_root.joinpath(name)), encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture
def readme(source_root):
    with io.open(str(source_root.joinpath('README.md')),
                 encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture
def linked(readme):
    return _linked(readme)


def test_the_number_of_fixed_issues_is_the_number_it_links(readme, linked):
    """Two places say how many, in digits and in words. Both have to be it."""
    stated = re.search(r'\*\*(\d+) items from \*The Fuck\*', readme)
    assert stated, "the README no longer says how many items are fixed"
    assert int(stated.group(1)) == len(linked)

    in_words = re.search(r'rather than a claim in a README\.\s+(\S+)\n',
                         readme)
    assert in_words, 'the "What\'s fixed" wording changed shape'
    word = in_words.group(1).lower()
    assert word in WORDS, 'unrecognised number word: {}'.format(word)
    assert WORDS[word] == len(linked)


def test_a_pull_request_is_not_linked_as_an_issue(readme, source_root):
    """`/issues/N` and `/pull/N` both resolve, and only one of them is true.

    Which of the thirty is which was checked against the GitHub API once; the
    list below is that answer, and this holds both documents to it rather than to
    the guess that everything upstream is an issue.

    """
    changelog = io.open(str(source_root.joinpath('CHANGELOG.md')),
                        encoding='utf-8').read()
    for text in (readme, changelog):
        wrong = {number for kind, number in UPSTREAM_ITEM.findall(text)
                 if (kind == 'issues') == (number in UPSTREAM_PULLS)}
        assert not wrong, sorted(wrong)


# Which of the upstream references are pull requests rather than issues, from
# the GitHub API. Kept here rather than fetched, because the suite does not go
# to the network and the answer does not change.
UPSTREAM_PULLS = frozenset(
    ('873', '995', '1063', '1101', '1102', '1104', '1243', '1258', '1344',
     '1355', '1442', '1470', '1479', '1499', '1506', '1514', '1523', '1538',
     '1539', '1550', '1551', '1553', '1562', '1600', '1610'))


def test_the_changelog_links_the_same_issues(source_root, linked):
    """Anything the README claims should be in the changelog too.

    The changelog is what a person reads to find out what changed; three of the
    thirty are about the test suite rather than the tool, so it is the README
    that carries those.

    """
    with io.open(str(source_root.joinpath('CHANGELOG.md')),
                 encoding='utf-8') as handle:
        changelog = _linked(handle.read())
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
    # Both what a shell calls itself (`nu`, `pwsh`) and what its driver is
    # called (`Nushell`, `Powershell`), because the README names shells the way
    # their users do rather than the way `TB_SHELL` spells them.
    known = ({name.lower() for name in shells.shells}
             | {driver.lower() for driver in shells.shells.values()})
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
    from thebleep import invocation

    from thebleep import agent_hooks

    real = set(const.ENV_TO_ATTR) | {'THEBLEEP_OVERRIDDEN_ALIASES',
                                     'THEBLEEP_ARGUMENT_PLACEHOLDER',
                                     'THEBLEEP_OUTPUT_LOG',
                                     'THEBLEEP_NO_RULE_PACK',
                                     # Read by the agent hooks alone, which
                                     # have no settings file of their own.
                                     agent_hooks.DECISION_ENV,
                                     # Not a setting: what the alias is told to
                                     # run, which is shell code and not a value.
                                     invocation.OVERRIDE_ENV}
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


# Facts that have gone out of step with the code more than once, each checked the
# only way that lasts: derived from the code rather than read off a note. None of
# these looks at prose -- a lint for English would fail on the day somebody
# rephrased a sentence, and would have caught none of what was actually wrong.


def test_the_rule_list_is_the_rules_there_are(readme, source_root):
    """Both directions. A rule that is not listed is a rule nobody finds."""
    # The three rule lists, and not the settings list, which is bulleted the
    # same way.
    rules_section = readme[readme.index('The following rules are enabled'):
                           readme.index('\n## Creating your own rules')]
    listed = set(re.findall(r'^\* `([a-z0-9_.]+)`', rules_section,
                            re.MULTILINE))
    # The rule for `test.py` is `rules/test.py.py`, so its name keeps the
    # extension and the file has it twice.
    bundled = {path.name[:-3] for path
               in source_root.joinpath('thebleep', 'rules').glob('*.py')
               if path.stem != '__init__'}
    assert bundled - listed == set(), sorted(bundled - listed)
    assert listed - bundled == set(), sorted(listed - bundled)


def test_the_number_of_rules_it_counts_is_the_number_there_are(readme,
                                                               source_root):
    """Stated in the table and again in How it works."""
    bundled = len([path for path
                   in source_root.joinpath('thebleep', 'rules').glob('*.py')
                   if path.stem != '__init__'])
    stated = re.search(r'\*\*Rules\*\*\s+\|\s+(\d+) of them', readme)
    assert stated, "the README's Rules row changed shape"
    assert int(stated.group(1)) == bundled

    for count in re.findall(r'(\d+) rules', readme):
        assert int(count) == bundled, \
            '{} rules is not {}'.format(count, bundled)


def test_the_rules_that_are_off_by_default_are_the_ones_it_says(
        readme, source_root):
    """The "not enabled by default" list, against the rules' own declaration.

    Only the unconditional `enabled_by_default = False`: the Arch and apt rules
    work theirs out from what is installed, and the README lists those
    separately as platform-specific.

    """
    off = set()
    for path in source_root.joinpath('thebleep', 'rules').glob('*.py'):
        with io.open(str(path), encoding='utf-8') as handle:
            if re.search(r'^enabled_by_default = False$', handle.read(),
                         re.MULTILINE):
                off.add(path.name[:-3])

    section = readme[readme.index('but are not enabled by\ndefault:'):]
    section = section[:section.index('\n#####')]
    listed = set(re.findall(r'^\* `([a-z0-9_]+)`', section, re.MULTILINE))
    assert listed == off - {'apt_get'}, sorted(listed ^ (off - {'apt_get'}))


def test_the_wrappers_it_names_are_the_wrappers_it_peels(readme):
    from thebleep import wrappers

    section = readme[readme.index('\n### Commands with something in front'):]
    section = section[:section.index('\nThe following rules are enabled')]
    # Fenced blocks out of the way first: a triple backtick is three of the
    # delimiter being looked for.
    section = re.sub(r'```.*?```', '', section, flags=re.DOTALL)
    # `env` appears as `env FOO=bar`, so the first word inside each span.
    named = {span.split()[0] for span in re.findall(r'`([^`]+)`', section)
             if span.split()}
    assert set(wrappers.WRAPPERS) <= named, \
        sorted(set(wrappers.WRAPPERS) - named)


def test_every_environment_variable_is_documented(readme):
    """The other direction of the check above: a setting with no `THEBLEEP_`
    line documented is a setting nobody can set from the environment."""
    from thebleep import const

    section = readme[readme.index('\nOr via environment variables'):]
    section = section[:section.index('\n## ', 1)]
    documented = set(re.findall(r'`(THEBLEEP_[A-Z_]+)`', section))
    assert set(const.ENV_TO_ATTR) == documented, \
        sorted(set(const.ENV_TO_ATTR) ^ documented)


def test_the_python_versions_agree_across_packaging_ci_and_tox(
        source_root, readme):
    """Four places say which Pythons this runs on."""
    setup = _read(source_root, 'setup.py')
    classified = sorted(re.findall(
        r"'Programming Language :: Python :: (\d+\.\d+)'", setup))

    tox = _read(source_root, 'tox.ini')
    envlist = re.search(r'envlist = py\{([\d,]+)\}', tox)
    assert envlist, 'tox.ini has no envlist in the expected shape'
    from_tox = sorted('{}.{}'.format(digits[0], digits[1:])
                      for digits in envlist.group(1).split(','))
    assert from_tox == classified, (from_tox, classified)

    workflow = _read(source_root, '.github/workflows/test.yml')
    matrix = re.search(r'python-version: \[([^\]]+)\]', workflow)
    assert matrix, 'the test workflow has no python-version matrix'
    from_ci = sorted(re.findall(r'\d+\.\d+', matrix.group(1)))
    assert from_ci == classified, (from_ci, classified)


def test_the_startup_files_agree_with_the_shells_and_the_installer(
        source_root, readme):
    """Where the alias goes, said in three places that drifted apart.

    tcsh had all three disagreeing: the driver named `~/.tcshrc` always, the
    installer named `~/.cshrc` always, and the README named the shell's actual
    rule. `--doctor` therefore looked in a file the shell does not read.

    """
    installer = _read(source_root, 'install.sh')
    for shell, path in (('zsh', '~/.zshrc'),
                        ('fish', '~/.config/fish/config.fish'),
                        ('nu', '~/.config/nushell/config.nu')):
        assert path in installer, '{} is not in install.sh'.format(path)
        assert path in readme, '{} is not in the README'.format(path)

    # tcsh: both files, and the rule for choosing between them.
    assert '~/.tcshrc' in installer and '~/.cshrc' in installer
    assert '`~/.tcshrc` if you have one, `~/.cshrc` otherwise' in readme


def test_the_benchmark_block_is_the_recorded_run(source_root, readme):
    """What `bench/chart.py --check` checks, so that `pytest` checks it too.

    In process rather than as a subprocess: the chart is drawn with block
    characters, and a subprocess writing those to a pipe on Windows encodes them
    with the locale's codec. That would turn a benchmark that has drifted into a
    UnicodeEncodeError, which is a worse way to be told.

    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        'bench_chart', str(source_root.joinpath('bench', 'chart.py')))
    chart = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chart)

    with io.open(str(source_root.joinpath('bench', 'results', 'final.json')),
                 encoding='utf-8') as handle:
        results = json.load(handle)

    assert chart.BEGIN in readme and chart.END in readme, \
        'no benchmark block in the README to check'
    start = readme.index(chart.BEGIN)
    finish = readme.index(chart.END) + len(chart.END)
    assert readme[start:finish] == chart.block(results), \
        'the README has drifted from bench/results/final.json; run ' \
        '`python bench/chart.py`'


def test_the_recorded_benchmark_names_a_commit_that_exists(source_root):
    """A result whose source cannot be checked out is not evidence.

    The previous one named a commit that stopped being reachable when the fork's
    author email was rewritten, so there was nothing to check out and see what
    those numbers were a measurement of.

    Only meaningful in a full clone. CI checks out one commit and an sdist has no
    repository at all, so this skips there rather than pretending; the moment it
    matters is when somebody records a new run, and they have the history.

    """
    import json

    with io.open(str(source_root.joinpath('bench', 'results', 'final.json')),
                 encoding='utf-8') as handle:
        recorded = json.load(handle)['environment']

    commit = recorded.get('commit')
    assert commit, 'the recorded run does not say which commit it measured'
    assert recorded.get('working_tree_clean') is True, \
        'the run was recorded from a tree with uncommitted changes in it'

    def git(*arguments):
        return subprocess.run(['git'] + list(arguments), cwd=str(source_root),
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)

    try:
        present = git('cat-file', '-e', commit + '^{commit}')
    except OSError:                                          # pragma: no cover
        pytest.skip('git is not installed')
    if present.returncode != 0:
        pytest.skip('this checkout does not have that commit')

    reachable = git('merge-base', '--is-ancestor', commit, 'HEAD')
    assert reachable.returncode == 0, \
        '{} is not reachable from HEAD: {}'.format(
            commit, reachable.stdout.decode('utf-8', 'replace'))


def test_the_shell_names_shell_takes_are_the_ones_it_documents(readme):
    """`--shell` lists what it accepts, and an unknown name is an error."""
    from thebleep import const

    listed = re.search(r'It takes any of ([^.]+?), and\n?an unknown name',
                       readme, re.DOTALL)
    assert listed, "the --shell wording changed shape"
    named = set(re.findall(r'`([a-z]+)`', listed.group(1)))
    assert named == set(const.SHELLS), sorted(named ^ set(const.SHELLS))


def test_the_hit_rate_in_the_readme_is_the_recorded_one(readme, source_root):
    """A number in the README that nothing checks is a number that drifts.

    The benchmark above it is held to a recorded run against a named commit; so
    is this. `bench/hit_rate.py --record` writes the file, and refuses to when
    the tree has uncommitted changes in it -- a measurement of code that is not
    in the history is not evidence.

    """
    import json

    recorded_path = source_root.joinpath('bench', 'results', 'hit-rate.json')
    if not recorded_path.exists():
        pytest.skip('no hit rate has been recorded yet')

    with io.open(str(recorded_path), encoding='utf-8') as handle:
        recorded = json.load(handle)

    table = readme.split('<!-- hit-rate:')[1].split('<!-- end hit-rate -->')[0]

    total = recorded['total']
    assert '{}/{}'.format(total['hits'], total['of']) in table, \
        'the README total is not the recorded one'

    for group in recorded['groups']:
        assert group['what'] in table, group['what']
        assert '{}/{}'.format(group['hits'], group['of']) in table

    theirs = recorded.get('thefuck_3_32')
    if theirs:
        assert '{}/{}'.format(theirs['total']['hits'],
                              theirs['total']['of']) in table


def test_the_hit_rate_names_a_commit_that_exists(source_root):
    """The same requirement the benchmark has, for the same reason."""
    import json

    recorded_path = source_root.joinpath('bench', 'results', 'hit-rate.json')
    if not recorded_path.exists():
        pytest.skip('no hit rate has been recorded yet')

    with io.open(str(recorded_path), encoding='utf-8') as handle:
        environment = json.load(handle)['environment']

    assert environment.get('commit'), 'it does not say what it measured'
    assert environment.get('working_tree_clean') is True, \
        'recorded from a tree with uncommitted changes in it'
