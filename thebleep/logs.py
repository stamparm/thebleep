# -*- encoding: utf-8 -*-

import sys
from .conf import settings
from .system import init_colors
from . import const


class colorama(object):
    """The escape codes we use, spelled the way colorama spells them.

    Importing colorama was the single most expensive thing this app did at
    startup, and on anything but Windows it was being asked for constants that
    never change. Windows still initialises the real colorama, in
    `system.win32`, because there the codes are not native.

    """

    class Fore(object):
        RED = '\033[31m'
        GREEN = '\033[32m'
        BLUE = '\033[34m'
        WHITE = '\033[37m'

    class Back(object):
        RED = '\033[41m'

    class Style(object):
        BRIGHT = '\033[1m'
        RESET_ALL = '\033[0m'


def _ansi_supported():
    """Whether the stream we colour is something that renders colour.

    Colorama used to answer this by wrapping the stream and stripping codes
    from it; asking the stream directly is the same answer for less work.

    """
    if _ansi_supported.cached is None:
        try:
            _ansi_supported.cached = bool(sys.stderr.isatty())
        except (AttributeError, ValueError):
            _ansi_supported.cached = False
    return _ansi_supported.cached


_ansi_supported.cached = None


def color(color_):
    """Utility for ability to disabling colored output.

    The one place an escape code is produced, and therefore the one place that
    has to make sure the console will render it. On Windows that means
    colorama, which is why it is asked for here and not at startup: an
    invocation that writes no colour -- and most write none -- should not pay
    to import it.

    """
    if settings.no_colors or not _ansi_supported():
        return ''

    init_colors()
    return color_


def warn(title):
    sys.stderr.write(u'{warn}[WARN] {title}{reset}\n'.format(
        warn=color(colorama.Back.RED + colorama.Fore.WHITE
                   + colorama.Style.BRIGHT),
        reset=color(colorama.Style.RESET_ALL),
        title=title))


def exception(title, exc_info):
    # traceback is one of the more expensive imports in the standard library
    # and this is the only thing that needs it.
    from traceback import format_exception

    sys.stderr.write(
        u'{warn}[WARN] {title}:{reset}\n{trace}'
        u'{warn}----------------------------{reset}\n\n'.format(
            warn=color(colorama.Back.RED + colorama.Fore.WHITE
                       + colorama.Style.BRIGHT),
            reset=color(colorama.Style.RESET_ALL),
            title=title,
            trace=''.join(format_exception(*exc_info))))


def rule_failed(rule, exc_info):
    exception(u'Rule {}'.format(rule.name), exc_info)


def failed(msg):
    sys.stderr.write(u'{red}{msg}{reset}\n'.format(
        msg=msg,
        red=color(colorama.Fore.RED),
        reset=color(colorama.Style.RESET_ALL)))


def show_corrected_command(corrected_command):
    sys.stderr.write(u'{prefix}{bold}{script}{reset}{side_effect}\n'.format(
        prefix=const.USER_COMMAND_MARK,
        script=corrected_command.script,
        side_effect=u' (+side effect)' if corrected_command.side_effect else u'',
        bold=color(colorama.Style.BRIGHT),
        reset=color(colorama.Style.RESET_ALL)))


def confirm_text(corrected_command):
    sys.stderr.write(
        (u'{prefix}{clear}{bold}{script}{reset}{side_effect} '
         u'[{green}enter{reset}/{blue}↑{reset}/{blue}↓{reset}'
         u'/{red}ctrl+c{reset}/{red}esc{reset}]').format(
            prefix=const.USER_COMMAND_MARK,
            script=corrected_command.script,
            side_effect=' (+side effect)' if corrected_command.side_effect else '',
            clear='\033[1K\r',
            bold=color(colorama.Style.BRIGHT),
            green=color(colorama.Fore.GREEN),
            red=color(colorama.Fore.RED),
            reset=color(colorama.Style.RESET_ALL),
            blue=color(colorama.Fore.BLUE)))


