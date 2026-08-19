import pytest
from thebleep.argument_parser import Parser, _fast_parse
from thebleep.const import ARGUMENT_PLACEHOLDER


def _args(**override):
    args = {'alias': None, 'alias_loader': None, 'clear_cache': False,
            'command': [], 'yes': False,
            'help': False, 'version': False, 'debug': False,
            'force_command': None, 'repeat': False, 'edit': False,
            'doctor': False, 'explain': False,
            'enable_experimental_instant_mode': False,
            'shell': None, 'shell_logger': None}
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
    (['thebleep', 'git', 'branch', ARGUMENT_PLACEHOLDER, '--edit'],
     _args(command=['git', 'branch'], edit=True)),
    (['thebleep', '--clear-cache'], _args(clear_cache=True)),
    (['thebleep', '--alias-loader'], _args(alias_loader='bleep')),
    (['thebleep', '--alias-loader', 'fix'], _args(alias_loader='fix')),
    (['thebleep', '-l', '/tmp/log'], _args(shell_logger='/tmp/log')),
    (['thebleep', '--shell-logger', '/tmp/log'],
     _args(shell_logger='/tmp/log')),
    (['thebleep', '--shell', 'fish'], _args(shell='fish')),
    (['thebleep', 'git', 'branch', ARGUMENT_PLACEHOLDER, '--shell', 'fish'],
     _args(command=['git', 'branch'], shell='fish')),
    (['thebleep', '--doctor'], _args(doctor=True)),
    (['thebleep', 'git', 'branch', ARGUMENT_PLACEHOLDER, '--explain'],
     _args(command=['git', 'branch'], explain=True))])
def test_parse(argv, result):
    assert vars(Parser().parse(argv)) == result


# Every shape the fast path claims to understand has to come out of it exactly
# as argparse would have produced it, or the shortcut is a bug.
FAST_PATH_SHAPES = [
    ['thebleep'],
    ['thebleep', 'git', 'branch'],
    ['thebleep', 'git', 'branch', '-a'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-y'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--yes'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--yeah'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--hard'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-r'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--repeat'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-d'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--debug'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-y', '-d'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-r', '-d'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-e'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--explain'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--edit'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-e', '-y'],
    ['thebleep', 'git', 'commit', '-m', 'a message', ARGUMENT_PLACEHOLDER, '-y'],
    ['thebleep', u'echo café', ARGUMENT_PLACEHOLDER],
]

# Shapes it must decline, leaving argparse to deal with them.
ARGPARSE_SHAPES = [
    ['thebleep', '-v'],
    ['thebleep', '--version'],
    ['thebleep', '-h'],
    ['thebleep', '--help'],
    ['thebleep', '-a'],
    ['thebleep', '--alias', 'fix'],
    ['thebleep', '--alias-loader'],
    ['thebleep', '--clear-cache'],
    ['thebleep', '-l', '/tmp/log'],
    ['thebleep', '--force-command', 'git brnch'],
    ['thebleep', '--enable-experimental-instant-mode'],
    ['thebleep', '--shell', 'fish'],
    ['thebleep', '--doctor'],
    ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '--nonsense'],
]


def _via_argparse(argv):
    parser = Parser()
    arguments = parser._prepare_arguments(argv[1:])
    return vars(parser._build().parse_args(arguments))


@pytest.mark.parametrize('argv', FAST_PATH_SHAPES)
def test_fast_path_agrees_with_argparse(argv):
    parser = Parser()
    arguments = parser._prepare_arguments(argv[1:])
    fast = _fast_parse(arguments)
    assert fast is not None, 'expected the fast path to handle this'
    assert vars(fast) == _via_argparse(argv)


@pytest.mark.parametrize('argv', ARGPARSE_SHAPES)
def test_fast_path_declines_what_it_cannot_do(argv):
    parser = Parser()
    assert _fast_parse(parser._prepare_arguments(argv[1:])) is None


def test_contradictory_switches_still_error():
    """`-y` with `-r` is refused by argparse, so the fast path must defer."""
    argv = ['thebleep', 'ls', ARGUMENT_PLACEHOLDER, '-y', '-r']
    parser = Parser()
    assert _fast_parse(parser._prepare_arguments(argv[1:])) is None
    with pytest.raises(SystemExit):
        parser.parse(argv)


def test_argparse_is_not_imported_for_a_correction(mocker):
    """The whole point: correcting a command must not build a parser."""
    parser = Parser()
    build = mocker.patch.object(parser, '_build')
    parser.parse(['thebleep', 'git', 'brnch', ARGUMENT_PLACEHOLDER, '-y'])
    assert not build.called
