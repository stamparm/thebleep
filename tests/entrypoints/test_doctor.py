# -*- coding: utf-8 -*-

"""`--doctor`: what it finds, and what it must never say.

Two of these are the point of the feature rather than details of it. A report
that has to write a settings file before it can tell you there isn't one is
describing a machine it just changed; and a report that carries a token out of
somebody's environment into a GitHub issue has done real harm.

"""

import os
import pytest
from thebleep import const
from thebleep.entrypoints import doctor as doctor_module
from thebleep.entrypoints.doctor import doctor, tidy, Report, OK, WARN, NOTE
from thebleep.shells import Bash, Generic, Nushell


@pytest.fixture
def home(tmpdir, os_environ, monkeypatch):
    """A home directory of our own, with nothing in it."""
    place = tmpdir.mkdir('home')
    os_environ['HOME'] = str(place)
    os_environ['XDG_CONFIG_HOME'] = str(place.mkdir('.config'))
    os_environ['XDG_CACHE_HOME'] = str(place.mkdir('.cache'))
    monkeypatch.setattr('os.path.expanduser',
                        lambda path: path.replace('~', str(place), 1))
    return place


@pytest.fixture(autouse=True)
def a_known_shell(monkeypatch):
    monkeypatch.setattr('thebleep.shells.shell', Bash())
    monkeypatch.setattr('thebleep.shells.bash.Bash._get_version',
                        lambda self: '5.2.21')


def _run(capsys):
    code = doctor()
    return code, capsys.readouterr()[0]


class TestReport(object):
    def test_only_warnings_count_as_problems(self):
        report = Report()
        report.add('a', 'fine')
        report.add('b', 'worth knowing', NOTE)
        report.add('c', 'broken', WARN)
        assert [line[0] for line in report.problems] == ['c']


class TestTidy(object):
    def test_the_home_directory_is_folded_back(self, home):
        assert tidy(os.path.join(str(home), 'x', 'y')) == os.path.join(
            '~', 'x', 'y')

    def test_a_path_outside_home_is_left_alone(self, home):
        assert tidy(os.path.join(os.sep, 'usr', 'bin')) == os.path.join(
            os.sep, 'usr', 'bin')

    def test_a_sibling_of_home_is_not_mistaken_for_it(self, home):
        """A prefix test without the separator would rewrite this one."""
        assert tidy(str(home) + '-backup') == str(home) + '-backup'

    def test_nothing(self):
        assert tidy(None) == 'not found'


class TestWhatItSays(object):
    def test_it_reports_the_basics(self, capsys, home):
        _, output = _run(capsys)
        assert 'The Bleep' in output
        assert 'Python' in output
        assert 'Platform' in output
        assert 'Bash 5.2.21' in output

    def test_a_clean_machine_says_so(self, capsys, home, monkeypatch):
        # The two things a bare test machine is missing anyway: no startup
        # file with an alias in it, and `thebleep` not on its PATH.
        monkeypatch.setattr(doctor_module, 'CHECKS', tuple(
            check for check in doctor_module.CHECKS
            if check not in (doctor_module._integration,
                             doctor_module._executable)))
        code, output = _run(capsys)
        assert 'Everything looks good.' in output
        assert code == 0

    def test_problems_are_counted_and_reported_in_the_status(
            self, capsys, home):
        report = Report()
        report.add('a', 'broken', WARN)
        report.add('b', 'also broken', WARN)
        from thebleep import logs

        logs.doctor_report(report.lines)
        assert '2 things to look at.' in capsys.readouterr()[0]

    def test_one_problem_is_singular(self, capsys):
        from thebleep import logs

        report = Report()
        report.add('a', 'broken', WARN)
        logs.doctor_report(report.lines)
        assert '1 thing to look at.' in capsys.readouterr()[0]


class TestItChangesNothing(object):
    """A diagnostic that alters the machine is describing a different one."""

    def test_no_settings_file_is_written(self, capsys, home):
        _run(capsys)
        assert not home.join('.config', 'thebleep', 'settings.py').exists()

    def test_no_config_directory_is_created(self, capsys, home):
        _run(capsys)
        assert not home.join('.config', 'thebleep').exists()

    def test_no_rule_pack_is_built(self, capsys, home):
        _run(capsys)
        assert not home.join('.cache', 'thebleep').exists()


