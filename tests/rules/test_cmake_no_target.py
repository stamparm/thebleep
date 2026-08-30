# -*- coding: utf-8 -*-

from thebleep.rules.cmake_no_target import get_new_command, match
from thebleep.types import Command


# Captured from CMake 3.28.3 with GNU Make and a target named `build`.
OUTPUT = "gmake: *** No rule to make target 'buil'.  Stop."


def test_match_requires_cmake_build_target_mode():
    assert match(Command('cmake --build build --target buil', OUTPUT))
    assert not match(Command('make buil', OUTPUT))
    assert not match(Command('cmake --build build', OUTPUT))


def test_declared_cmake_target_is_suggested(tmpdir, monkeypatch):
    tmpdir.join('CMakeLists.txt').write(
        'cmake_minimum_required(VERSION 3.15)\n'
        'add_custom_target(build)\n'
        'add_custom_target(test)\n')
    monkeypatch.chdir(tmpdir)

    assert get_new_command(
        Command('cmake --build build --target buil', OUTPUT)) == [
            'cmake --build build --target build']


def test_compound_command_replaces_the_cmake_target_not_prior_output_arg(
        tmpdir, monkeypatch):
    tmpdir.join('CMakeLists.txt').write('add_custom_target(build)\n')
    monkeypatch.chdir(tmpdir)

    assert get_new_command(Command(
        'echo buil && cmake --build build --target buil', OUTPUT)) == [
            'echo buil && cmake --build build --target build']


def test_static_target_declarations_are_read_without_running_cmake(
        tmpdir, monkeypatch):
    tmpdir.join('CMakeLists.txt').write(
        '# add_custom_target(commented)\n'
        'add_custom_target("build docs")\n'
        'add_executable(app main.c)\n'
        'add_library(${GENERATED} generated.c)\n')
    monkeypatch.chdir(tmpdir)

    from thebleep import project_context
    assert project_context.cmake_targets() == ['build docs', 'app']


def test_unreadable_project_metadata_abstains(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    assert get_new_command(Command(
        'cmake --build build --target buil', OUTPUT)) == []
