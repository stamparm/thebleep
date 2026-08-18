# -*- coding: utf-8 -*-

import io


def test_readme(source_root):
    # The README is UTF-8, and says so nowhere a text editor can be told, so
    # read it as UTF-8 rather than as whatever the machine's locale happens to
    # be. Windows reads cp1252 by default, which has no character for 0x8D --
    # the third byte of the block characters the benchmark chart is drawn with.
    with io.open(str(source_root.joinpath('README.md')),
                 encoding='utf-8') as handle:
        readme = handle.read()

    bundled = source_root.joinpath('thebleep').joinpath('rules').glob('*.py')

    for rule in bundled:
        if rule.stem != '__init__':
            assert rule.stem in readme, \
                'Missing rule "{}" in README.md'.format(rule.stem)