class TestItIsSafeToPaste(object):
    def test_settings_are_named_and_never_quoted(self, capsys, home):
        """The names say what is overridden; the values are somebody's."""
        config = home.join('.config').mkdir('thebleep')
        config.join('settings.py').write_text(
            u"rules = ['sudo']\n"
            u"slow_commands = ['/opt/secret-corp/deploy']\n", 'utf-8')
        _, output = _run(capsys)
        assert 'rules' in output and 'slow_commands' in output
        assert 'secret-corp' not in output

    def test_the_environment_is_named_and_never_quoted(self, capsys, home,
                                                       os_environ):
        os_environ['THEBLEEP_RULES'] = 'sudo:not-a-secret-but-still'
        _, output = _run(capsys)
        assert 'THEBLEEP_RULES' in output
        assert 'not-a-secret-but-still' not in output

    def test_nothing_else_in_the_environment_is_reported(self, capsys, home,
                                                         os_environ):
        os_environ['AWS_SECRET_ACCESS_KEY'] = 'wJalrXUtnFEMI'
        os_environ['GITHUB_TOKEN'] = 'ghp_examplevalue'
        _, output = _run(capsys)
        assert 'wJalrXUtnFEMI' not in output
        assert 'ghp_examplevalue' not in output
        assert 'AWS_SECRET_ACCESS_KEY' not in output

    def test_the_startup_file_is_not_quoted_back(self, capsys, home,
                                                 monkeypatch):
        rc = home.join('.bashrc')
        rc.write_text(u'export API_KEY=hunter2\n'
                      u'eval "$(thebleep --alias-loader)"\n', 'utf-8')
        monkeypatch.setattr(
            'thebleep.shells.bash.Bash.how_to_configure',
            lambda self: self._create_shell_configuration(
                content='', path=str(rc), reload=''))
        _, output = _run(capsys)
        assert 'alias loader' in output
        assert 'hunter2' not in output


class TestIntegration(object):
    def _configure(self, monkeypatch, path):
        monkeypatch.setattr(
            'thebleep.shells.bash.Bash.how_to_configure',
            lambda self: self._create_shell_configuration(
                content='', path=str(path), reload=''))

    def test_a_missing_startup_file_is_a_problem(self, capsys, home,
                                                 monkeypatch):
        self._configure(monkeypatch, home.join('.bashrc'))
        code, output = _run(capsys)
        assert 'does not exist' in output
        assert code == 1

    def test_an_rc_without_the_alias_is_a_problem(self, capsys, home,
                                                  monkeypatch):
        rc = home.join('.bashrc')
        rc.write_text(u'export PATH=$PATH\n', 'utf-8')
        self._configure(monkeypatch, rc)
        code, output = _run(capsys)
        assert 'not in' in output
        assert code == 1

    def test_the_eager_alias_is_found_and_the_loader_suggested(
            self, capsys, home, monkeypatch):
        rc = home.join('.bashrc')
        rc.write_text(u'eval "$(thebleep --alias)"\n', 'utf-8')
        self._configure(monkeypatch, rc)
        _, output = _run(capsys)
        assert '--alias-loader' in output


