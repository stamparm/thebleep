from thebleep.utils import for_app


@for_app('ag')
def match(command):
    # `in`, not `endswith(... '\n')`: the pane and instant-mode readers strip
    # the output, so the trailing newline is only ever there after a replay.
    return 'run ag with -Q' in command.output


def get_new_command(command):
    return command.script.replace('ag', 'ag -Q', 1)
