from thebleep.specific.archlinux import get_pkgfile, archlinux_env
from thebleep.shells import shell


def match(command):
    return 'not found' in command.output and get_pkgfile(command.script)


def get_new_command(command):
    packages = get_pkgfile(command.script)

    return [shell.and_(u'{} -S {}'.format(pacman, shell.quote(package)),
                       command.script)
            for package in packages]


enabled_by_default, pacman = archlinux_env()
