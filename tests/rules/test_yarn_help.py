import shlex
import pytest
from thebleep.rules.yarn_help import match, get_new_command
from thebleep.types import Command
from thebleep.system import open_command


output_clean = '''

  Usage: yarn [command] [flags]

  Options:

    -h, --help                      output usage information
    -V, --version                   output the version number
    --verbose                       output verbose messages on internal operations
    --offline                       trigger an error if any required dependencies are not available in local cache
    --prefer-offline                use network only if dependencies are not available in local cache
    --strict-semver                 
    --json                          
    --ignore-scripts                don't run lifecycle scripts
    --har                           save HAR output of network traffic
    --ignore-platform               ignore platform checks
    --ignore-engines                ignore engines check
    --ignore-optional               ignore optional dependencies
    --force                         ignore all caches
    --no-bin-links                  don't generate bin links when setting up packages
    --flat                          only allow one version of a package
    --prod, --production [prod]     
    --no-lockfile                   don't read or generate a lockfile
    --pure-lockfile                 don't generate a lockfile
    --frozen-lockfile               don't generate a lockfile and fail if an update is needed
    --link-duplicates               create hardlinks to the repeated modules in node_modules
    --global-folder <path>          
    --modules-folder <path>         rather than installing modules into the node_modules folder relative to the cwd, output them here
    --cache-folder <path>           specify a custom folder to store the yarn cache
    --mutex <type>[:specifier]      use a mutex to ensure only one yarn instance is executing
    --no-emoji                      disable emoji in output
    --proxy <host>                  
    --https-proxy <host>            
    --no-progress                   disable progress bar
    --network-concurrency <number>  maximum number of concurrent network requests

  Visit https://yarnpkg.com/en/docs/cli/clean for documentation about this command.
'''  # noqa


@pytest.mark.parametrize('command', [
    Command('yarn help clean', output_clean)])
def test_match(command):
    assert match(command)


def test_match_accepts_environment_assignments():
    assert match(Command('YARN_SILENT=1 yarn help clean', output_clean))


@pytest.mark.parametrize('command, url', [
    (Command('yarn help clean', output_clean),
     'https://yarnpkg.com/en/docs/cli/clean')])
def test_get_new_command(command, url):
    assert get_new_command(command) == open_command(url)


@pytest.mark.parametrize('url', [
    'https://example.com;touch${IFS}/tmp/poc',
    'https://example.com&&id',
    'https://example.com`id`',
    'https://example.com$(id)',
    'https://example.com|id',
    "https://example.com';id;'",
])
def test_a_hostile_url_stays_one_argument(url):
    """The URL comes out of yarn's output, and the command we return is
    evaluated by the shell, so anything in it has to survive as data."""
    output = 'Visit {} for documentation about this command.'.format(url)
    new_command = get_new_command(Command('yarn help clean', output))

    # Whatever this platform's opener is — `xdg-open URL`, `open URL` or
    # `cmd /c start URL` — the URL has to be the whole of its last argument.
    opener = shlex.split(open_command('PLACEHOLDER'))
    assert opener[-1] == 'PLACEHOLDER'
    assert shlex.split(new_command) == opener[:-1] + [url]
