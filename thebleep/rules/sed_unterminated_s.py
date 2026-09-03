from thebleep.utils import _argument_spans, for_app


@for_app('sed')
def match(command):
    return any(message in command.output for message in (
        "unterminated `s' command",
        "unterminated 's' command",
        'unescaped newline inside substitute pattern',
        "unmatched '/'"))


def get_new_command(command):
    """The closing slash, added inside the word that lacks it.

    Only that word changes, in place. The line used to be split and every
    word re-quoted, which turned `> out` and `| less` into arguments for sed
    and rewrote the user's own quoting.

    """
    script = command.script
    for begin, end in reversed(list(_argument_spans(script))):
        word = script[begin:end]
        # A quoted word's span starts after its opening quote and ends after
        # its closing one; the slash goes inside the closing quote.
        opening = script[begin - 1] if begin and script[begin - 1] in '"\'' \
            else ''
        inner = word
        close_at = end
        if opening and word.endswith(opening):
            inner = word[:-1]
            close_at = end - 1
        if inner.startswith(('s/', '-es/')) and not inner.endswith('/'):
            script = script[:close_at] + '/' + script[close_at:]
    return script
