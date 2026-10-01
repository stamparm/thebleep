from thebleep.shells import shell
from thebleep.utils import which

enabled_by_default = bool(which('xcodebuild'))

# After an Xcode update, every developer tool that goes through the xcrun
# shims -- git, make, clang -- refuses to run until the new license has been
# accepted. Current Xcode prints the whole license and ends with "please accept
# the Xcode license as the root user (e.g. 'sudo xcodebuild -license')"; older
# ones said "You have not agreed to the Xcode license agreements, please run
# 'sudo xcodebuild -license'". Both name the same command.
HINT = "sudo xcodebuild -license"


def _is_license_command(command):
    return command.script_parts[:2] == ['xcodebuild', '-license']


def match(command):
    # Already run as root, so adding sudo again would change nothing.
    return HINT in command.output and command.script_parts[:1] != ['sudo']


def get_new_command(command):
    # Accepting the license by hand was the slip: it only needs root.
    if _is_license_command(command):
        return [u'sudo {}'.format(command.script)]

    # `accept` first, since the license was just printed in full; the
    # interactive one for whoever wants to read it and type `agree`.
    return [shell.and_(u'sudo xcodebuild -license accept', command.script),
            shell.and_(u'sudo xcodebuild -license', command.script)]