class TestConfig(object):
    def _settings(self, home, source):
        config = home.join('.config').mkdir('thebleep')
        config.join('settings.py').write_text(source, 'utf-8')
        return config

    def test_a_settings_file_that_does_not_load_is_a_problem(self, capsys,
                                                             home):
        self._settings(home, u'rules = [\n')
        code, output = _run(capsys)
        assert 'does not load' in output
        assert 'SyntaxError' in output
        assert code == 1

    def test_a_setting_nobody_reads_is_pointed_out(self, capsys, home):
        """Which is exactly what a misspelled one looks like."""
        self._settings(home, u'requre_confirmation = False\n')
        _, output = _run(capsys)
        assert 'requre_confirmation' in output

    def test_no_settings_file_is_not_a_problem(self, capsys, home):
        _, output = _run(capsys)
        assert 'defaults in use' in output

    def test_a_rules_list_that_enables_nothing_is_a_problem(self, capsys,
                                                            home):
        """Naming rules replaces the default set rather than adding to it.

        So a list of one name that is not a rule is a list of no rules, the
        whole tool goes quiet, and this used to be reported as healthy.

        """
        self._settings(home, u"rules = ['python_moduel_error']\n")
        code, output = _run(capsys)
        assert 'Rules enabled' in output
        assert 'none' in output
        assert 'DEFAULT_RULES' in output
        assert code == 1

    def test_the_DEFAULT_RULES_string_is_not_a_problem(self, capsys, home):
        self._settings(
            home, u"rules = ['DEFAULT_RULES', 'python_module_error']\n")
        _, output = _run(capsys)
        assert 'Rules enabled' not in output

    def test_a_misspelling_beside_real_rules_is_pointed_out(self, capsys,
                                                            home):
        self._settings(home, u"rules = ['sudo', 'no_commnad']\n")
        _, output = _run(capsys)
        assert 'no_commnad' in output
        assert '1 of the 2 named' in output

    def test_a_narrow_rules_list_of_real_rules_is_fine(self, capsys, home):
        self._settings(home, u"rules = ['sudo', 'no_command']\n")
        _, output = _run(capsys)
        assert 'Rules enabled' not in output


class TestRulePack(object):
    def test_entries_from_another_installation_are_not_counted(
            self, capsys, home, monkeypatch):
        """The pack is keyed by absolute path, and two installations share it.

        Which is harmless -- nothing loads a rule from a path this installation
        does not look in -- but reporting "346 rules cached" against "173
        bundled" describes a machine with two copies on it and reads as a number
        that has gone wrong.

        """
        from thebleep import rulepack

        bundled = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(doctor_module.__file__))), 'rules')
        monkeypatch.setattr(rulepack, '_read_pack', lambda: {
            os.path.join(bundled, 'sudo.py'): object(),
            os.path.join(bundled, '__init__.py'): object(),
            os.path.join(os.sep, 'somebody', 'else', 'rules', 'sudo.py'):
                object(),
            os.path.join(os.sep, 'somebody', 'else', 'rules', 'git_add.py'):
                object(),
        })
        _, output = _run(capsys)
        assert '(1 rules cached)' in output
        assert '2 entries from somewhere else' in output

    def test_a_pack_with_nothing_of_ours_in_it_reads_as_not_built(
            self, capsys, home, monkeypatch):
        from thebleep import rulepack

        monkeypatch.setattr(rulepack, '_read_pack', lambda: {
            os.path.join(os.sep, 'elsewhere', 'rules', 'sudo.py'): object()})
        _, output = _run(capsys)
        assert 'not built yet' in output


class TestPerShell(object):
    def test_an_unrecognised_shell_is_a_problem(self, capsys, home,
                                                monkeypatch):
        monkeypatch.setattr('thebleep.shells.shell', Generic())
        code, output = _run(capsys)
        assert 'generic' in output
        assert '--shell' in output
        assert code == 1

    def test_nushell_is_described_as_it_works(self, capsys, home, monkeypatch):
        monkeypatch.setattr('thebleep.shells.shell', Nushell())
        monkeypatch.setattr('thebleep.shells.nushell.Nushell._get_version',
                            lambda self: '0.108.0')
        _, output = _run(capsys)
        assert 'always go to your command line' in output

    def test_a_nushell_too_old_for_commandline_edit_is_a_problem(
            self, capsys, home, monkeypatch):
        """Where the whole integration is `commandline edit --replace`.

        Without it there is no correction at all, and the way that failed was a
        Nushell parse error out of the middle of the alias.

        """
        monkeypatch.setattr('thebleep.shells.shell', Nushell())
        monkeypatch.setattr('thebleep.shells.nushell.Nushell._get_version',
                            lambda self: '0.86.0')
        code, output = _run(capsys)
        said = ' '.join(output.split())
        assert 'Shell version' in said
        assert 'Nushell 0.86 is older than 0.87' in said
        assert 'commandline edit' in said
        assert code == 1

    def test_a_nushell_it_cannot_ask_is_not_called_too_old(
            self, capsys, home, monkeypatch):
        """`nu` not being on PATH right now is not a version problem."""
        monkeypatch.setattr('thebleep.shells.shell', Nushell())
        monkeypatch.setattr(
            'thebleep.shells.nushell.Nushell._get_version',
            lambda self: (_ for _ in ()).throw(OSError('no nu')))
        code, output = _run(capsys)
        assert 'Shell version' not in output

    def test_a_shell_that_records_output_says_so(self, capsys, home):
        _, output = _run(capsys)
        assert 'Replayless capture' in output

    def test_the_shell_source_is_named(self, capsys, home, os_environ):
        os_environ['TB_SHELL'] = 'bash'
        _, output = _run(capsys)
        assert 'from TB_SHELL' in output


