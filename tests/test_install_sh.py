# -*- encoding: utf-8 -*-

"""`install.sh`, run for real, with `--dry-run` so it installs nothing.

It is the first thing anybody runs and the one piece of this project that is not
Python, so what it prints is checked the same way everything else is. Two things
it got wrong are the reason there is a file here: `--help` could be prevented from
printing by input it was about to reject, and a shell it did not recognise -- any
PowerShell -- was told to append to `~/.bashrc` with a redirection PowerShell does
not have.

"""

import os
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform == 'win32',
                                reason='there is no sh to run it with')


@pytest.fixture
def install_sh(source_root):
    path = str(source_root.joinpath('install.sh'))

    def run(*arguments, **environment):
        # A HOME of its own: the tcsh branch looks for `~/.tcshrc`, and the
        # answer must not depend on whose machine the suite is running on. Same
        # reason the installer's own knobs are cleared -- a developer with
        # THEBLEEP_SHELL exported would otherwise get different answers here
        # from the ones CI gets.
        env = dict(os.environ, HOME=environment.pop('home', '/nonexistent'))
        for knob in ('THEBLEEP_SHELL', 'THEBLEEP_ALIAS', 'THEBLEEP_INSTALLER',
                     'THEBLEEP_INSTALL_FROM'):
            env.pop(knob, None)
        env.update(environment)
        process = subprocess.run(
            ['sh', path] + list(arguments), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return process.returncode, process.stdout.decode('utf-8'), \
            process.stderr.decode('utf-8')

    return run


class TestHelp(object):
    def test_it_prints_the_usage(self, install_sh):
        code, out, _ = install_sh('--help')
        assert code == 0
        assert 'THEBLEEP_INSTALLER' in out
        assert '--dry-run' in out

    def test_it_prints_it_even_with_an_alias_it_would_refuse(self, install_sh):
        """Being told your input is bad is when you ask for the usage."""
        code, out, err = install_sh('--help', THEBLEEP_ALIAS='rm -rf /')
        assert code == 0, err
        assert 'THEBLEEP_INSTALLER' in out

    def test_it_installs_nothing_to_print_it(self, install_sh):
        code, out, _ = install_sh('--help')
        assert 'would run' not in out


class TestTheAliasName(object):
    def test_a_name_that_is_shell_code_is_refused(self, install_sh):
        code, _, err = install_sh('--dry-run', THEBLEEP_ALIAS='a; rm -rf /')
        assert code == 2
        assert 'cannot be the name of the alias' in err

    def test_an_ordinary_name_is_used(self, install_sh):
        code, out, err = install_sh('--dry-run', THEBLEEP_ALIAS='fuck')
        assert code == 0, err
        assert '--alias-loader fuck' in out


class TestWhichFileItNames(object):
    @pytest.mark.parametrize('shell, expected', [
        ('bash', '>> ~/.bashrc'),
        ('zsh', '>> ~/.zshrc'),
        ('fish', '>> ~/.config/fish/config.fish'),
        ('nu', '>> ~/.config/nushell/config.nu'),
        ('csh', '>> ~/.cshrc'),
        ('tcsh', '>> ~/.cshrc'),
    ])
    def test_the_shells_it_knows(self, install_sh, shell, expected):
        code, out, err = install_sh('--dry-run', THEBLEEP_SHELL=shell)
        assert code == 0, err
        assert expected in out

    def test_tcsh_with_a_tcshrc_of_its_own(self, install_sh, tmpdir):
        tmpdir.join('.tcshrc').write('')
        code, out, err = install_sh('--dry-run', THEBLEEP_SHELL='tcsh',
                                    home=str(tmpdir))
        assert code == 0, err
        assert '>> ~/.tcshrc' in out

    def test_powershell_gets_powershell_instructions(self, install_sh):
        code, out, err = install_sh('--dry-run', THEBLEEP_SHELL='pwsh')
        assert code == 0, err
        assert 'Add-Content $PROFILE' in out
        assert '~/.bashrc' not in out
        assert '>>' not in out.split('would run')[-1]

    def test_a_shell_it_does_not_know_is_not_guessed_at(self, install_sh):
        code, out, err = install_sh('--dry-run', THEBLEEP_SHELL='ksh')
        assert code == 0, err
        assert 'not going to guess' in out
        # Every shell it does know, offered rather than one of them chosen.
        for expected in ('~/.bashrc', '~/.zshrc', 'config.fish',
                         'config.nu', '$PROFILE'):
            assert expected in out

    def test_no_shell_at_all_is_not_guessed_at_either(self, install_sh):
        code, out, err = install_sh('--dry-run', SHELL='')
        assert code == 0, err
        assert 'not going to guess' in out

    def test_the_environment_beats_the_login_shell(self, install_sh):
        code, out, err = install_sh('--dry-run', SHELL='/bin/bash',
                                    THEBLEEP_SHELL='fish')
        assert code == 0, err
        assert '>> ~/.config/fish/config.fish' in out
