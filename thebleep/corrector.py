import os
import sys
from .conf import settings
from .types import Rule
from . import logs, rulepack


def get_loaded_rules(rules_paths):
    """Yields all available rules.

    :type rules_paths: [str]
    :rtype: Iterable[Rule]

    """
    for path in rules_paths:
        if os.path.basename(str(path)) != '__init__.py':
            rule = Rule.from_path(path)
            if rule and rule.is_enabled:
                yield rule


def get_rules_import_paths():
    """Yields all rules import paths.

    :rtype: Iterable[str]

    """
    # Bundled rules:
    yield os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')
    # Rules defined by user:
    yield os.path.join(str(settings.user_dir), 'rules')
    # Packages with third-party rules:
    for path in sys.path:
        for contrib_module in _contrib_modules(path):
            contrib_rules = os.path.join(contrib_module, 'rules')
            if os.path.isdir(contrib_rules):
                yield contrib_rules


def _contrib_modules(path):
    """Third-party rule packages sitting in one entry of `sys.path`."""
    try:
        entries = list(os.scandir(path))
    except OSError:
        return []
    return [entry.path for entry in entries
            if entry.name.startswith('thebleep_contrib_')]


def _rule_files(directory):
    """The rule files in a directory, in a stable order.

    `os.scandir` rather than `Path.glob`: listing the bundled rules is done on
    every single invocation, and globbing them took longer than loading them.

    """
    try:
        entries = list(os.scandir(str(directory)))
    except OSError:
        return []
    return sorted(entry.path for entry in entries
                  if entry.name.endswith('.py'))


def get_rules(command=None):
    """Returns all enabled rules.

    When a command is given, only the rules that could possibly match it are
    loaded, which is most of the reason a correction is fast. Rules that don't
    say what they are about are always loaded, so a rule is never skipped on a
    guess.

    :type command: thebleep.types.Command | None
    :rtype: [Rule]

    """
    paths = [rule_path for path in get_rules_import_paths()
             for rule_path in _rule_files(path)]

    if command is not None:
        rules = rulepack.get_rules_for(command, paths)
        if rules is not None:
            return rules

    return sorted(get_loaded_rules(paths),
                  key=lambda rule: rule.priority)


def organize_commands(corrected_commands):
    """Yields sorted commands without duplicates.

    :type corrected_commands: Iterable[thebleep.types.CorrectedCommand]
    :rtype: Iterable[thebleep.types.CorrectedCommand]

    """
    try:
        first_command = next(corrected_commands)
        yield first_command
    except StopIteration:
        return

    # First-seen order within a priority, and not set-iteration order. A set of
    # `CorrectedCommand` iterates by the hash of a string, which Python
    # randomises per process, so every suggestion after the first came out in a
    # different order on every run -- and which suggestion the down arrow gives
    # you is not a detail. Rules arrive in priority order and a rule lists its
    # own suggestions in the order it means them, so first-seen is the order to
    # keep.
    without_duplicates = []
    for command in corrected_commands:
        if command != first_command and command not in without_duplicates:
            without_duplicates.append(command)

    sorted_commands = sorted(
        without_duplicates,
        key=lambda corrected_command: corrected_command.priority)

    logs.debug(u'Corrected commands: {}'.format(
        ', '.join(u'{}'.format(cmd) for cmd in [first_command] + sorted_commands)))

    yield from sorted_commands


def get_corrected_commands(command):
    """Returns generator with sorted and unique corrected commands.

    :type command: thebleep.types.Command
    :rtype: Iterable[thebleep.types.CorrectedCommand]

    """
    corrected_commands = (
        corrected for rule in get_rules(command)
        if rule.is_match(command)
        for corrected in rule.get_corrected_commands(command))
    return organize_commands(corrected_commands)