class TestLeftovers(object):
    def test_an_unmigrated_the_fuck_config_is_a_problem(self, capsys, home):
        home.join('.config').mkdir('thefuck').join('settings.py').write('')
        code, output = _run(capsys)
        assert 'has not been copied over' in output
        assert code == 1

    def test_it_is_only_a_note_once_you_have_your_own(self, capsys, home):
        home.join('.config').mkdir('thefuck').join('settings.py').write('')
        ours = home.join('.config').mkdir('thebleep')
        ours.join('settings.py').write('')
        _, output = _run(capsys)
        assert 'is still there' in output


class TestEveryCheckIsGuarded(object):
    def test_one_check_blowing_up_does_not_lose_the_rest(self, capsys, home,
                                                         monkeypatch):
        def explode(report):
            raise RuntimeError('the disk is on fire')

        monkeypatch.setattr(doctor_module, 'CHECKS',
                            (explode,) + doctor_module.CHECKS)
        code, output = _run(capsys)
        assert 'the disk is on fire' in output
        assert 'The Bleep' in output
        assert code == 1


def test_the_doctor_flag_reaches_the_doctor(mocker):
    from thebleep.entrypoints import main as main_module

    called = mocker.patch('thebleep.entrypoints.doctor.doctor',
                          return_value=0)
    mocker.patch('sys.argv', ['thebleep', '--doctor'])
    with pytest.raises(SystemExit) as exc_info:
        main_module._main()
    assert called.called
    assert exc_info.value.code == 0


def test_every_setting_name_it_reports_is_a_real_one():
    """The report names settings; the names have to come from one place."""
    assert 'rules' in const.DEFAULT_SETTINGS
    assert OK != WARN != NOTE


class TestRuleHealth(object):
    """A rule that raises never fires, and nothing anywhere says so.

    `Rule.is_match` and `Rule.get_corrected_commands` catch what a rule raises,
    which is the right failure model -- one rule's mistake is that rule's
    problem -- and it is also why three rules were found dead against real
    output in one afternoon. What can be seen from here is the narrow version:
    a rule that raises on the plainest input there is.

    """

    def test_a_healthy_set_says_so(self, capsys, home):
        doctor()
        assert 'none raising' in capsys.readouterr()[0]

    def test_a_rule_that_raises_is_named(self, capsys, home, mocker):
        from thebleep import corrector

        exploding = mocker.Mock()
        exploding.name = 'exploding_rule'
        exploding.match.side_effect = IndexError('list index out of range')
        mocker.patch.object(corrector, 'get_rules', return_value=[exploding])

        doctor()
        # Whitespace-normalised: the advice is word-wrapped to the report's
        # width, so the name and its exception can land on separate lines.
        printed = ' '.join(capsys.readouterr()[0].split())
        assert 'exploding_rule (IndexError)' in printed
        assert 'never fire' in printed
        assert '1 of 1 rules raise' in printed

    def test_the_probes_are_shapes_a_correction_really_makes(self):
        """`Command('', '')` is not one -- `from_raw_script` refuses an empty
        script -- and probing with it reported four rules as broken for indexing
        `script_parts[0]`, which is an index they are entitled to."""
        from thebleep import corrector
        from thebleep.types import Command

        for rule in corrector.get_rules():
            for probe in (Command('x', ''), Command('git x', 'error'),
                          Command('x y z', 'not found')):
                rule.match(probe)
