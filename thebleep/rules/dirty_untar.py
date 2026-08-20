from thebleep.utils import for_app
from thebleep.shells import shell


tar_extensions = ('.tar', '.tar.Z', '.tar.bz2', '.tar.gz', '.tar.lz',
                  '.tar.lzma', '.tar.xz', '.taz', '.tb2', '.tbz', '.tbz2',
                  '.tgz', '.tlz', '.txz', '.tz')


def _is_tar_extract(cmd):
    if '--extract' in cmd:
        return True

    cmd = cmd.split()

    return len(cmd) > 1 and 'x' in cmd[1]


def _tar_file(cmd):
    for c in cmd:
        for ext in tar_extensions:
            if c.endswith(ext):
                return (c, c[0:len(c) - len(ext)])


@for_app('tar')
def match(command):
    return ('-C' not in command.script
            and _is_tar_extract(command.script)
            and _tar_file(command.script_parts) is not None)


def get_new_command(command):
    dir = shell.quote(_tar_file(command.script_parts)[1])
    return shell.and_('{} {{dir}}'.format(shell.mkdir_command()),
                      '{cmd} -C {dir}') \
        .format(dir=dir, cmd=command.script)


# There used to be a `side_effect` here that tried to undo the extraction by
# deleting every file named in the archive. See `dirty_unzip` for why it could
# not be made safe: it deleted files the user already had under the same name,
# and its containment check was a string prefix test that a `../` member walks
# straight out of. The extracted files are left where they are.
