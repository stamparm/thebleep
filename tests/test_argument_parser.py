import pytest
from thebleep.argument_parser import Parser
from thebleep.const import ARGUMENT_PLACEHOLDER


def _args(**override):
    args = {'alias': None, 'command': [], 'yes': False,
            'help': False, 'version': False, 'debug': False,
            'force_command': None, 'repeat': False,
            'enable_experimental_instant_mode': False,
            'shell_logger': None}
    args.update(override)
    return args


@pytest.mark.parametrize('argv, result', [
    (['thebleep'], _args()),
    (['thebleep', '-a'], _args(alias='bleep')),
    (['thebleep', '--alias', '--enable-experimental-instant-mode'],
     _args(alias='bleep', enable_experimental_instant_mode=True)),
    (['thebleep', '-a', 'fix'], _args(alias='fix')),
    (['thebleep', 'git', 'branch', ARGUMENT_PLACEHOLDER, '-y'],
     _args(command=['git', 'branch'], yes=True)),
    (['thebleep', 'git', 'branch', '-a', ARGUMENT_PLACEHOLDER, '-y'],
     _args(command=['git', 'branch', '-a'], yes=True)),
    (['thebleep', ARGUMENT_PLACEHOLDER, '-v'], _args(version=True)),
    (['thebleep', ARGUMENT_PLACEHOLDER, '--help'], _args(help=True)),
    (['thebleep', 'git', 'branch', '-a', ARGUMENT_PLACEHOLDER, '-y', '-d'],
     _args(command=['git', 'branch', '-a'], yes=True, debug=True)),
    (['thebleep', 'git', 'branch', '-a', ARGUMENT_PLACEHOLDER, '-r', '-d'],
     _args(command=['git', 'branch', '-a'], repeat=True, debug=True)),
    (['thebleep', '-l', '/tmp/log'], _args(shell_logger='/tmp/log')),
    (['thebleep', '--shell-logger', '/tmp/log'],
     _args(shell_logger='/tmp/log'))])
def test_parse(argv, result):
    assert vars(Parser().parse(argv)) == result
