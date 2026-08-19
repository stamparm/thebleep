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
    """Third-party rule packages sitting in one entry of `sys.path`.

    This looks like something to cache -- it is a directory listing of every
    entry on `sys.path`, on every correction -- and measurement says otherwise.
    A normal virtualenv is 364 entries and costs 0.18 ms; one padded out to
    3,265 entries, far more than any real environment, costs 1.35 ms. Against a
    65 ms correction that is a third of one percent, and a cache would have to
    be invalidated when somebody installs a rule package, which is the one case
    that has to work.

    """
    try:
        entries = list(os.scandir(path))
    except OSError:
        return []
    return [entry.path for entry in entries
            if entry.name.startswith('thebleep_contrib_')]


def _rule_files(directory):
    """The rule files in a directory, in path order, each with size and mtime.

    `os.scandir` rather than `Path.glob`: listing the bundled rules is done on
    every single invocation, and globbing them took longer than loading them.

    The size and the timestamp come along because the listing has already been
    told them and the rule pack is about to ask. Windows carries both in the
    directory entry, so `DirEntry.stat()` there costs nothing, and the pack's own
    `os.stat` of every rule file was the most expensive thing between a mistyped
    command and a correction on the platform where a syscall is dearest.

    A mapping rather than a list of pairs, so that iterating it still yields the
    paths and nothing that only wanted those has to know about the rest.

    """
    try:
        entries = list(os.scandir(str(directory)))
    except OSError:
        return {}

    found = {}
    for entry in sorted(entries, key=lambda entry: entry.path):
        if not entry.name.endswith('.py'):
            continue
        try:
            stat = entry.stat()
        except OSError:
            # Gone between the listing and the question. The pack asks again and
            # reaches the same conclusion.
            continue
        found[entry.path] = (int(stat.st_mtime_ns), int(stat.st_size))
    return found


def get_rules(command=None):
    """Returns all enabled rules.

    When a command is given, only the rules that could possibly match it are
    loaded, which is most of the reason a correction is fast. Rules that don't
    say what they are about are always loaded, so a rule is never skipped on a
    guess.

    :type command: thebleep.types.Command | None
    :rtype: [Rule]

    """
    listed = {}
    for path in get_rules_import_paths():
        listed.update(_rule_files(path))
    paths = list(listed)

    if command is not None:
        # `listed` twice over: the paths to consider, and what the directory
        # listing already knows about them so the pack need not ask again.
        rules = rulepack.get_rules_for(command, paths, listed)
        if rules is not None:
            return rules

    return sorted(get_loaded_rules(paths),
                  key=lambda rule: rule.priority)


def _worth_offering(corrected, command):
    """Whether this suggestion is different from what the user already typed.

    Offering somebody their own command back is not a correction. It happens:
    a rule matches on something in the output and then finds nothing in the
    script to change, and what comes out is the failed command again -- which
    reads as a suggestion, takes a place in the list the arrow keys walk, and
    runs the same failure a second time when accepted.

    Except when the rule has a side effect. Then the command being unchanged is
    the point: what the suggestion does is the side effect, and running the
    command afterwards is what makes it useful.

    """
    return corrected.side_effect or corrected.script.strip() != command.strip()


def organize_commands(corrected_commands, script=''):
    """Yields sorted commands without duplicates.

    :type corrected_commands: Iterable[thebleep.types.CorrectedCommand]
    :type script: str
    :rtype: Iterable[thebleep.types.CorrectedCommand]

    """
    corrected_commands = (corrected for corrected in corrected_commands
                          if _worth_offering(corrected, script))
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


def _corrections(rules, command):
    return (corrected for rule in rules if rule.is_match(command)
            for corrected in rule.get_corrected_commands(command))


def _corrections_behind_the_wrapper(rules, command, prefix, inner_script):
    """Corrections for the command underneath, each given its wrapper back.

    Both commands are offered to every rule, because a rule may be about the
    wrapper -- `sudo` suggests adding one, `no_command` fixes a misspelled one
    -- or about what it wraps. The rules are looked up once for the two of them:
    dispatch already knows the command could be about either, so the second pass
    costs matching and not loading.

    The wrapper goes back in front of the whole suggestion, as `sudo_support`
    has always put `sudo` back, and it goes back as the user wrote it: the
    prefix is the text cut out of their own command line, not words joined up
    again.

    """
    inner = command.update(script=inner_script)

    for rule in rules:
        if rule.is_match(command):
            for corrected in rule.get_corrected_commands(command):
                yield corrected
        if rule.is_match(inner):
            for corrected in rule.get_corrected_commands(inner):
                yield corrected.with_prefix(prefix)


def get_corrected_commands(command):
    """Returns generator with sorted and unique corrected commands.

    :type command: thebleep.types.Command
    :rtype: Iterable[thebleep.types.CorrectedCommand]

    """
    from . import wrappers

    rules = get_rules(command)
    prefix, inner_script = wrappers.peel(command.script, command.script_parts)

    if prefix is None:
        corrected_commands = _corrections(rules, command)
    else:
        logs.debug(u'Wrapped command: {!r} behind {!r}'.format(
            inner_script, prefix))
        corrected_commands = _corrections_behind_the_wrapper(
            rules, command, prefix, inner_script)

    return organize_commands(corrected_commands, command.script)
