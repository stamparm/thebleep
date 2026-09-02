# -*- encoding: utf-8 -*-

"""Subcommands and options read off manual pages and fish completions.

The pages here are written in the shapes real pages take -- roff with `\\-\\-`,
preformatted `--`, mdoc `.Fl -` -- and named the way real tools name them:
`tool-cherry-pick.1` for a command with a dash in it, `tool-image-ls.1` for a
command under a command, told apart by the synopsis exactly as `git` and
`docker` have to be.

"""

import gzip
import os

import pytest

from thebleep import vocabulary


ROFF = u'''.TH TOOL 1
.SH NAME
tool \\- a tool
.SH SYNOPSIS
\\fBtool\\fR [\\fB\\-\\-color\\fR=\\fIwhen\\fR] [\\fB\\-\\-verbose\\fR]
.SH OPTIONS
.TP
\\fB\\-\\-color\\fR[=\\fIWHEN\\fR]
colorize the output
.TP
\\fB\\-v\\fR, \\fB\\-\\-verbose\\fR
say more
.TP
\\fB\\-\\-dry\\-run\\fR
do nothing
'''

CHERRY = u'''.SH NAME
tool-cherry \\- find commits
.SH SYNOPSIS
\\fBtool cherry\\fR [\\-v]
'''

CHERRY_PICK = u'''.SH NAME
tool-cherry-pick \\- apply changes
.SH SYNOPSIS
\\fBtool cherry-pick\\fR [\\-\\-edit] [\\-\\-no\\-commit]
'''

IMAGE = u'''.SH NAME
tool-image \\- manage images
.SH SYNOPSIS
\\fBtool image\\fR COMMAND
'''

IMAGE_LS = u'''.SH NAME
tool-image-ls \\- list images
.SH SYNOPSIS
\\fBtool image ls\\fR [\\fB\\-\\-quiet\\fR] [\\fB\\-\\-digests\\fR]
'''

MDOC = u'''.Dd January 1, 2026
.Sh SYNOPSIS
.Nm other
.Fl -recursive
.Fl -follow-symlinks
.Fl v
'''

PREFORMATTED = u'''PLAIN(1)

NAME
       plain - a preformatted page

OPTIONS
       --long-form   the long form
       --other       another one
'''

FISH = u'''# completions for tool
complete -c tool -n '__fish_use_subcommand' -a status -d 'Show status'
complete -c tool -n '__fish_use_subcommand' -a 'fetch pull' -d 'Get things'
complete -c tool -n '__fish_seen_subcommand_from fetch' -a '(__fish_remotes)'
complete -c tool -l porcelain -d 'Machine output'
complete -c tool -s q -l quiet
complete -c other -l not-ours
complete -c tool -n 'not __fish_seen_subcommand_from status' -a 'stash'
'''


@pytest.fixture
def home(tmpdir, os_environ):
    man1 = tmpdir.mkdir('man').mkdir('man1')
    man1.join('tool.1.gz').write_binary(gzip.compress(ROFF.encode('utf-8')))
    man1.join('tool-cherry.1.gz').write_binary(
        gzip.compress(CHERRY.encode('utf-8')))
    man1.join('tool-cherry-pick.1.gz').write_binary(
        gzip.compress(CHERRY_PICK.encode('utf-8')))
    man1.join('tool-image.1.gz').write_binary(
        gzip.compress(IMAGE.encode('utf-8')))
    man1.join('tool-image-ls.1.gz').write_binary(
        gzip.compress(IMAGE_LS.encode('utf-8')))
    man1.join('tool-web--browse.1.gz').write_binary(
        gzip.compress(b'.SH NAME\nhelper\n'))
    man1.join('other.1').write(MDOC)
    man1.join('plain.1').write(PREFORMATTED)
    completions = tmpdir.mkdir('share').mkdir('fish').mkdir(
        'vendor_completions.d')
    completions.join('tool.fish').write(FISH)

    os_environ['MANPATH'] = str(tmpdir.join('man'))
    os_environ['XDG_DATA_DIRS'] = str(tmpdir.join('share'))
    os_environ['XDG_DATA_HOME'] = str(tmpdir.join('nowhere'))
    os_environ['XDG_CONFIG_HOME'] = str(tmpdir.join('nowhere'))
    os_environ['XDG_CACHE_HOME'] = str(tmpdir.join('cache'))
    os_environ['HOME'] = str(tmpdir.join('nowhere'))
    return tmpdir


