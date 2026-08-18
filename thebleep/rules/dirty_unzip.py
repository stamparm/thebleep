import zipfile
from thebleep.utils import for_app
from thebleep.shells import shell


def _is_bad_zip(file):
    try:
        with zipfile.ZipFile(file, 'r') as archive:
            return len(archive.namelist()) > 1
    except Exception:
        return False


def _zip_file(command):
    # unzip works that way:
    # unzip [-flags] file[.zip] [file(s) ...] [-x file(s) ...]
    #                ^          ^ files to unzip from the archive
    #                archive to unzip
    for c in command.script_parts[1:]:
        if not c.startswith('-'):
            if c.endswith('.zip'):
                return c
            else:
                return u'{}.zip'.format(c)


@for_app('unzip')
def match(command):
    if '-d' in command.script:
        return False

    zip_file = _zip_file(command)
    if zip_file:
        return _is_bad_zip(zip_file)
    else:
        return False


def get_new_command(command):
    return u'{} -d {}'.format(
        command.script, shell.quote(_zip_file(command)[:-4]))


# There used to be a `side_effect` here that tried to undo the extraction by
# deleting every file named in the archive, and it could not be made safe.
#
# It cannot tell an extracted file from one that was already there under the
# same name, so accepting `unzip -d` deleted the user's own README.md if the
# archive happened to contain one -- data that unzip had already overwritten and
# that nothing could put back.
#
# Its containment check was `os.path.abspath(file).startswith(os.getcwd())`,
# which is a string prefix test and not a path containment test: from
# `/tmp/foo`, an archive member `../foobar/precious` passes it, because
# `/tmp/foobar/precious` does start with `/tmp/foo`. Symlinked directories and
# absolute member names get past it too, in each case deleting something outside
# the directory the user was working in.
#
# So the extracted files are left where they are. What the correction does is
# now exactly what it says: extract into a directory of its own.
requires_output = False
