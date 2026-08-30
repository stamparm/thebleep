# -*- encoding: utf-8 -*-

import json

from thebleep import project_context


def test_package_scripts_use_the_nearest_manifest(tmpdir):
    root = tmpdir.mkdir('project')
    nested = root.mkdir('packages').mkdir('web')
    root.join('package.json').write(json.dumps(
        {'scripts': {'root-task': 'true'}}))
    nested.join('package.json').write(json.dumps(
        {'scripts': {'build; rm -rf ~': 'true', 'test': 'true'}}))

    assert project_context.package_scripts(str(nested)) == [
        'build; rm -rf ~', 'test']


def test_package_scripts_find_a_parent_manifest(tmpdir):
    root = tmpdir.mkdir('project')
    nested = root.mkdir('src').mkdir('deep')
    root.join('package.json').write(json.dumps(
        {'scripts': {'build': 'true'}}))

    assert project_context.package_scripts(str(nested)) == ['build']


def test_missing_manifest_is_distinct_from_empty_scripts(tmpdir):
    empty = tmpdir.mkdir('empty')
    assert project_context.package_scripts(str(empty)) is None

    empty.join('package.json').write(json.dumps({'name': 'project'}))
    assert project_context.package_scripts(str(empty)) == []


def test_invalid_or_oversized_manifests_are_abstentions(tmpdir):
    project = tmpdir.mkdir('project')
    manifest = project.join('package.json')
    manifest.write('{"scripts":')
    assert project_context.package_scripts(str(project)) is None

    manifest.write('x' * (project_context.MAX_JSON_BYTES + 1))
    assert project_context.package_scripts(str(project)) is None


def test_manifest_keys_must_be_usable_command_names(tmpdir):
    project = tmpdir.mkdir('project')
    project.join('package.json').write(json.dumps({'scripts': {
        'ok': 'true', '\nnot-a-line': 'true', '\u0000bad': 'true'}}))

    assert project_context.package_scripts(str(project)) == ['ok']


def test_make_targets_are_static_and_deduplicated(tmpdir):
    root = tmpdir.mkdir('project')
    nested = root.mkdir('src')
    root.join('Makefile').write(
        '.PHONY: build test\n'
        'build test:\n\t@true\n'
        'generated-%:\n\t@true\n'
        '$(DYNAMIC):\n\t@true\n')

    assert project_context.make_targets(str(nested)) == ['build', 'test']


def test_make_targets_distinguish_missing_and_empty_files(tmpdir):
    empty = tmpdir.mkdir('empty')
    assert project_context.make_targets(str(empty)) is None

    empty.join('Makefile').write('# comments only\nVAR := value\n')
    assert project_context.make_targets(str(empty)) == []


def test_just_recipes_are_static_aliases_and_deduplicated(tmpdir):
    root = tmpdir.mkdir('project')
    nested = root.mkdir('src')
    root.join('Justfile').write(
        'set shell := ["bash", "-cu"]\n'
        'build target:\n\t@echo built\n'
        '[private] test:\n\t@echo tested\n'
        'alias b := build\n'
        'generated-{{name}}:\n\t@true\n')

    assert project_context.just_recipes(str(nested)) == [
        'build', 'test', 'b']


def test_just_recipes_distinguish_missing_and_empty_files(tmpdir):
    empty = tmpdir.mkdir('empty')
    assert project_context.just_recipes(str(empty)) is None

    empty.join('Justfile').write('# comments only\nset dotenv-load := true\n')
    assert project_context.just_recipes(str(empty)) == []


def test_cargo_bins_read_only_explicit_bin_blocks(tmpdir):
    project = tmpdir.mkdir('project')
    project.join('Cargo.toml').write(
        '[package]\nname = "ignored-package-name"\n\n'
        '[[bin]]\nname = "server"\npath = "src/server.rs"\n\n'
        '[[bin]]\nname = \'worker\'\n\n'
        '[workspace]\nname = "not-a-bin"\n')

    assert project_context.cargo_bins(str(project)) == ['server', 'worker']


def test_cargo_bins_distinguish_missing_and_empty_manifests(tmpdir):
    empty = tmpdir.mkdir('empty')
    assert project_context.cargo_bins(str(empty)) is None

    empty.join('Cargo.toml').write('[package]\nname = "project"\n')
    assert project_context.cargo_bins(str(empty)) == []
