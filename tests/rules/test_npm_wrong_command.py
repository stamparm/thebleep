import pytest
from thebleep.rules.npm_wrong_command import match, get_new_command
from thebleep.types import Command

output = '''
Usage: npm <command>

where <command> is one of:
    access, add-user, adduser, apihelp, author, bin, bugs, c,
    cache, completion, config, ddp, dedupe, deprecate, dist-tag,
    dist-tags, docs, edit, explore, faq, find, find-dupes, get,
    help, help-search, home, i, info, init, install, issues, la,
    link, list, ll, ln, login, logout, ls, outdated, owner,
    pack, ping, prefix, prune, publish, r, rb, rebuild, remove,
    repo, restart, rm, root, run-script, s, se, search, set,
    show, shrinkwrap, star, stars, start, stop, t, tag, team,
    test, tst, un, uninstall, unlink, unpublish, unstar, up,
    update, upgrade, v, verison, version, view, whoami

npm <cmd> -h     quick help on <cmd>
npm -l           display full usage info
npm faq          commonly asked questions
npm help <term>  search for help on <term>
npm help npm     involved overview

Specify configs in the ini-formatted file:
    /home/nvbn/.npmrc
or on the command line via: npm <command> --key value
Config info can be viewed via: npm help config

npm@2.14.7 /opt/node/lib/node_modules/npm
'''


@pytest.mark.parametrize('script', [
    'npm urgrdae',
    'npm urgrade -g',
    'npm -f urgrade -g',
    'npm urg'])
def test_match(script):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('npm urgrade', ''),
    ('npm', output),
    ('test urgrade', output),
    ('npm -e', output)])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, result', [
    ('npm urgrade', 'npm upgrade'),
    ('npm -g isntall gulp', 'npm -g install gulp'),
    ('npm isntall -g gulp', 'npm install -g gulp')])
def test_get_new_command(script, result):
    assert get_new_command(Command(script, output)) == result


# What npm has said since version 7: no listing, just the answer.
output_modern = '''Unknown command: "{}"


Did you mean this?
  npm install # Install a package
To see a list of supported npm commands, run:
  npm help
'''.format

output_several = '''Unknown command: "{}"


Did you mean one of these?
  npm uninstall # Remove a package
  npm install # Install a package
To see a list of supported npm commands, run:
  npm help
'''.format


@pytest.mark.parametrize('script, output', [
    ('npm nstall', output_modern('nstall')),
    ('npm -g nstall gulp', output_modern('nstall')),
    ('npm uninstal express', output_several('uninstal'))])
def test_match_modern_npm(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output, result', [
    ('npm nstall', output_modern('nstall'), ['npm install']),
    ('npm -g nstall gulp', output_modern('nstall'),
     ['npm -g install gulp']),
    # npm's own order is kept: it knows better than a string distance does.
    ('npm uninstal express', output_several('uninstal'),
     ['npm uninstall express', 'npm install express'])])
def test_get_new_command_modern_npm(script, output, result):
    assert get_new_command(Command(script, output)) == result


def test_legacy_npm_does_not_fall_back_to_first_command():
    assert get_new_command(Command('npm zzzzz', output)) == []


def test_how_to_list_them_all_is_not_a_suggestion(script='npm nstall'):
    """The line after the suggestions tells you to run `npm help`."""
    assert 'npm help' not in get_new_command(
        Command(script, output_modern('nstall')))
