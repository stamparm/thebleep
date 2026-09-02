# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.wrong_directory import get_new_command, match
from thebleep.types import Command


# Every message below was printed by the named program run in an empty
# directory: git 2.43.0, GNU Make 4.3, npm 11.19.0, pnpm 11.25.0, yarn
# 1.22.17, cargo 1.98.0, Maven 3, Docker Compose v2.27.0, just 1.26.0,
# go-task, uv 0.9.30, Poetry 2.4.2, Terraform 1.9.
GIT = 'fatal: not a git repository (or any of the parent directories): .git'
MAKE_NONE = 'make: *** No targets specified and no makefile found.  Stop.'
MAKE_TARGET = "make: *** No rule to make target 'build'.  Stop."
NPM_ENOENT = (
    'npm error code ENOENT\n'
    'npm error syscall open\n'
    'npm error path /tmp/x/package.json\n'
    'npm error errno -2\n'
    'npm error enoent Could not read package.json: Error: ENOENT: no such '
    "file or directory, open '/tmp/x/package.json'\n"
    'npm error enoent This is related to npm not being able to find a file.\n')
NPM_SCRIPT = (
    'npm error Missing script: "build"\n'
    'npm error\n'
    'npm error To see a list of scripts, run:\n'
    'npm error   npm run\n')
PNPM_NONE = ('[ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND] No package.json (or '
             'package.yaml, or package.json5) was found in "/tmp/x".')
PNPM_SCRIPT = ('[ERR_PNPM_NO_SCRIPT] Missing script: build\n\n'
               'Command "build" not found.\n')
YARN = ('yarn run v1.22.17\n'
        'error Couldn\'t find a package.json file in "/tmp/x"\n'
        'info Visit https://yarnpkg.com/en/docs/cli/run for documentation '
        'about this command.\n')
CARGO = ('error: could not find `Cargo.toml` in `/tmp/x` or any parent '
         'directory')
MVN = ('[ERROR] The goal you specified requires a project to execute but '
       'there is no POM in this directory (/tmp/x). Please verify you '
       'invoked Maven from the correct directory. -> [Help 1]')
COMPOSE = 'no configuration file provided: not found'
JUST_NONE = 'error: No justfile found'
JUST_RECIPE = 'error: Justfile does not contain recipe `build`.'
TASK = 'task: No Taskfile found at "/tmp/x"'
UV = ('error: No `pyproject.toml` found in current directory or any parent '
      'directory')
POETRY = 'Poetry could not find a pyproject.toml file in /tmp/x or its parents'
TERRAFORM = ('╷\n│ Error: No configuration files\n│\n│ Plan requires '
             'configuration to be present.')


