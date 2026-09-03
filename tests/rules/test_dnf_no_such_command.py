import pytest
from thebleep.types import Command
from thebleep.rules.dnf_no_such_command import match, get_new_command, _get_operations


help_text = b'''usage: dnf [options] COMMAND

List of Main Commands:

autoremove                remove all unneeded packages that were originally installed as dependencies
check                     check for problems in the packagedb
check-update              check for available package upgrades
clean                     remove cached data
deplist                   List package's dependencies and what packages provide them
distro-sync               synchronize installed packages to the latest available versions
downgrade                 Downgrade a package
group                     display, or use, the groups information
help                      display a helpful usage message
history                   display, or use, the transaction history
info                      display details about a package or group of packages
install                   install a package or packages on your system
list                      list a package or groups of packages
makecache                 generate the metadata cache
mark                      mark or unmark installed packages as installed by user.
provides                  find what package provides the given value
reinstall                 reinstall a package
remove                    remove a package or packages from your system
repolist                  display the configured software repositories
repoquery                 search for packages matching keyword
repository-packages       run commands on top of all packages in given repository
search                    search package details for the given string
shell                     run an interactive DNF shell
swap                      run an interactive dnf mod for remove and install one spec
updateinfo                display advisories about packages
upgrade                   upgrade a package or packages on your system
upgrade-minimal           upgrade, but only 'newest' package match which fixes a problem that affects your system

List of Plugin Commands:

builddep                  Install build dependencies for package or spec file
config-manager            manage dnf configuration options and repositories
copr                      Interact with Copr repositories.
debug-dump                dump information about installed rpm packages to file
debug-restore             restore packages recorded in debug-dump file
debuginfo-install         install debuginfo packages
download                  Download package to current directory
needs-restarting          determine updated binaries that need restarting
playground                Interact with Playground repository.
repoclosure               Display a list of unresolved dependencies for repositories
repograph                 Output a full package dependency graph in dot format
repomanage                Manage a directory of rpm packages
reposync                  download all packages from remote repo

Optional arguments:
  -c [config file], --config [config file]
                        config file location
  -q, --quiet           quiet operation
  -v, --verbose         verbose operation
  --version             show DNF version and exit
  --installroot [path]  set install root
  --nodocs              do not install documentations
  --noplugins           disable all plugins
  --enableplugin [plugin]
                        enable plugins by name
  --disableplugin [plugin]
                        disable plugins by name
  --releasever RELEASEVER
                        override the value of $releasever in config and repo
                        files
  --setopt SETOPTS      set arbitrary config and repo options
  --skip-broken         resolve depsolve problems by skipping packages
  -h, --help, --help-cmd
                        show command help
  --allowerasing        allow erasing of installed packages to resolve
                        dependencies
  -b, --best            try the best available package versions in
                        transactions.
  -C, --cacheonly       run entirely from system cache, don't update cache
  -R [minutes], --randomwait [minutes]
                        maximum command wait time
  -d [debug level], --debuglevel [debug level]
                        debugging output level
  --debugsolver         dumps detailed solving results into files
  --showduplicates      show duplicates, in repos, in list/search commands
  -e ERRORLEVEL, --errorlevel ERRORLEVEL
                        error output level
  --obsoletes           enables dnf's obsoletes processing logic for upgrade
                        or display capabilities that the package obsoletes for
                        info, list and repoquery
  --rpmverbosity [debug level name]
                        debugging output level for rpm
  -y, --assumeyes       automatically answer yes for all questions
  --assumeno            automatically answer no for all questions
  --enablerepo [repo]
  --disablerepo [repo]
  --repo [repo], --repoid [repo]
                        enable just specific repositories by an id or a glob,
                        can be specified multiple times
  -x [package], --exclude [package], --excludepkgs [package]
                        exclude packages by name or glob
  --disableexcludes [repo], --disableexcludepkgs [repo]
                        disable excludepkgs
  --repofrompath [repo,path]
                        label and path to additional repository, can be
                        specified multiple times.
  --noautoremove        disable removal of dependencies that are no longer
                        used
  --nogpgcheck          disable gpg signature checking
  --color COLOR         control whether colour is used
  --refresh             set metadata as expired before running the command
  -4                    resolve to IPv4 addresses only
  -6                    resolve to IPv6 addresses only
  --destdir DESTDIR, --downloaddir DESTDIR
                        set directory to copy packages to
  --downloadonly        only download packages
  --bugfix              Include bugfix relevant packages, in updates
  --enhancement         Include enhancement relevant packages, in updates
  --newpackage          Include newpackage relevant packages, in updates
  --security            Include security relevant packages, in updates
  --advisory ADVISORY, --advisories ADVISORY
                        Include packages needed to fix the given advisory, in
                        updates
  --bzs BUGZILLA        Include packages needed to fix the given BZ, in
                        updates
  --cves CVES           Include packages needed to fix the given CVE, in
                        updates
  --sec-severity {Critical,Important,Moderate,Low}, --secseverity {Critical,Important,Moderate,Low}
                        Include security relevant packages matching the
                        severity, in updates
  --forcearch ARCH      Force the use of an architecture
'''

