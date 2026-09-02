# -*- encoding: utf-8 -*-

"""What a program's subcommands and options are called, read off the disk.

Most rules learn a tool's vocabulary from the tool: git prints the most
similar command, npm lists the scripts, `ls --help` lists the options. That
works when the tool says something, and a large class of tools say nothing:
Go's `flag` package, Ruby's optparse, Perl's Getopt::Long, docopt, and every
hand-rolled parser that prints `unknown option` and stops. Until now there
was nothing to read there, so nothing to suggest.

There is something to read. It is just not in the output:

- **Manual pages.** Nearly every installed program has one, and it lists the
  long options in a form a regular expression can pick out -- `\\-\\-color`
  in roff, `--color` in preformatted pages, `.Fl -color` in mdoc. The pages
  are also how the big tools document their subcommands, *one page each*:
  `git-status.1`, `docker-image-ls.1`, `npm-install.1`, `cargo-build.1`. The
  file names are the subcommand list, and they are read without opening a
  single page.

- **fish completions.** Declarative, one line per fact:
  `complete -c docker -n __fish_docker_no_subcommand -a attach` and
  `complete -c rg -l ignore-case -s i`. fish ships about a thousand of them
  and packages add their own; where they are installed, they are read
  whether or not fish is the shell in use.

Everything here is a file read, bounded in size and count, cached under the
directories' modification times, and never a process run. It is vocabulary,
not truth: a manual page can be older than the binary, so what comes back is
a list of *candidates* for `matching.rank` to hold at edit distance, exactly
as a `--help` screen would be. A wrong option name is still refused when
nothing is close.

"""

import os
import re

from . import cachefile

# Bumped when what is gathered or how changes, so an older cache is a miss.
FORMAT = 1

MAX_PAGE = 2 * 1024 * 1024
MAX_COMPLETION = 1024 * 1024
MAX_PAGES_PER_TOOL = 400

# Long options as roff, preformatted text and mdoc write them. The name is
# what follows the two dashes, however the dashes were escaped.
_ROFF_OPTION = re.compile(r'(?:\\-|-)(?:\\-|-)([A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])')
_MDOC_OPTION = re.compile(r'^\.Fl\s+\\?-([A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])',
                          re.MULTILINE)
_PAGE_NAME = re.compile(r'^(.+?)\.[1-8](?:[a-z]*)(?:\.(?:gz|bz2|xz|Z|zst|lzma))?$')

# fish's conditions for "no subcommand has been typed yet", across the ways
# completion authors spell them.
_NEEDS_COMMAND = re.compile(
    r'(?:no_subcommand|needs_command|use_subcommand|not\s+__fish_seen_subcommand'
    r'|__fish_is_first_arg|__fish_is_first_token|__fish_is_nth_token 1)')


def man_directories():
    """Where manual pages are, as `manpath` would work it out without running it.

    `MANPATH` when set; otherwise the usual system places plus, for every
    `bin` on `PATH`, the `share/man` and `man` beside it -- which is how
    `manpath` itself finds Homebrew's, Rust's and npm's pages.

    """
    found = []

    def add(directory):
        if directory and directory not in found and os.path.isdir(directory):
            found.append(directory)

    configured = os.environ.get('MANPATH')
    if configured:
        for directory in configured.split(os.pathsep):
            add(directory)
        return found

    for directory in os.environ.get('PATH', '').split(os.pathsep):
        if not directory:
            continue
        parent = os.path.dirname(directory.rstrip(os.sep))
        add(os.path.join(parent, 'share', 'man'))
        add(os.path.join(parent, 'man'))
    for directory in ('/usr/share/man', '/usr/local/share/man',
                      '/usr/local/man', '/opt/homebrew/share/man',
                      '/opt/local/share/man', '/usr/X11R6/man',
                      os.path.expanduser('~/.local/share/man')):
        add(directory)
    return found


def completion_directories():
    """Where fish completions are, for any shell's benefit."""
    found = []

    def add(directory):
        if directory and directory not in found and os.path.isdir(directory):
            found.append(directory)

    for base in [os.environ.get('XDG_CONFIG_HOME') or
                 os.path.expanduser('~/.config')]:
        add(os.path.join(base, 'fish', 'completions'))
    data_home = os.environ.get('XDG_DATA_HOME') or os.path.expanduser(
        '~/.local/share')
    data_dirs = os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share'
    for base in [data_home] + data_dirs.split(os.pathsep):
        if not base:
            continue
        add(os.path.join(base, 'fish', 'vendor_completions.d'))
        add(os.path.join(base, 'fish', 'completions'))
    add('/opt/homebrew/share/fish/vendor_completions.d')
    add('/opt/homebrew/share/fish/completions')
    return found


