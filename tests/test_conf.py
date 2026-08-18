import io
import pytest
import os
from unittest.mock import Mock
from thebleep import const
from thebleep.conf import Settings


@pytest.fixture
def load_source(mocker):
    return mocker.patch('thebleep.conf.load_source')


def test_settings_defaults(load_source, settings):
    load_source.return_value = object()
    settings.init()
    for key, val in const.DEFAULT_SETTINGS.items():
        assert getattr(settings, key) == val


class TestSettingsFromFile(object):
    def test_from_file(self, load_source, settings):
        load_source.return_value = Mock(rules=['test'],
                                        wait_command=10,
                                        require_confirmation=True,
                                        no_colors=True,
                                        priority={'vim': 100},
                                        exclude_rules=['git'])
        settings.init()
        assert settings.rules == ['test']
        assert settings.wait_command == 10
        assert settings.require_confirmation is True
        assert settings.no_colors is True
        assert settings.priority == {'vim': 100}
        assert settings.exclude_rules == ['git']

    def test_from_file_with_DEFAULT(self, load_source, settings):
        load_source.return_value = Mock(rules=const.DEFAULT_RULES + ['test'],
                                        wait_command=10,
                                        exclude_rules=[],
                                        require_confirmation=True,
                                        no_colors=True)
        settings.init()
        assert settings.rules == const.DEFAULT_RULES + ['test']


@pytest.mark.usefixtures('load_source')
class TestSettingsFromEnv(object):
    def test_from_env(self, os_environ, settings):
        os_environ.update({'THEBLEEP_RULES': 'bash:lisp',
                           'THEBLEEP_EXCLUDE_RULES': 'git:vim',
                           'THEBLEEP_WAIT_COMMAND': '55',
                           'THEBLEEP_REQUIRE_CONFIRMATION': 'true',
                           'THEBLEEP_NO_COLORS': 'false',
                           'THEBLEEP_PRIORITY': 'bash=10:lisp=wrong:vim=15',
                           'THEBLEEP_WAIT_SLOW_COMMAND': '999',
                           'THEBLEEP_SLOW_COMMANDS': 'lein:react-native:./gradlew',
                           'THEBLEEP_NUM_CLOSE_MATCHES': '359',
                           'THEBLEEP_EXCLUDED_SEARCH_PATH_PREFIXES': '/media/:/mnt/'})
        settings.init()
        assert settings.rules == ['bash', 'lisp']
        assert settings.exclude_rules == ['git', 'vim']
        assert settings.wait_command == 55
        assert settings.require_confirmation is True
        assert settings.no_colors is False
        assert settings.priority == {'bash': 10, 'vim': 15}
        assert settings.wait_slow_command == 999
        assert settings.slow_commands == ['lein', 'react-native', './gradlew']
        assert settings.num_close_matches == 359
        assert settings.excluded_search_path_prefixes == ['/media/', '/mnt/']

    def test_from_env_with_DEFAULT(self, os_environ, settings):
        os_environ.update({'THEBLEEP_RULES': 'DEFAULT_RULES:bash:lisp'})
        settings.init()
        assert settings.rules == const.DEFAULT_RULES + ['bash', 'lisp']


def test_settings_from_args(settings):
    settings.init(Mock(yes=True, debug=True, repeat=True))
    assert not settings.require_confirmation
    assert settings.debug
    assert settings.repeat


class TestInitializeSettingsFile(object):
    def test_ignore_if_exists(self, settings):
        settings_path_mock = Mock(is_file=Mock(return_value=True), open=Mock())
        settings.user_dir = Mock(joinpath=Mock(return_value=settings_path_mock))
        settings._init_settings_file()
        assert settings_path_mock.is_file.call_count == 1
        assert not settings_path_mock.open.called

    def test_create_if_doesnt_exists(self, settings):
        settings_file = io.StringIO()
        settings_path_mock = Mock(
            is_file=Mock(return_value=False),
            open=Mock(return_value=Mock(
                __exit__=lambda *args: None, __enter__=lambda *args: settings_file)))
        settings.user_dir = Mock(joinpath=Mock(return_value=settings_path_mock))
        settings._init_settings_file()
        settings_file_contents = settings_file.getvalue()
        assert settings_path_mock.is_file.call_count == 1
        assert settings_path_mock.open.call_count == 1
        assert const.SETTINGS_HEADER in settings_file_contents
        for setting in const.DEFAULT_SETTINGS.items():
            assert '# {} = {}\n'.format(*setting) in settings_file_contents
        settings_file.close()


