import pytest
from thebleep import logs


@pytest.fixture(autouse=True)
def forget_tty_check():
    """The answer is cached per process, and these tests change it."""
    logs._ansi_supported.cached = None
    yield
    logs._ansi_supported.cached = None


@pytest.mark.parametrize('no_colors, a_terminal, expected', [
    (False, True, 'red'),
    (True, True, ''),
    # Colour written to a pipe or a log file is noise, so it is left out.
    (False, False, ''),
    (True, False, '')])
def test_color(settings, mocker, no_colors, a_terminal, expected):
    mocker.patch('sys.stderr.isatty', return_value=a_terminal, create=True)
    settings.no_colors = no_colors
    assert logs.color('red') == expected


@pytest.mark.parametrize('no_colors, a_terminal, initialised', [
    (False, True, True),
    (True, True, False),
    (False, False, False),
    (True, False, False)])
def test_the_console_is_only_prepared_when_colour_is_written(
        settings, mocker, no_colors, a_terminal, initialised):
    """On Windows preparing it means colorama, and colorama means `ctypes`.

    Which is a DLL the scanner reads before it can be mapped, on the platform
    where that is the dearest thing an interpreter does. An invocation that
    writes no colour -- `--alias` at every shell startup, a correction with
    `--yes`, anything redirected -- must not pay for it.

    """
    init_colors = mocker.patch('thebleep.logs.init_colors')
    mocker.patch('sys.stderr.isatty', return_value=a_terminal, create=True)
    settings.no_colors = no_colors

    logs.color('red')

    assert init_colors.called is initialised


@pytest.mark.usefixtures('no_colors')
@pytest.mark.parametrize('debug, stderr', [
    (True, 'DEBUG: test\n'),
    (False, '')])
def test_debug(capsys, settings, debug, stderr):
    settings.debug = debug
    logs.debug('test')
    assert capsys.readouterr() == ('', stderr)
