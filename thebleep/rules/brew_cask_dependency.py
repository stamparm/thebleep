from thebleep.utils import for_app, eager, quote_words
from thebleep.shells import shell
from thebleep.specific.brew import brew_available


# brew removed the `cask` command in 2.6 and casks are installed with a flag
# now, so the advice it prints for an unsatisfied cask requirement reads
# `brew install --cask osxfuse`. The old wording is still accepted for a brew
# old enough to have had the command.
CASK_INSTALL = (u'brew install --cask', u'brew cask install')


@for_app('brew')
def match(command):
    return (u'install' in command.script_parts
            and any(line in command.output for line in CASK_INSTALL)
            and bool(_get_cask_install_lines(command.output)))


@eager
def _get_cask_install_lines(output):
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith(CASK_INSTALL):
            yield line


def get_new_command(command):
    # Each line quoted on its own and *then* chained: quoting the chain made
    # `&&` a word, and brew was asked to install a cask by that name.
    lines = _get_cask_install_lines(command.output)
    if not lines:
        return []
    return shell.and_(*([quote_words(line) for line in lines]
                        + [command.script]))


enabled_by_default = brew_available
