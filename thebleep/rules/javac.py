"""Appends .java when compiling java files

Example:
 > javac foo
 error: Class names, 'foo', are only accepted if annotation
 processing is explicitly requested

"""
from thebleep.utils import for_app


from thebleep.utils import command_word_index, raw_script_parts  # noqa: E402


@for_app('javac', at_least=1)
def match(command):
    return _source(command) is not None


def _source(command):
    """The last word that is not an option, when it lacks `.java`."""
    parts = command.script_parts
    for part in reversed(parts[command_word_index(parts) + 1:]):
        if not part.startswith('-'):
            return None if part.endswith('.java') else part
    return None


def get_new_command(command):
    parts = raw_script_parts(command.script)
    for index in range(len(parts) - 1, command_word_index(parts), -1):
        if not parts[index].startswith('-'):
            parts[index] += '.java'
            break
    return ' '.join(parts)


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
