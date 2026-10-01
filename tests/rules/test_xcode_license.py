# -*- coding: utf-8 -*-

import pytest
from thebleep.rules.xcode_license import match, get_new_command
from thebleep.types import Command


# Captured on macOS 15 (Xcode 16.4) and macOS 26 (Xcode 26.6) runners with the
# license unaccepted.
unagreed = (
    "You have not agreed to the Xcode license agreements. Please run "
    "'sudo xcodebuild -license' from within a Terminal window to review and "
    "agree to the Xcode and Apple SDKs license.\n")

needs_admin = (
    u"\nAgreeing to the Xcode and SDK licenses requires admin privileges, "
    u"please run ‘sudo xcodebuild -license’ and then retry this "
    u"command.\n\n")

make_shim = (
    "make: error: sh -c '/Applications/Xcode_26.6.app/Contents/Developer/usr/"
    "bin/xcodebuild -sdk '' -find make 2> /dev/null' failed with exit code "
    "17664: (null) (errno=No such file or directory)\n"
    "xcode-select: Failed to locate 'make', requesting installation of "
    "command line developer tools.\n")


@pytest.mark.parametrize('script, output', [
    ('make', make_shim),
    ('git clone https://example.com/x.git', make_shim),
    ('xcodebuild -license', unagreed),
    ('xcodebuild -license accept', needs_admin),
    ('xcodebuild -license check', unagreed)])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('make', ''),
    ('git status', 'fatal: not a git repository'),
    # the same shim failure for any other reason
    ('make', make_shim.replace('17664', '256')),
    # no developer tools at all is a different problem
    ('make', "xcode-select: Failed to locate 'make', requesting installation "
             "of command line developer tools.\n"),
    ('sudo xcodebuild -license', unagreed),
    ('sudo xcodebuild -license accept', needs_admin)])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, output, new_command', [
    ('make', make_shim, ['sudo xcodebuild -license accept && make']),
    ('git clone https://example.com/x.git', make_shim,
     ['sudo xcodebuild -license accept && git clone https://example.com/x.git']),
    ('xcodebuild -license', unagreed, ['sudo xcodebuild -license']),
    ('xcodebuild -license accept', needs_admin,
     ['sudo xcodebuild -license accept'])])
def test_get_new_command(script, output, new_command):
    assert get_new_command(Command(script, output)) == new_command