def _mtime(path):
    try:
        return int(os.stat(path).st_mtime)
    except OSError:
        return 0


def _fingerprint(tool):
    directories = man_directories() + completion_directories()
    return (FORMAT, tool, tuple((directory, _mtime(directory))
                                for directory in directories))


def _page_files(tool):
    """Every man1 page whose name is `tool` or begins with `tool-`."""
    pages = {}
    prefix = tool + '-'
    for directory in man_directories():
        for section in ('man1', 'man8'):
            try:
                names = os.listdir(os.path.join(directory, section))
            except OSError:
                continue
            for filename in sorted(names):
                found = _PAGE_NAME.match(filename)
                if not found:
                    continue
                name = found.group(1)
                if name == tool or name.startswith(prefix):
                    pages.setdefault(name, os.path.join(directory, section,
                                                        filename))
                    if len(pages) > MAX_PAGES_PER_TOOL:
                        return pages
    return pages


def _read_page(path):
    """A manual page's text, decompressed as its suffix says."""
    try:
        if os.path.getsize(path) > MAX_PAGE:
            return u''
        with open(path, 'rb') as handle:
            raw = handle.read(MAX_PAGE + 1)
    except OSError:
        return u''
    if len(raw) > MAX_PAGE:
        return u''
    try:
        if path.endswith('.gz') or raw[:2] == b'\x1f\x8b':
            import gzip
            raw = gzip.decompress(raw)
        elif path.endswith('.bz2'):
            import bz2
            raw = bz2.decompress(raw)
        elif path.endswith(('.xz', '.lzma')):
            import lzma
            raw = lzma.decompress(raw)
        elif path.endswith(('.Z', '.zst')):
            return u''
    except Exception:
        return u''
    if len(raw) > MAX_PAGE:
        return u''
    return raw.decode('utf-8', 'replace')


def _options_in_page(text):
    # `\-\-dry\-run`: the dashes inside a name are escaped too, so the
    # escapes come out before the name is read.
    plain = _plain(text)
    names = set(_ROFF_OPTION.findall(plain))
    names.update(_MDOC_OPTION.findall(text))
    return names


_ROFF_FONT = re.compile(r'\\f(?:\[[^\]]*\]|\(..|.)')


def _plain(text):
    """Roff text with the escapes that hide a command line taken out."""
    return _ROFF_FONT.sub('', text).replace('\\-', '-').replace('\\ ', ' ')


def _spelled(tool, rest, text):
    """How the page spells the command: `git cherry-pick` or `docker image ls`.

    Returns the words after `tool`, as a tuple, or None when the page does not
    say. `git-cherry-pick.1` and `docker-image-ls.1` look the same from the
    outside and mean different things -- one command with a dash in it, and
    a command under a command -- and the page's own synopsis is what tells
    them apart. The words are searched for as the page would print them.

    """
    plain = _plain(text[:64 * 1024])
    parts = rest.split('-')
    for cut in range(len(parts), 0, -1):
        # Longest dashed head first: `cherry-pick` before `cherry pick`.
        head = '-'.join(parts[:cut])
        tail = parts[cut:]
        spelled = ' '.join([tool, head] + tail)
        if re.search(r'(?<![\w-])' + re.escape(spelled) + r'(?![\w-])', plain):
            return tuple([head] + tail)
    return None


def _subcommands_from_pages(tool, pages, spelling):
    """The command words of every page, as `tool a b` tuples.

    `spelling` is what `_spelled` found per page; a page that did not say is
    read as one command with dashes, which is what most tools mean.

    """
    commands = set()
    prefix = tool + '-'
    for name in pages:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        if not rest or rest.startswith('-') or '--' in rest:
            continue
        words = spelling.get(name) or (rest,)
        commands.add(tuple(words))
    return commands


def _fish_words(line):
    """The words of one `complete` line, or None when it is not one."""
    stripped = line.strip()
    if not stripped.startswith('complete '):
        return None
    import shlex

    try:
        return shlex.split(stripped, comments=False, posix=True)
    except ValueError:
        return None


