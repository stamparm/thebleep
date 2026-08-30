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
    # A blank string is not a command. Without this guard a rule that matched
    # and then failed to find anything to replace could put an empty entry in
    # the selector: it looked different from the failed command, so the
    # unchanged-command check above did not catch it.
    script = corrected.script.strip()
    return corrected.side_effect or bool(script) and script != command.strip()


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


def _corrections_in_segments(rules, command):
    """Apply rules to each complete top-level command, then splice it back.

    A rule still receives the command shape it was written for -- its segment,
    not a reconstructed list of words -- so existing ``for_app`` rules can
    work in a pipeline or after ``&&``. The correction is inserted at the
    model's exact source span; separators, whitespace and neighboring commands
    never pass through a rule.
    """
    model = command.command_model
    if not model.complete or len(model.segments) < 2:
        return

    for segment in model.segments:
        if segment.command is None or segment.start == segment.end:
            continue

        segment_script = command.script[segment.start:segment.end]
        segment_command = command.update(script=segment_script)
        segment_rules = (rule for rule in rules
                         if not rule.requires_output
                         or _segment_has_unique_output_evidence(
                             command, segment))
        for corrected in _corrections_for_one_command(segment_rules,
                                                      segment_command):
            script = command.script[:segment.start] + corrected.script + \
                command.script[segment.end:]
            yield corrected.with_script(script)


def _segment_words_before_redirection(segment):
    """Return ordinary words before a segment's first redirection."""
    words = []
    for token in segment.tokens:
        if token.kind == 'redirection':
            break
        if token.kind == 'word':
            words.append(token.text)
    return words


def _word_values(word):
    """Return source and simple quoted forms of one shell word."""
    values = [word]
    if len(word) >= 2 and word[0] == word[-1] and word[0] in "'\"":
        values.append(word[1:-1])
    return values


def _segment_has_unique_output_evidence(command, segment):
    """Whether output names a non-command word in only this segment.

    Output-dependent rules cannot safely be applied to every member after a
    shell operator: ``git bad && git bad`` may have executed only the first
    member. A reported argument that occurs in exactly one top-level segment is
    useful evidence; no reported argument, or one repeated across segments,
    leaves the correction to the whole-line rules, which already abstain when
    their target is ambiguous.
    """
    if command.output is None:
        return True

    model = command.command_model
    words_by_segment = [
        _segment_words_before_redirection(item)[1:]
        for item in model.segments]
    current = _segment_words_before_redirection(segment)[1:]
    evidence = {value for word in current for value in _word_values(word)
                if len(value) >= 2 and value in command.output}
    if not evidence:
        return False

    occurrences = {
        value: sum(value in _word_values(word)
                   for words in words_by_segment for word in words)
        for value in evidence}
    return any(occurrences[value] == 1 for value in evidence)


def _corrections_for_one_command(rules, command):
    """Return ordinary and wrapper-aware corrections for one command view."""
    from . import wrappers

    prefix, inner_script = wrappers.peel(command.script, command.script_parts)
    if prefix is None:
        return _corrections(rules, command)

    logs.debug(u'Wrapped segment: {!r} behind {!r}'.format(
        inner_script, prefix))
    return _corrections_behind_the_wrapper(
        rules, command, prefix, inner_script)


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
    wrapper_name = prefix.split()[0] if prefix.split() else ''

    for rule in rules:
        if rule.is_match(command):
            for corrected in rule.get_corrected_commands(command):
                yield corrected

        # A rule whose whole job is to *add* a wrapper has nothing useful to say
        # about a command that wrapper was just peeled off. `sudo`, asked about
        # the `make install` behind a `sudo`, answers `sudo make install` -- and
        # then the peeled `sudo` goes back in front of it, giving
        # `sudo sudo make install`. `sudo make install` printing a nested
        # "Permission denied" is an entirely ordinary thing, so this was easy to
        # meet. The rule still runs against the whole command above, which is
        # where it belongs.
        if rule.name == wrapper_name:
            continue

        if rule.is_match(inner):
            for corrected in rule.get_corrected_commands(inner):
                yield corrected.with_prefix(prefix)


def get_corrected_commands(command):
    """Returns generator with sorted and unique corrected commands.

    :type command: thebleep.types.Command
    :rtype: Iterable[thebleep.types.CorrectedCommand]

    """
    from itertools import chain

    from . import learning

    rules = get_rules(command)
    learned_commands = learning.corrections(command)
    # Keep the whole-line pass for compound-aware rules such as no_command,
    # which can deliberately combine independent missing commands. The
    # segment pass adds the app-specific rules that previously could not see
    # anything after the first pipeline member.
    corrected_commands = chain(
        learned_commands,
        _corrections_for_one_command(rules, command),
        _corrections_in_segments(rules, command))

    return organize_commands(corrected_commands, command.script)
