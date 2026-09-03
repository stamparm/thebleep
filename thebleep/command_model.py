# -*- encoding: utf-8 -*-

"""A conservative, source-preserving model of a shell command line.

This is deliberately a lexer with structure, not a shell interpreter. It
recognises the boundaries that matter to a correction engine while leaving
expansion, execution and shell-specific semantics to the shell itself.

The important property is source spans. A caller can identify the command word
inside ``cd foo && gti status | grep main`` without joining tokens back together
and accidentally changing quoting, spacing or redirections. Quoted strings and
nested substitutions are opaque at their parent level and expose their own
children instead.

Unknown or incomplete syntax is retained as text and marked incomplete. That
lets a consumer abstain rather than pretend that a partial parse is an AST.
"""


SEPARATORS = ('&&', '||', '|&', ';', '&', '|', '\n')
REDIRECTIONS = ('&>', '<<<', '>>', '<<', '<>', '>&', '<&', '>|', '>', '<')


class Token(object):
    """One source span in a command structure."""

    __slots__ = ('text', 'start', 'end', 'kind', 'children')

    def __init__(self, text, start, end, kind='word', children=()):
        self.text = text
        self.start = start
        self.end = end
        self.kind = kind
        self.children = tuple(children)

    def as_dict(self):
        result = {
            'text': self.text,
            'start': self.start,
            'end': self.end,
            'kind': self.kind,
        }
        if self.children:
            result['children'] = [child.as_dict() for child in self.children]
        return result


class Segment(object):
    """One command/pipeline member and the separator following it."""

    __slots__ = ('tokens', 'start', 'end', 'separator')

    def __init__(self, tokens, start, end, separator=None):
        self.tokens = tuple(tokens)
        self.start = start
        self.end = end
        self.separator = separator

    @property
    def words(self):
        return tuple(token for token in self.tokens if token.kind == 'word')

    @property
    def command(self):
        """The first ordinary word, or ``None`` for an opaque segment."""
        return self.words[0] if self.words else None

    def as_dict(self):
        command = self.command
        return {
            'start': self.start,
            'end': self.end,
            'separator': self.separator,
            'command': command.text if command else None,
            'tokens': [token.as_dict() for token in self.tokens],
        }


class CommandModel(object):
    """The parsed shape of one command line."""

    __slots__ = ('script', 'shell', 'tokens', 'segments', 'complete')

    def __init__(self, script, shell_name, tokens, segments, complete):
        self.script = script
        self.shell = shell_name
        self.tokens = tuple(tokens)
        self.segments = tuple(segments)
        self.complete = complete

    def as_dict(self):
        return {
            'shell': self.shell,
            'complete': self.complete,
            'segments': [segment.as_dict() for segment in self.segments],
        }

    def command_tokens(self):
        """Return command-position tokens, including nested structures.

        This intentionally knows no shell wrappers or control keywords. A
        caller that has that shell-specific knowledge can use these exact spans
        without losing the model's source-preserving guarantees.
        """
        found = []

        def visit(segment):
            if segment.command is not None:
                found.append(segment.command)
            for token in segment.tokens:
                for child in token.children:
                    visit(child)

        for segment in self.segments:
            visit(segment)
        return tuple(found)


def _is_escaped(script, index):
    count = 0
    index -= 1
    while index >= 0 and script[index] == '\\':
        count += 1
        index -= 1
    return count % 2 == 1


