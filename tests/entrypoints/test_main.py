import pytest


@pytest.fixture
def main_module(mocker):
    mocker.patch('thebleep.system.init_output')
    from thebleep.entrypoints import main
    return main


def test_broken_pipe_is_not_an_error(main_module, mocker):
    mocker.patch.object(main_module, '_main', side_effect=BrokenPipeError)
    mocker.patch('os.open', return_value=42)
    # The stdout pytest captures has no descriptor to redirect, a real one has.
    mocker.patch('sys.stdout', new=mocker.Mock(fileno=lambda: 1))
    dup2 = mocker.patch('os.dup2')
    close = mocker.patch('os.close')

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 0
    assert dup2.call_args[0] == (42, 1)
    # And the descriptor it duplicated from is not left open.
    assert close.call_args[0] == (42,)


def test_exact_command_requires_json(main_module, mocker, capsys):
    class Arguments(object):
        alias = alias_loader = shell = shell_logger = None
        command = []
        command_text = 'git status'
        clear_cache = doctor = edit = enable_experimental_instant_mode = False
        help = json = repeat = version = yes = why = False

    mocker.patch.object(main_module.Parser, 'parse', return_value=Arguments())

    with pytest.raises(SystemExit) as exc_info:
        main_module._main()

    assert exc_info.value.code == 2
    assert '--command needs --json' in capsys.readouterr().err


def test_why_uses_the_previous_command_instead_of_json(
        main_module, mocker):
    class Arguments(object):
        alias = alias_loader = shell = shell_logger = None
        command = []
        command_text = None
        clear_cache = doctor = edit = enable_experimental_instant_mode = False
        help = json = repeat = version = yes = False
        why = True

    mocker.patch.object(main_module.Parser, 'parse', return_value=Arguments())
    fix = mocker.patch('thebleep.entrypoints.fix_command.fix_command')

    main_module._main()

    fix.assert_called_once()


class TestShellOverride(object):
    """`--shell`, for when working the shell out from the process tree fails."""

    def test_it_says_what_the_alias_would_have(self, main_module, os_environ):
        main_module._use_shell('fish')
        assert os_environ['TB_SHELL'] == 'fish'

    def test_an_unknown_name_is_refused_with_the_known_ones(
            self, main_module, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main_module._use_shell('elvish')
        assert exc_info.value.code == 2
        message = capsys.readouterr()[1]
        assert "Unknown shell 'elvish'" in message
        assert 'bash' in message and 'zsh' in message

    def test_it_does_not_go_looking_for_the_shell(self, main_module, mocker,
                                                  os_environ):
        """The whole point: no walking the process tree to be told what we
        were just told."""
        import thebleep.shells

        found = mocker.patch.object(thebleep.shells, '_get_shell_from_proc')
        main_module._use_shell('zsh')
        assert not found.called