class TestSubcommands(object):
    def test_one_page_each(self, home):
        assert set(vocabulary.subcommands('tool')) >= {
            'cherry', 'cherry-pick', 'image'}

    def test_a_dashed_command_and_a_nested_one_are_told_apart(self, home):
        """`tool-cherry-pick.1` says `tool cherry-pick`; `tool-image-ls.1` says
        `tool image ls`. Same file name shape, different commands."""
        top = vocabulary.subcommands('tool')
        assert 'cherry-pick' in top
        assert 'image-ls' not in top
        assert 'ls' not in top
        assert vocabulary.subcommands('tool', ('image',)) == ['ls']
        assert vocabulary.subcommands('tool', ('cherry',)) == []

    def test_helper_pages_with_a_double_dash_are_not_commands(self, home):
        assert 'web' not in vocabulary.subcommands('tool')
        assert 'web--browse' not in vocabulary.subcommands('tool')

    def test_fish_adds_what_it_declares_before_a_subcommand(self, home):
        top = vocabulary.subcommands('tool')
        assert {'status', 'fetch', 'pull', 'stash'} <= set(top)
        # Arguments completed *after* a subcommand are not commands.
        assert '(__fish_remotes)' not in top

    def test_another_tools_completion_is_not_ours(self, home):
        assert 'not-ours' not in vocabulary.options('tool')

    def test_a_tool_nobody_documented(self, home):
        assert vocabulary.subcommands('nothing') == []
        assert vocabulary.options('nothing') == []


class TestOptions(object):
    def test_roff_escaped_dashes(self, home):
        assert set(vocabulary.options('tool')) >= {'color', 'verbose', 'dry-run'}

    def test_fish_long_options_join_them(self, home):
        assert {'porcelain', 'quiet'} <= set(vocabulary.options('tool'))

    def test_a_subcommands_own_page(self, home):
        assert set(vocabulary.options('tool', 'cherry-pick')) == {
            'edit', 'no-commit'}
        assert set(vocabulary.options('tool', ('image', 'ls'))) == {
            'quiet', 'digests'}

    def test_an_unknown_subcommand_falls_back_to_the_program(self, home):
        assert 'color' in vocabulary.options('tool', 'nosuch')

    def test_mdoc(self, home):
        assert set(vocabulary.options('other')) == {'recursive', 'follow-symlinks'}

    def test_preformatted(self, home):
        assert set(vocabulary.options('plain')) == {'long-form', 'other'}


class TestBounds(object):
    def test_a_page_too_large_is_skipped(self, home, mocker):
        mocker.patch.object(vocabulary, 'MAX_PAGE', 10)
        assert vocabulary.options('tool') == ['porcelain', 'quiet']

    def test_a_name_that_is_a_path_is_refused(self, home):
        assert vocabulary.facts('../../etc/passwd') == {
            'subcommands': [], 'nested': {}, 'options': {}}
        assert vocabulary.facts('') == {
            'subcommands': [], 'nested': {}, 'options': {}}

    def test_a_program_given_by_path_is_looked_up_by_name(self, home):
        assert 'color' in vocabulary.options('/usr/bin/tool')

    def test_the_answer_is_cached_under_the_directories(self, home, mocker):
        vocabulary.facts('tool')
        gather = mocker.patch.object(vocabulary, '_gather')
        vocabulary.facts('tool')
        assert not gather.called

    def test_a_changed_directory_is_read_again(self, home, mocker):
        vocabulary.facts('tool')
        mocker.patch.object(vocabulary, '_mtime', return_value=1)
        gather = mocker.patch.object(vocabulary, '_gather', return_value={
            'subcommands': ['fresh'], 'nested': {}, 'options': {}})
        assert vocabulary.subcommands('tool') == ['fresh']
        assert gather.called

    def test_the_cache_format_is_part_of_the_key(self, home, mocker):
        vocabulary.facts('tool')
        mocker.patch.object(vocabulary, 'FORMAT', vocabulary.FORMAT + 1)
        gather = mocker.patch.object(vocabulary, '_gather', return_value={
            'subcommands': [], 'nested': {}, 'options': {}})
        vocabulary.facts('tool')
        assert gather.called


class TestDirectories(object):
    def test_manpath_wins_when_set(self, home):
        assert vocabulary.man_directories() == [str(home.join('man'))]

    def test_otherwise_beside_every_bin_on_path(self, tmpdir, os_environ):
        os_environ.pop('MANPATH', None)
        prefix = tmpdir.mkdir('prefix')
        prefix.mkdir('bin')
        prefix.mkdir('share').mkdir('man')
        os_environ['PATH'] = str(prefix.join('bin'))
        assert str(prefix.join('share', 'man')) in vocabulary.man_directories()

    def test_missing_directories_are_not_listed(self, home):
        assert all(os.path.isdir(directory)
                   for directory in vocabulary.completion_directories())