@pytest.fixture
def here(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    return tmpdir


def project(root, name, **files):
    directory = root.ensure(name, dir=True)
    for filename, content in files.items():
        directory.join(filename).write(content)
    return directory


@pytest.mark.parametrize('script, output', [
    ('git status', GIT), ('make', MAKE_NONE), ('make build', MAKE_TARGET),
    ('npm run build', NPM_ENOENT), ('npm run build', NPM_SCRIPT),
    ('pnpm run build', PNPM_NONE), ('pnpm build', PNPM_SCRIPT),
    ('yarn build', YARN), ('cargo build', CARGO), ('mvn compile', MVN),
    ('docker compose up -d', COMPOSE), ('just build', JUST_NONE),
    ('just build', JUST_RECIPE), ('task build', TASK), ('uv sync', UV),
    ('poetry install', POETRY), ('terraform plan', TERRAFORM)])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('git status', 'On branch master'),
    ('ls', GIT),
    ('make build', 'make: Nothing to be done for build.'),
    ('npm run build', '> build\n> tsc'),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


class TestGit(object):
    def test_the_one_checkout_below(self, here):
        project(here, 'repo', **{'.git': ''}).join('.git').remove()
        here.join('repo').ensure('.git', dir=True)
        here.ensure('notes', dir=True)
        assert get_new_command(Command('git status', GIT)) == [
            'cd repo && git status']

    def test_a_worktree_whose_dot_git_is_a_file(self, here):
        here.ensure('wt', dir=True).join('.git').write('gitdir: /elsewhere')
        assert get_new_command(Command('git log', GIT)) == ['cd wt && git log']

    def test_two_checkouts_is_a_guess_and_says_nothing(self, here):
        here.ensure('a', dir=True).ensure('.git', dir=True)
        here.ensure('b', dir=True).ensure('.git', dir=True)
        assert get_new_command(Command('git status', GIT)) == []

    def test_the_parent_is_not_offered(self, here):
        """git already looked there itself."""
        here.ensure('.git', dir=True)
        inside = here.ensure('src', dir=True)
        inside.chdir()
        assert get_new_command(Command('git status', GIT)) == []

    def test_two_levels_down(self, here):
        here.ensure('work', 'repo', dir=True).ensure('.git', dir=True)
        assert get_new_command(Command('git status', GIT)) == [
            'cd work/repo && git status']

    def test_hidden_and_dependency_directories_are_not_entered(self, here):
        here.ensure('.cache', 'repo', dir=True).ensure('.git', dir=True)
        here.ensure('node_modules', 'pkg', dir=True).ensure('.git', dir=True)
        assert get_new_command(Command('git status', GIT)) == []


class TestNpm(object):
    def test_the_child_that_declares_the_script(self, here):
        project(here, 'app', **{'package.json':
                                '{"scripts": {"build": "tsc"}}'})
        project(here, 'docs', **{'package.json':
                                 '{"scripts": {"serve": "x"}}'})
        got = get_new_command(Command('npm run build', NPM_ENOENT))
        assert got == ['cd app && npm run build']
        assert got[0].confidence == 0.9
        assert got[0].evidence == ('app/package.json declares build',)

    def test_a_root_manifest_without_the_script(self, here):
        here.join('package.json').write('{"scripts": {"lint": "x"}}')
        here.ensure('packages', 'web', dir=True).join('package.json').write(
            '{"scripts": {"build": "vite build"}}')
        assert get_new_command(Command('npm run build', NPM_SCRIPT)) == [
            'cd packages/web && npm run build']

    def test_several_children_declare_it(self, here):
        for name in ('a', 'b', 'c', 'd'):
            project(here, name, **{'package.json':
                                   '{"scripts": {"build": "x"}}'})
        got = get_new_command(Command('npm run build', NPM_ENOENT))
        assert got == ['cd a && npm run build', 'cd b && npm run build',
                       'cd c && npm run build']
        assert all(suggestion.confidence == 0.7 for suggestion in got)

    def test_no_child_declares_it(self, here):
        project(here, 'app', **{'package.json': '{"scripts": {"test": "x"}}'})
        assert get_new_command(Command('npm run build', NPM_ENOENT)) == []

    def test_a_lifecycle_script(self, here):
        project(here, 'app', **{'package.json': '{"scripts": {"test": "x"}}'})
        assert get_new_command(Command('npm test', NPM_ENOENT)) == [
            'cd app && npm test']

    def test_a_command_naming_no_script_needs_one_manifest(self, here):
        project(here, 'app', **{'package.json': '{}'})
        assert get_new_command(Command('npm install', NPM_ENOENT)) == [
            'cd app && npm install']
        project(here, 'other', **{'package.json': '{}'})
        assert get_new_command(Command('npm install', NPM_ENOENT)) == []

    def test_pnpm_and_yarn(self, here):
        project(here, 'app', **{'package.json':
                                '{"scripts": {"build": "x"}}'})
        assert get_new_command(Command('pnpm run build', PNPM_NONE)) == [
            'cd app && pnpm run build']
        assert get_new_command(Command('pnpm build', PNPM_SCRIPT)) == [
            'cd app && pnpm build']
        assert get_new_command(Command('yarn build', YARN)) == [
            'cd app && yarn build']
        assert get_new_command(Command('yarn run build', YARN)) == [
            'cd app && yarn run build']


class TestMake(object):
    def test_the_child_whose_makefile_has_the_target(self, here):
        here.join('Makefile').write('test:\n\t@true\n')
        project(here, 'app', Makefile='build:\n\t@true\n')
        assert get_new_command(Command('make build', MAKE_TARGET)) == [
            'cd app && make build']

    def test_the_parent_because_make_does_not_look_there(self, here):
        here.join('Makefile').write('build:\n\t@true\n')
        here.ensure('src', dir=True).chdir()
        assert get_new_command(Command('make build', MAKE_TARGET)) == [
            'cd .. && make build']

    def test_bare_make_needs_one_makefile(self, here):
        project(here, 'app', Makefile='all:\n\t@true\n')
        assert get_new_command(Command('make', MAKE_NONE)) == [
            'cd app && make']
        project(here, 'lib', Makefile='all:\n\t@true\n')
        assert get_new_command(Command('make', MAKE_NONE)) == []

    def test_options_are_not_targets(self, here):
        project(here, 'app', Makefile='build:\n\t@true\n')
        assert get_new_command(Command('make -j4 build', MAKE_TARGET)) == [
            'cd app && make -j4 build']


class TestOtherTools(object):
    def test_cargo(self, here):
        project(here, 'crate', **{'Cargo.toml': '[package]\nname = "c"\n'})
        assert get_new_command(Command('cargo build', CARGO)) == [
            'cd crate && cargo build']

    def test_maven_looks_at_the_parent_too(self, here):
        here.join('pom.xml').write('<project/>')
        here.ensure('src', dir=True).chdir()
        assert get_new_command(Command('mvn compile', MVN)) == [
            'cd .. && mvn compile']

    def test_docker_compose(self, here):
        project(here, 'stack', **{'compose.yaml': 'services: {}\n'})
        assert get_new_command(Command('docker compose up -d', COMPOSE)) == [
            'cd stack && docker compose up -d']

    def test_docker_without_compose_is_not_this(self, here):
        project(here, 'stack', **{'compose.yaml': 'services: {}\n'})
        assert get_new_command(Command('docker up', COMPOSE)) == []

    def test_just(self, here):
        project(here, 'app', justfile='build:\n\t@true\n')
        assert get_new_command(Command('just build', JUST_NONE)) == [
            'cd app && just build']
        here.join('justfile').write('test:\n\t@true\n')
        assert get_new_command(Command('just build', JUST_RECIPE)) == [
            'cd app && just build']

    def test_task(self, here):
        project(here, 'app', **{'Taskfile.yml':
                                'version: "3"\ntasks:\n  build:\n    cmds:\n'
                                '      - true\n'})
        assert get_new_command(Command('task build', TASK)) == [
            'cd app && task build']

    def test_uv_and_poetry(self, here):
        project(here, 'pkg', **{'pyproject.toml': '[project]\nname = "p"\n'})
        assert get_new_command(Command('uv sync', UV)) == ['cd pkg && uv sync']
        assert get_new_command(Command('poetry install', POETRY)) == [
            'cd pkg && poetry install']

    def test_terraform(self, here):
        project(here, 'infra', **{'main.tf': ''})
        assert get_new_command(Command('terraform plan', TERRAFORM)) == [
            'cd infra && terraform plan']


def test_a_hostile_directory_name_is_quoted(here):
    here.ensure(u'repo$(touch pwned)', dir=True).ensure('.git', dir=True)
    assert get_new_command(Command('git status', GIT)) == [
        "cd 'repo$(touch pwned)' && git status"]


def test_nothing_nearby_says_nothing(here):
    assert get_new_command(Command('git status', GIT)) == []
    assert get_new_command(Command('cargo build', CARGO)) == []


def test_an_unknown_program_says_nothing(here):
    assert get_new_command(Command('gradle build', MVN)) == []
