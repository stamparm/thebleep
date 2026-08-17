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


@pytest.mark.usefixtures('no_colors')
@pytest.mark.parametrize('debug, stderr', [
    (True, 'DEBUG: test\n'),
    (False, '')])
def test_debug(capsys, settings, debug, stderr):
    settings.debug = debug
    logs.debug('test')
    assert capsys.readouterr() == ('', stderr)