def _fish_facts(tool, directories):
    """Subcommands and long options declared for `tool` by fish completions."""
    subcommands = set()
    options = set()
    filename = tool + '.fish'
    for directory in directories:
        path = os.path.join(directory, filename)
        try:
            if os.path.getsize(path) > MAX_COMPLETION:
                continue
            with open(path, encoding='utf-8', errors='replace') as handle:
                lines = handle.read(MAX_COMPLETION + 1).splitlines()
        except OSError:
            continue
        for line in lines:
            words = _fish_words(line)
            if not words:
                continue
            _fish_line(words, tool, subcommands, options)
    return subcommands, options


def _fish_line(words, tool, subcommands, options):
    command = None
    condition = u''
    arguments = []
    declared = []
    index = 1
    while index < len(words):
        word = words[index]
        value = words[index + 1] if index + 1 < len(words) else None
        if word in ('-c', '--command'):
            command = value
            index += 2
        elif word in ('-n', '--condition'):
            condition += u' ' + (value or u'')
            index += 2
        elif word in ('-l', '--long-option', '-o', '--old-option'):
            if value and re.match(r'^[A-Za-z][A-Za-z0-9-]*$', value):
                declared.append(value)
            index += 2
        elif word in ('-a', '--arguments'):
            if value is not None:
                arguments.extend(value.split())
            index += 2
        elif word in ('-s', '--short-option', '-d', '--description',
                      '-w', '--wraps', '-p', '--path'):
            index += 2
        else:
            index += 1
    if command != tool:
        return
    options.update(declared)
    if arguments and _NEEDS_COMMAND.search(condition):
        for argument in arguments:
            if re.match(r'^[A-Za-z][A-Za-z0-9_-]*$', argument):
                subcommands.add(argument)


def _gather(tool):
    """Everything known about `tool`, in one read, for the cache."""
    pages = _page_files(tool)
    options = {}
    spelling = {}
    for name, path in pages.items():
        text = _read_page(path)
        found = _options_in_page(text)
        if found:
            options[name] = sorted(found)
        if name != tool:
            spelled = _spelled(tool, name[len(tool) + 1:], text)
            if spelled:
                spelling[name] = spelled

    commands = _subcommands_from_pages(tool, pages, spelling)
    subcommands = {words[0] for words in commands}
    nested = {}
    for words in commands:
        if len(words) > 1:
            nested.setdefault(words[0], set()).add(words[1])
    nested = {name: sorted(below) for name, below in nested.items()}
    # A page's options are filed under the command as typed: `git-cherry-pick`
    # stays, `docker-image-ls` is also reachable as `docker image ls`.
    for name, words in spelling.items():
        if len(words) > 1:
            options.setdefault(u'{}-{}'.format(tool, ' '.join(words)),
                               options.get(name, []))

    fish_subcommands, fish_options = _fish_facts(tool,
                                                 completion_directories())
    subcommands |= fish_subcommands
    if fish_options:
        options[tool] = sorted(set(options.get(tool, ())) | fish_options)

    return {'subcommands': sorted(subcommands), 'nested': nested,
            'options': options}


def _valid_tool(tool):
    return bool(tool) and re.match(r'^[A-Za-z0-9][A-Za-z0-9_.+-]*$', tool) \
        is not None and '..' not in tool


def facts(tool):
    """The cached vocabulary for `tool`: subcommands, nested, options."""
    tool = os.path.basename(tool or '')
    if not _valid_tool(tool):
        return {'subcommands': [], 'nested': {}, 'options': {}}
    fingerprint = _fingerprint(tool)
    name = 'vocabulary-' + tool
    cached = cachefile.load(name, fingerprint)
    if cached is not None:
        return cached
    return cachefile.save(name, fingerprint, _gather(tool))


def subcommands(tool, prefix=()):
    """What `tool` (or `tool <prefix>`) accepts as its next word."""
    known = facts(tool)
    if not prefix:
        return list(known['subcommands'])
    if len(prefix) == 1:
        return list(known['nested'].get(prefix[0], ()))
    return []


def options(tool, subcommand=None):
    """The long option names `tool` (or `tool <subcommand>`) documents."""
    known = facts(tool)
    tool = os.path.basename(tool or '')
    if subcommand:
        specific = known['options'].get(u'{}-{}'.format(
            tool, subcommand if isinstance(subcommand, str)
            else ' '.join(subcommand)))
        if specific:
            return list(specific)
    return list(known['options'].get(tool, ()))
