from thebleep.utils import replace_argument, for_app


@for_app('php', at_least=2)
def match(command):
    return ('-s' in command.script_parts
            and command.script_parts[-1] != '-s')


def get_new_command(command):
    return replace_argument(command.script, "-s", "-S")


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
