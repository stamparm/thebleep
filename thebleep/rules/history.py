from thebleep.utils import get_close_matches, get_closest, \
    get_valid_history_without_current


def match(command):
    return len(get_close_matches(command.script,
                                 get_valid_history_without_current(command)))


def get_new_command(command):
    return get_closest(command.script,
                       get_valid_history_without_current(command))


priority = 9999


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
