"""Small, hermetic tests for the CI command discovery utility."""

import importlib.util
import io
import os
from pathlib import Path


def _inventory_module(source_root):
    path = source_root.joinpath('ci', 'command_inventory.py')
    spec = importlib.util.spec_from_file_location('command_inventory', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_keeps_first_path_entry(monkeypatch, tmpdir, source_root):
    module = _inventory_module(source_root)
    first = Path(str(tmpdir)).joinpath('first')
    second = Path(str(tmpdir)).joinpath('second')
    first.mkdir()
    second.mkdir()
    for directory in (first, second):
        executable = directory.joinpath('tool')
        executable.write_text('placeholder\n', encoding='utf-8')
    monkeypatch.setenv('PATH', os.pathsep.join((str(first), str(second))))
    monkeypatch.setattr(module, '_is_executable', lambda path: True)

    commands = module.inventory_commands()

    assert [item for item in commands if item['name'] == 'tool'] == [
        {'name': 'tool', 'path': str(first.joinpath('tool'))}]


def test_probe_reader_is_bounded(source_root):
    module = _inventory_module(source_root)
    module.MAX_PROBE_OUTPUT = 1024
    output = bytearray()
    finished = module.threading.Event()
    output_limited = module.threading.Event()
    process = type('Process', (), {
        'stdout': io.BytesIO(b'x' * 4096)})()

    module._probe_output(process, output, finished, output_limited)

    assert output_limited.is_set()
    assert finished.is_set()
    assert len(output) == 1024


def test_protected_path_entry_is_skipped(source_root):
    module = _inventory_module(source_root)

    class ProtectedPath:
        def is_file(self):
            raise PermissionError('protected')

    assert not module._is_executable(ProtectedPath())


def test_platform_specific_probe_is_skipped(monkeypatch, source_root):
    module = _inventory_module(source_root)
    monkeypatch.setattr(module.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(module, 'PROBES', {
        'ls': [{'arguments': ['--invalid'], 'platforms': ('posix',)}]})

    assert module.probe_commands([{'name': 'ls', 'path': 'ls'}]) == []
