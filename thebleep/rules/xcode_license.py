from thebleep.shells import shell
from thebleep.utils import which

enabled_by_default = bool(which('xcodebuild'))

# After an Xcode update the license has to be accepted again. xcodebuild says
# so itself, and names the command:
#   You have not agreed to the Xcode license agreements. Please run 'sudo
#   xcodebuild -license' from within a Terminal window ...
# The xcrun shims behind git, make and clang do not: they run
# `xcodebuild -find` with stderr thrown away, and all that is left is
#   make: error: sh -c '.../xcodebuild -sdk '' -find make 2> /dev/null' failed
#   with exit code 17664 ...
# 17664 is 69 << 8, xcodebuild's exit status for an unaccepted license.
# (Captured on Xcode 16.4 and 26.6; a warm xcrun cache hides the failure.)


def match(command):
    # Already run as root, so adding sudo again would change nothing.
    return ('sudo xcodebuild -license' in command.output
            or 'failed with exit code 17664' in command.output
            ) and command.script_parts[:1] != ['sudo']


def get_new_command(command):
    # `xcodebuild -license` itself only lacked root.
    if command.script_parts[:2] == ['xcodebuild', '-license']:
        return [u'sudo {}'.format(command.script)]

    return [shell.and_(u'sudo xcodebuild -license accept', command.script)]
