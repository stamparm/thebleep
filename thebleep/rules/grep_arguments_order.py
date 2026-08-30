import os
from thebleep.utils import for_app, raw_script_parts


def _get_actual_file(parts):
    for part in parts[1:]:
        if os.path.isfile(part) or os.path.isdir(part):
            return part


@for_app('grep', 'egrep')
def match(command):
    return ': No such file or directory' in command.output \
        and _get_actual_file(command.script_parts)


def get_new_command(command):
    actual_file = _get_actual_file(command.script_parts)
    parts = raw_script_parts(command.script)
    if actual_file is None or len(parts) != len(command.script_parts):
        return []

    actual_file_index = command.script_parts.index(actual_file)
    # Moves file to the end of the script:
    raw_file = parts.pop(actual_file_index)
    parts.append(raw_file)
    return ' '.join(parts)
