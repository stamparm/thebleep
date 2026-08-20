# -*- coding: utf-8 -*-

import os
import pytest
from thebleep import const
from thebleep.shells import Bash


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestBash(object):
    @pytest.fixture
    def shell(self):
        return Bash()

    @pytest.fixture(autouse=True)
    def probe(self, mocker):
        """What `bash -c 'echo $BASH_VERSION'` said.

        Patched at `tool_output`, which is where the timeout, the `/dev/null`
        stderr and the `errors='replace'` decoding now live -- a raw `Popen`
        here had none of them.

        """
        return mocker.patch('thebleep.shells.bash.tool_output',
                            return_value='')

    @pytest.fixture(autouse=True)
    def shell_aliases(self):
        os.environ['TB_SHELL_ALIASES'] = (
            'alias bleep=\'eval $(thebleep $(fc -ln -1))\'\n'
            'alias l=\'ls -CF\'\n'
            'alias la=\'ls -A\'\n'
            'alias ll=\'ls -alF\'')

    @pytest.mark.parametrize('before, after', [
        ('pwd', 'pwd'),
        ('bleep', 'eval $(thebleep $(fc -ln -1))'),
        ('awk', 'awk'),
        ('ll', 'ls -alF')])
    def test_from_shell(self, before, after, shell):
        assert shell.from_shell(before) == after

    def test_to_shell(self, shell):
        assert shell.to_shell('pwd') == 'pwd'

    def test_and_(self, shell):
        assert shell.and_('ls', 'cd') == 'ls && cd'

    def test_or_(self, shell):
        assert shell.or_('ls', 'cd') == 'ls || cd'

    def test_get_aliases(self, shell):
        assert shell.get_aliases() == {'bleep': 'eval $(thebleep $(fc -ln -1))',
                                       'l': 'ls -CF',
                                       'la': 'ls -A',
                                       'll': 'ls -alF'}

    @pytest.mark.parametrize('alias, parsed', [
        ('alias ll=\'ls -alF\'', ('ll', 'ls -alF')),
        ('alias empty=', ('empty', '')),
        ('alias quote=\'', ('quote', "'"))])
    def test_parse_alias(self, shell, alias, parsed):
        assert shell._parse_alias(alias) == parsed

    def test_app_alias(self, shell):
        assert 'bleep () {' in shell.app_alias('bleep')
        assert 'BLEEP () {' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert 'bleep() {' in loader
        assert 'thebleep --alias bleep' in loader
        assert 'bleep "$@"' in loader

    def test_app_alias_variables_correctly_set(self, shell):
        alias = shell.app_alias('bleep')
        assert "bleep () {" in alias
        assert 'TB_SHELL=bash' in alias
        assert "TB_ALIAS=bleep" in alias
        assert 'TB_SHELL_ALIASES=$(alias)' in alias

    def test_app_alias_can_edit(self, shell):
        alias = shell.app_alias('bleep')
        # Offered only from bash 4, which is where `read -i` starts.
        assert 'BASH_VERSINFO[0]' in alias
        assert 'TB_CAN_EDIT="$TB_CAN_EDIT"' in alias
        assert 'read -r -e -i "$TB_CMD"' in alias
        assert '-eq {}'.format(const.EXIT_EDIT) in alias

    def test_app_alias_edit_respects_alter_history(self, settings, shell):
        settings.alter_history = True
        assert 'history -s "$TB_EDIT"' in shell.app_alias('bleep')
        settings.alter_history = False
        assert 'history -s "$TB_EDIT"' not in shell.app_alias('bleep')

    def test_get_history(self, history_lines, shell):
        history_lines(['ls', 'rm'])
        assert list(shell.get_history()) == ['ls', 'rm']

    def test_split_command(self, shell):
        command = 'git log -p'
        command_parts = ['git', 'log', '-p']
        assert shell.split_command(command) == command_parts

    def test_how_to_configure(self, shell, config_exists):
        config_exists.return_value = True
        assert shell.how_to_configure().can_configure_automatically

    def test_how_to_configure_when_config_not_found(self, shell,
                                                    config_exists):
        config_exists.return_value = False
        assert not shell.how_to_configure().can_configure_automatically

    @pytest.mark.parametrize('present, platform, path', [
        (('.bashrc',), 'linux', '~/.bashrc'),
        (('.bash_profile',), 'linux', '~/.bash_profile'),
        (('.bashrc', '.bash_profile'), 'linux', '~/.bashrc'),
        # Neither there. What is named has to be a path -- `bash config` was
        # printed into the advice, which came out as "Run `thebleep
        # --alias-loader >> bash config`" -- and which path depends on the
        # platform, because macOS's Terminal starts a login shell and a login
        # shell reads `.bash_profile`.
        ((), 'linux', '~/.bashrc'),
        ((), 'darwin', '~/.bash_profile'),
        (('.bashrc',), 'darwin', '~/.bashrc'),
    ])
    def test_how_to_configure_names_a_file_that_is_there(
            self, shell, present, platform, path, monkeypatch, config_exists):
        """The test used to be `if os.path.join(home, '.bashrc')`.

        A joined path is a non-empty string, so the first branch always won and
        `.bash_profile` was never named -- on a machine with one and no
        `.bashrc`, the advice was to edit a file that does not exist.

        """
        config_exists.return_value = True
        home = os.path.expanduser('~')
        monkeypatch.setattr('thebleep.shells.bash.sys.platform', platform)
        monkeypatch.setattr(
            'os.path.exists',
            lambda candidate: os.path.basename(candidate) in present
            and os.path.dirname(candidate) == home)
        assert shell.how_to_configure().path == path
        assert shell.how_to_configure().path.startswith('~/'), \
            'the advice has to name a file, not describe one'

    def test_info(self, shell, probe):
        probe.return_value = '3.5.9'
        assert shell.info() == 'Bash 3.5.9'
        assert probe.call_args[0][0] == ['bash', '-c', 'echo $BASH_VERSION']

    def test_a_probe_that_answers_nothing(self, shell, probe):
        """A shell that is not there, will not start, or did not finish in
        time. All three used to come out of `info()` as a traceback or a
        warning naming an exception; now the version is simply unknown."""
        probe.return_value = ''
        assert shell.info() == 'Bash'
