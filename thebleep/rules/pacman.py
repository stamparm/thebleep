from thebleep.specific.archlinux import get_pkgfile, archlinux_env
from thebleep.shells import shell
from thebleep.utils import which


def _program(script):
    words = script.split()
    if words[:1] == ['sudo']:
        words = words[1:]
    return words[0] if words else None


def match(command):
    # The program has to be missing, not merely mentioned near "not found":
    # `pacman -S vmi` (`target not found`) was offered a reinstall of pacman,
    # and `pip show x` (`Package(s) not found`) one of pip.
    program = _program(command.script)
    return ('not found' in command.output and program is not None
            and which(program) is None and get_pkgfile(command.script))


def get_new_command(command):
    packages = get_pkgfile(command.script)

    return [shell.and_(u'{} -S {}'.format(pacman, shell.quote(package)),
                       command.script)
            for package in packages]


enabled_by_default, pacman = archlinux_env()