def _matching(script, start, end, opener, closer, shell_name):
    """Find a balanced nested construct, respecting its own quotes."""
    depth = 1
    quote = None
    escaped = False
    index = start
    while index < end:
        character = script[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if shell_name == 'powershell' and character == '`' and quote != "'":
            escaped = True
            index += 1
            continue
        if character == '\\' and quote != "'":
            escaped = True
            index += 1
            continue
        if quote:
            if character == quote:
                quote = None
            index += 1
            continue
        if character in ("'", '"'):
            quote = character
        elif script.startswith(opener, index):
            depth += 1
            index += len(opener) - 1
        elif script.startswith(closer, index):
            depth -= 1
            if depth == 0:
                return index
            index += len(closer) - 1
        index += 1
    return None


def _nested(script, index, end, shell_name):
    """Return ``(token, next_index, complete)`` for nested syntax."""
    if script.startswith('$(', index):
        opener, closer, kind = '$(', ')', 'substitution'
    elif script.startswith('<(', index) or script.startswith('>(', index):
        opener, closer, kind = script[index:index + 2], ')', 'substitution'
    elif script[index] == '(':
        opener, closer, kind = '(', ')', 'group'
    elif script[index] == '{':
        opener, closer, kind = '{', '}', 'group'
    else:
        return None

    closing = _matching(
        script, index + len(opener), end, opener, closer, shell_name)
    if closing is None:
        return Token(script[index:end], index, end, 'opaque'), end, False

    inner_start = index + len(opener)
    inner_tokens, _, inner_complete = _scan(
        script, inner_start, closing, shell_name)
    children = _segments(inner_tokens)
    token = Token(script[index:closing + len(closer)], index,
                  closing + len(closer), kind, children)
    return token, closing + len(closer), inner_complete


def _backtick(script, index, end, shell_name):
    """Return a command-substitution token for POSIX backticks."""
    if shell_name == 'powershell' or script[index] != '`':
        return None

    closing = index + 1
    while closing < end:
        if script[closing] == '`' and not _is_escaped(script, closing):
            inner_tokens, _, inner_complete = _scan(
                script, index + 1, closing, shell_name)
            token = Token(script[index:closing + 1], index, closing + 1,
                          'substitution', _segments(inner_tokens))
            return token, closing + 1, inner_complete
        closing += 1
    return Token(script[index:end], index, end, 'opaque'), end, False


def _scan(script, start, end, shell_name):
    """Scan one level and return ``(tokens, unused, complete)``."""
    tokens = []
    current = None
    complete = True

    def flush(position):
        nonlocal current
        if current is not None and current < position:
            tokens.append(Token(script[current:position], current, position))
        current = None

    index = start
    quote = None
    escaped = False
    separators = tuple(item for item in SEPARATORS
                       if not (shell_name == 'powershell' and item == '&'))
    while index < end:
        character = script[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if shell_name == 'powershell' and character == '`' and quote != "'":
            if current is None:
                current = index
            escaped = True
            index += 1
            continue
        if character == '\\' and quote != "'":
            if current is None:
                current = index
            escaped = True
            index += 1
            continue
        if quote:
            if quote == '"' and script.startswith('$(', index):
                nested = _nested(script, index, end, shell_name)
                if nested is not None:
                    flush(index)
                    token, index, nested_complete = nested
                    tokens.append(token)
                    complete = complete and nested_complete
                    # Still inside the quotes: what follows the substitution
                    # up to the closing quote is the rest of this word, and
                    # used to be dropped, which left the segment ending in
                    # an unbalanced quote.
                    current = index
                    continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in ("'", '"'):
            if current is None:
                current = index
            quote = character
            index += 1
            continue

        nested = (_backtick(script, index, end, shell_name)
                  if character == '`' else
                  _nested(script, index, end, shell_name))
        if nested is not None:
            flush(index)
            token, index, nested_complete = nested
            tokens.append(token)
            complete = complete and nested_complete
            continue
        if character in (' ', '\t', '\r'):
            flush(index)
            index += 1
            continue

        redirection = next((item for item in REDIRECTIONS
                            if script.startswith(item, index)), None)
        if redirection is not None:
            prefix = script[current:index] if current is not None else ''
            if prefix and prefix.isdigit():
                redirection_start = current
                current = None
            else:
                redirection_start = index
                flush(index)
            tokens.append(Token(script[redirection_start:
                                       index + len(redirection)],
                                redirection_start,
                                index + len(redirection), 'redirection'))
            index += len(redirection)
            continue

        separator = next((item for item in separators
                          if script.startswith(item, index)), None)
        if separator is not None:
            flush(index)
            tokens.append(Token(separator, index, index + len(separator),
                                'separator'))
            index += len(separator)
            continue

        if character == '#':
            previous = script[index - 1] if index else ''
            if current is None or previous.isspace():
                flush(index)
                comment_end = script.find('\n', index, end)
                if comment_end == -1:
                    comment_end = end
                tokens.append(Token(script[index:comment_end], index,
                                    comment_end, 'comment'))
                index = comment_end
                continue

        if current is None:
            current = index
        index += 1

    flush(end)
    if quote or escaped:
        complete = False
    return tokens, (), complete


def _segments(tokens):
    segments = []
    current = []

    def finish(separator):
        nonlocal current
        if not current:
            return
        segments.append(Segment(current, current[0].start,
                                current[-1].end, separator))
        current = []

    for token in tokens:
        if token.kind == 'separator':
            finish(token.text)
        else:
            current.append(token)
    finish(None)
    return segments


def parse(script, shell_name='posix'):
    """Parse ``script`` without executing it."""
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    tokens, _, complete = _scan(script, 0, len(script), shell_name)
    return CommandModel(script, shell_name, tokens, _segments(tokens), complete)


def replace_span(script, token, replacement):
    """Replace exactly one token span, preserving everything around it."""
    if token.start < 0 or token.end > len(script) or token.start > token.end:
        return None
    if script[token.start:token.end] != token.text:
        return None
    return script[:token.start] + replacement + script[token.end:]
