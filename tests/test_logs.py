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


class TestTheOneEscapeThatIsNotAColour(object):
    """`\\x1b[1K` -- erase the line -- before reprinting a suggestion.

    It was hard-coded, so it was the one sequence nothing checked: a console
    that renders no escapes rendered `^[[1K` in front of every suggestion. It
    goes through `logs.escape` now, which asks the same question `color` does
    without `no_colors` in it -- because erasing a line is layout, and somebody
    who asked for no colour still wants the previous suggestion gone.

    """

    @pytest.fixture
    def command(self):
        from thebleep.types import CorrectedCommand

        return CorrectedCommand('ls', None, 100)

    def _written(self, capsys, command):
        logs.confirm_text(command)
        return capsys.readouterr()[1]

    def test_a_terminal_gets_it(self, capsys, command, mocker, settings):
        mocker.patch.object(logs._ansi_supported, 'cached', True)
        settings.no_colors = False
        assert '\x1b[1K\r' in self._written(capsys, command)

    def test_no_colors_still_gets_it(self, capsys, command, mocker, settings):
        """The suggestion still has to replace the previous one on screen."""
        mocker.patch.object(logs._ansi_supported, 'cached', True)
        settings.no_colors = True
        written = self._written(capsys, command)
        assert '\x1b[1K\r' in written
        # And no colour, which is what was actually asked for.
        assert '\x1b[32m' not in written

    def test_something_that_renders_no_escapes_does_not(self, capsys, command,
                                                        mocker):
        mocker.patch.object(logs._ansi_supported, 'cached', False)
        assert '\x1b' not in self._written(capsys, command)
