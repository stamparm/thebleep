import pytest


@pytest.fixture
def main_module(mocker):
    mocker.patch('thebleep.system.init_output')
    from thebleep.entrypoints import main
    return main


def test_broken_pipe_is_not_an_error(main_module, mocker):
    mocker.patch.object(main_module, '_main', side_effect=BrokenPipeError)
    mocker.patch('os.open', return_value=42)
    dup2 = mocker.patch('os.dup2')

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 0
    assert dup2.call_args[0][0] == 42
