# -*- encoding: utf-8 -*-

"""`cat /ec/passwd` -> `cat /etc/passwd`. The spellcheck `cd_correction` does
for a directory you are moving into, done for a path you are only reading,
writing or naming on the command line.

    $ cat /ec/passwd
    cat: /ec/passwd: No such file or directory
    $ bleep
    No bleeps given                  <- `path_from_history` only recognises a
                                         path exactly as you typed it before,
                                         and this one never was

`cd_correction` walks a path a directory at a time, spellchecking each piece
against what is actually sitting in its parent -- `/ec` next to `etc`, `bin`,
`var` -- but only `cd` gets that treatment, by way of `@for_app('cd')`.
Everything else that fails on a path -- `cat`, `less`, `rm`, `vim` -- had
nothing but `path_from_history`, silent unless this exact path was typed
before.

Same walk, generalised, and asked of `thebleep.matching` rather than
`difflib`: the keyboard-aware distance `no_command` uses, so `/ec` reaches
`/etc` for the reason `sud` reaches `sudo`, and a segment with no single
plausible explanation -- or two equally plausible ones -- stops the walk
rather than guessing past it. Every segment but the last must still be a
directory to descend into; the last does not have to be, because `passwd` is
a file.

"""

from pathlib import Path

from thebleep import matching
from thebleep.shells import shell
from thebleep.system import expanduser
from thebleep.utils import memoize, replace_argument


def _closest(name, entries):
    """The one entry `name` is a plausible slip of, or `None`.

    More than one equally good candidate is exactly as uninformative as none,
    so both are refused the same way `no_command` refuses a tie it cannot
    break on its own.

    """
    ranked = matching.rank_with_distance(name, entries)
    slips = matching.plausible_slips(name, ranked)
    return slips[0] if len(slips) == 1 else None


def _walk(cwd, segments):
    """`cwd` plus `segments`, spellchecked one piece at a time.

    `None` the moment a piece cannot be explained -- by being there already,
    or by being one plausible slip from something that is.

    """
    for index, segment in enumerate(segments):
        if segment in ('', '.'):
            continue
        if segment == '..':
            cwd = cwd.parent
            continue

        candidate = cwd / segment
        if not candidate.exists():
            try:
                entries = [child.name for child in cwd.iterdir()]
            except OSError:
                return None
            found = _closest(segment, entries)
            if found is None:
                return None
            candidate = cwd / found

        last = index == len(segments) - 1
        if not last and not candidate.is_dir():
            return None
        cwd = candidate

    return cwd


def _fix(word):
    """The corrected path for `word`, or `None` if there is nothing to fix.

    Only an absolute or home-relative path is answerable this way: a bare
    `passwd` could be one slip from a hundred things depending on where the
    program would have looked for it, and no filesystem walk resolves that.

    Absolute is asked of `Path` rather than a leading `/`, because that is
    also how `C:\\Users\\...` answers: an `\\ec\\passwd` on Windows starts
    with a drive letter, not a slash, and never reached the walk below.

    """
    if not (Path(word).is_absolute() or word.startswith('~')):
        return None

    expanded = expanduser(word)
    if expanded.exists():
        return None

    root = Path(expanded.anchor)
    fixed = _walk(root, expanded.relative_to(root).parts)
    if fixed is None or fixed == expanded:
        return None

    return str(fixed)


@memoize
def _fixed_argument(command):
    for part in command.script_parts[1:]:
        fixed = _fix(part)
        if fixed:
            return part, fixed
    return None


def match(command):
    return ('no such file or directory' in command.output.lower()
            and bool(command.script_parts)
            # `cd` already gets this, directory-only and with its own
            # `cd_mkdir` fallback; asking again here would just duplicate it.
            and command.script_parts[0] != 'cd'
            and bool(_fixed_argument(command)))


def get_new_command(command):
    word, fixed = _fixed_argument(command)
    return replace_argument(command.script, word, shell.quote(fixed))


# Behind `path_from_history`, at 800: a path you have actually used before is
# stronger evidence than one spellchecked against the filesystem just now.
priority = 900
