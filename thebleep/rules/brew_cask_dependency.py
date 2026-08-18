from thebleep.utils import for_app, eager
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
            and any(line in command.output for line in CASK_INSTALL))


@eager
def _get_cask_install_lines(output):
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith(CASK_INSTALL):
            yield line


def _get_script_for_brew_cask(output):
    cask_install_lines = _get_cask_install_lines(output)
    if len(cask_install_lines) > 1:
        return shell.and_(*cask_install_lines)
    else:
        return cask_install_lines[0]


def get_new_command(command):
    brew_cask_script = _get_script_for_brew_cask(command.output)
    return shell.and_(brew_cask_script, command.script)


enabled_by_default = brew_available