dnf_operations = ['autoremove', 'check', 'check-update', 'clean', 'deplist',
                  'distro-sync', 'downgrade', 'group', 'help', 'history',
                  'info', 'install', 'list', 'makecache', 'mark', 'provides',
                  'reinstall', 'remove', 'repolist', 'repoquery',
                  'repository-packages', 'search', 'shell', 'swap', 'updateinfo',
                  'upgrade', 'upgrade-minimal', 'builddep', 'config-manager',
                  'copr', 'debug-dump', 'debug-restore', 'debuginfo-install',
                  'download', 'needs-restarting', 'playground', 'repoclosure',
                  'repograph', 'repomanage', 'reposync']


def invalid_command(command):
    return """No such command: %s. Please use /usr/bin/dnf --help
It could be a DNF plugin command, try: "dnf install 'dnf-command(%s)'"
""" % (command, command)


@pytest.mark.parametrize('output', [
    (invalid_command('saerch')),
    (invalid_command('isntall'))
])
def test_match(output):
    assert match(Command('dnf', output))


@pytest.mark.parametrize('script, output', [
    ('pip', invalid_command('isntall')),
    ('vim', "")
])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.fixture
def set_help(mocker):
    mock = mocker.patch('thebleep.rules.dnf_no_such_command.tool_output')

    def _set_text(text):
        mock.return_value = text.decode('utf-8')

    return _set_text


def test_get_operations(set_help):
    set_help(help_text)
    assert _get_operations() == dnf_operations


@pytest.mark.parametrize('script, output, result', [
    ('dnf isntall vim', invalid_command('isntall'),
     'dnf install vim'),
    ('dnf saerch vim', invalid_command('saerch'),
     'dnf search vim'),
])
def test_get_new_command(set_help, output, script, result):
    set_help(help_text)
    assert result in get_new_command(Command(script, output))


# dnf 5, from `fedora:latest` (Fedora 44, dnf5 5.4.3.0): `dnf isntall vim`,
# verbatim, and the shape of its `--help`.
DNF5_UNKNOWN = u'''Unknown argument "isntall" for command "dnf5". Add "--help" \
for more information about the arguments.
It could be a command provided by a plugin, try: dnf5 install \
'dnf5-command(isntall)'
'''

DNF5_HELP = u'''Usage:
  dnf5 [GLOBAL OPTIONS] <COMMAND> ...

Description:
  DNF5 is a program for maintaining packages.

Software Management Commands:
  do                                     Do transaction
  install                                Install software
  upgrade                                Upgrade software
  remove                                 Remove (uninstall) software
  distro-sync                            Upgrade or downgrade installed software

Query Commands:
  leaves                                 List groups of installed packages
  search                                 Search for software matching all specified strings
  list                                   Lists packages depending on the packages' relation

Compatibility Aliases:
  check-update                           Alias for 'check-upgrade'
  if                                     Alias for 'info'
'''


def test_dnf5_wording_matches():
    assert match(Command('dnf isntall vim', DNF5_UNKNOWN))
    assert match(Command('dnf5 isntall vim', DNF5_UNKNOWN))


def test_dnf5_help_is_parsed():
    from thebleep.rules.dnf_no_such_command import _parse_operations

    assert _parse_operations(DNF5_HELP) == [
        'do', 'install', 'upgrade', 'remove', 'distro-sync', 'leaves',
        'search', 'list', 'check-update', 'if']


def test_dnf5_typo_is_corrected(mocker):
    mocker.patch('thebleep.rules.dnf_no_such_command.tool_output',
                 return_value=DNF5_HELP)
    assert get_new_command(Command('dnf isntall vim', DNF5_UNKNOWN))[0] == \
        'dnf install vim'
    assert get_new_command(Command('sudo dnf isntall vim', DNF5_UNKNOWN))[0] \
        == 'sudo dnf install vim'
