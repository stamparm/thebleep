"""
This happens way too often

When typing really fast cause I'm a 1337 H4X0R,
I often mistype 'ls' as 'sl'. No more!
"""


def match(command):
    return command.script == 'sl'


def get_new_command(command):
    return 'ls'
