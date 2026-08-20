def match(command):
    split_command = command.script_parts

    return (split_command
            and len(split_command) >= 2
            and split_command[0] == split_command[1])


def get_new_command(command):
    return ' '.join(command.script_parts[1:])


# it should be rare enough to actually have to type twice the same word, so
# this rule can have a higher priority to come before things like "cd cd foo"
priority = 900


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
