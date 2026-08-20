from thebleep.utils import replace_argument
from thebleep.specific.git import git_support


@git_support
def match(command):
    # git prints `(with two dashes)?` -- the question mark is outside the
    # bracket. This wanted `(with two dashes ?)`, which no git in current use
    # prints, so the rule never fired: verified dead against 2.30.2, 2.39.5 and
    # 2.47.3, all three of which agree on the wording. The older form is still
    # accepted rather than swapped out.
    return ('error: did you mean `' in command.output
            and '(with two dashes' in command.output)


@git_support
def get_new_command(command):
    to = command.output.split('`')[1]
    return replace_argument(command.script, to[1:], to)
