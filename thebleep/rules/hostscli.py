# -*- encoding: utf-8 -*-

"""`hostscli blck` -> `hostscli block`, and the website that is not there.

The subcommand half was dead. It read the name out of the error with

    re.findall(r'Error: No such command ".*"', command.output)[0]

-- a pattern with no capturing group, so `findall` handed back the whole matched
sentence, `Error: No such command "blck"`. That string was then looked for in
the command the user typed, where it has never appeared, so the closeness match
had nothing to work on and the rule offered nothing. Every time.

The wording had moved too. hostscli is a Click program, and Click switched from
double quotes to single ones, so on any current install the pattern did not
match at all:

    $ hostscli blck
    Error: No such command 'blck'. (Did you mean one of: 'block', 'block-all',
    'unblock'?)

Which is also the form `click_suggestion` reads, and it does better than this
can: those are the commands Click itself thinks are close, from the program's
own list, rather than a list written down here. So this now stands aside when
Click has answered, and keeps the list only for the versions that do not.

The command list was wrong in the same quiet way -- `block_all` and
`unblock_all`, where the program spells them `block-all` and `unblock-all`.

Captured from hostscli 0.2 on Click 8.4.

"""

import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import replace_command, for_app

no_command = "Error: No such command"
no_website = "hostscli.errors.WebsiteImportError"

# Either quote style, and a capturing group this time.
MISSPELLED = re.compile(r'No such command [\'"]([^\'"]+)[\'"]')

# What `hostscli --help` lists, with the hyphens it really uses.
COMMANDS = ('block', 'block-all', 'unblock', 'unblock-all', 'websites')

# Click's own suggestion, which `click_suggestion` turns into a correction.
CLICK_SUGGESTED = 'Did you mean'


@sudo_support
@for_app('hostscli')
def match(command):
    if no_website in command.output:
        return True

    return (no_command in command.output
            and CLICK_SUGGESTED not in command.output
            and MISSPELLED.search(command.output) is not None)


@sudo_support
def get_new_command(command):
    if no_website in command.output:
        return ['hostscli websites']

    found = MISSPELLED.search(command.output)
    if not found:
        return []

    return replace_command(command, found.group(1), COMMANDS)