@pytest.mark.parametrize('legacy_dir_exists, xdg_config_home, result', [
    (False, '~/.config', '~/.config/thebleep'),
    (False, '/user/test/config/', '/user/test/config/thebleep'),
    (True, '~/.config', '~/.thebleep'),
    (True, '/user/test/config/', '~/.thebleep')])
def test_get_user_dir_path(mocker, os_environ, settings, legacy_dir_exists,
                           xdg_config_home, result):
    mocker.patch('thebleep.conf.Path.is_dir',
                 return_value=legacy_dir_exists)

    if xdg_config_home is not None:
        os_environ['XDG_CONFIG_HOME'] = xdg_config_home
    else:
        os_environ.pop('XDG_CONFIG_HOME', None)

    path = settings._get_user_dir_path().as_posix()
    assert path == os.path.expanduser(result)


class TestSettingsFromEnvironment(object):
    """One variable that cannot be understood costs that variable and no more.

    It used to cost all of them: `_settings_from_env` was a comprehension, so a
    single unparseable value raised out of the whole thing and the caller's
    `update` never ran. Colours came back on and excluded rules came back with
    them, silently.

    """

    @pytest.fixture
    def from_env(self, os_environ):
        def read(**variables):
            os_environ.update(variables)
            return Settings(const.DEFAULT_SETTINGS)._settings_from_env()

        return read

    def test_a_bad_value_does_not_take_the_good_ones_with_it(self, from_env,
                                                             capsys):
        got = from_env(THEBLEEP_WAIT_COMMAND='abc',
                       THEBLEEP_NO_COLORS='true',
                       THEBLEEP_EXCLUDE_RULES='git_push',
                       THEBLEEP_NUM_CLOSE_MATCHES='7')
        assert got == {'no_colors': True,
                       'exclude_rules': ['git_push'],
                       'num_close_matches': 7}
        assert 'THEBLEEP_WAIT_COMMAND' in capsys.readouterr()[1]

    @pytest.mark.parametrize('value, expected', [
        ('true', True), ('True', True), ('TRUE', True), (' true ', True),
        ('yes', True), ('on', True), ('1', True),
        ('false', False), ('no', False), ('off', False), ('0', False),
    ])
    def test_booleans(self, from_env, value, expected):
        assert from_env(THEBLEEP_DEBUG=value) == {'debug': expected}

    @pytest.mark.parametrize('value', ['nope', 'ok', '', '2', 'truthy'])
    def test_a_boolean_that_is_neither(self, from_env, value, capsys):
        """Silently reading anything that is not `true` as false is a way to
        have a setting that does nothing and says nothing."""
        assert from_env(THEBLEEP_DEBUG=value) == {}
        assert 'neither true nor false' in capsys.readouterr()[1]

    @pytest.mark.parametrize('variable, value', [
        ('THEBLEEP_WAIT_COMMAND', 'abc'),
        ('THEBLEEP_WAIT_COMMAND', '-1'),
        ('THEBLEEP_WAIT_SLOW_COMMAND', '-5'),
        ('THEBLEEP_NUM_CLOSE_MATCHES', '0'),
        ('THEBLEEP_NUM_CLOSE_MATCHES', '-3'),
        ('THEBLEEP_HISTORY_LIMIT', '0'),
    ])
    def test_a_number_that_makes_no_sense(self, from_env, variable, value,
                                          capsys):
        assert from_env(**{variable: value}) == {}
        assert variable in capsys.readouterr()[1]

    @pytest.mark.parametrize('variable, value, expected', [
        ('THEBLEEP_WAIT_COMMAND', '0', ('wait_command', 0)),
        ('THEBLEEP_WAIT_COMMAND', '30', ('wait_command', 30)),
        ('THEBLEEP_NUM_CLOSE_MATCHES', '1', ('num_close_matches', 1)),
        ('THEBLEEP_HISTORY_LIMIT', '2000', ('history_limit', 2000)),
    ])
    def test_a_number_that_does(self, from_env, variable, value, expected):
        assert from_env(**{variable: value}) == dict([expected])