def confirm_replay(script):
    sys.stderr.write(
        (u'{bold}{script}{reset} has to run again to be read, and anything '
         u'it changes will change twice. Run it? '
         u'[{green}y{reset}/{red}N{reset}]').format(
            script=script,
            bold=color(colorama.Style.BRIGHT),
            green=color(colorama.Fore.GREEN),
            red=color(colorama.Fore.RED),
            reset=color(colorama.Style.RESET_ALL)))

    # The question ends without a newline and is followed by a blocking read,
    # and stderr is line buffered, so without this it sits in the buffer and
    # the user is asked nothing while the terminal waits for their answer.
    sys.stderr.flush()


def replay_answer(allowed):
    sys.stderr.write(u' {}\n'.format(u'yes' if allowed else u'no'))


def debug(msg):
    if settings.debug:
        sys.stderr.write(u'{blue}{bold}DEBUG:{reset} {msg}\n'.format(
            msg=msg,
            reset=color(colorama.Style.RESET_ALL),
            blue=color(colorama.Fore.BLUE),
            bold=color(colorama.Style.BRIGHT)))


class debug_time(object):
    """Times a block of work and reports it, when debugging is on.

    A class rather than a `contextlib` generator because this wraps every rule
    import and every rule match: with debugging off it should cost as close to
    nothing as a context manager can, and it should not need a clock at all.

    """

    def __init__(self, msg):
        self._msg = msg
        self._started = None

    def __enter__(self):
        if settings.debug:
            from datetime import datetime

            self._started = datetime.now()
        return self

    def __exit__(self, *exc_info):
        if self._started is not None:
            from datetime import datetime

            debug(u'{} took: {}'.format(
                self._msg, datetime.now() - self._started))


def how_to_configure_alias(configuration_details):
    print(u"Seems like {bold}bleep{reset} alias isn't configured!".format(
        bold=color(colorama.Style.BRIGHT),
        reset=color(colorama.Style.RESET_ALL)))

    if configuration_details:
        # On its own lines, indented: what goes in a startup file is a few
        # lines of shell, and reading it out of the middle of a sentence is
        # harder than it needs to be.
        print(u"\nPut this in your {bold}{path}{reset}:\n".format(
            bold=color(colorama.Style.BRIGHT),
            reset=color(colorama.Style.RESET_ALL),
            path=configuration_details.path))
        for line in configuration_details.content.split(u'\n'):
            print(u'    {}'.format(line))
        print(
            u"\nThen apply it with {bold}{reload}{reset}, or restart your"
            u" shell.".format(
                bold=color(colorama.Style.BRIGHT),
                reset=color(colorama.Style.RESET_ALL),
                reload=configuration_details.reload))

        if configuration_details.can_configure_automatically:
            print(
                u"Or run {bold}bleep{reset} a second time to configure"
                u" it automatically.".format(
                    bold=color(colorama.Style.BRIGHT),
                    reset=color(colorama.Style.RESET_ALL)))

    # A heading GitHub makes an anchor for by itself. It used to be
    # `#manual-installation`, which existed only as a hand-written `<a name=...>`
    # in the README and rendered there as a stray `#` above the heading.
    print(u'More details - '
          u'https://github.com/stamparm/thebleep#installation')


def already_configured(configuration_details):
    print(
        u"Seems like {bold}bleep{reset} alias already configured!\n"
        u"For applying changes run {bold}{reload}{reset}"
        u" or restart your shell.".format(
            bold=color(colorama.Style.BRIGHT),
            reset=color(colorama.Style.RESET_ALL),
            reload=configuration_details.reload))


def configured_successfully(configuration_details):
    print(
        u"{bold}bleep{reset} alias configured successfully!\n"
        u"For applying changes run {bold}{reload}{reset}"
        u" or restart your shell.".format(
            bold=color(colorama.Style.BRIGHT),
            reset=color(colorama.Style.RESET_ALL),
            reload=configuration_details.reload))


def version(thebleep_version, python_version, shell_info):
    sys.stderr.write(
        u'The Bleep {} using Python {} and {}\n'.format(thebleep_version,
                                                        python_version,
                                                        shell_info))
