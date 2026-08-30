import shlex
from thebleep.shells import shell
from thebleep.utils import for_app


@for_app('sed')
def match(command):
    return any(message in command.output for message in (
        "unterminated `s' command",
        "unterminated 's' command",
        'unescaped newline inside substitute pattern',
        "unmatched '/'"))


def get_new_command(command):
    script = shlex.split(command.script)

    for (i, e) in enumerate(script):
        if e.startswith(('s/', '-es/')) and e[-1] != '/':
            script[i] += '/'

    return ' '.join(map(shell.quote, script))
