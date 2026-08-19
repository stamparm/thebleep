# -*- coding: utf-8 -*-

"""Which of the Arch rules are on, on a machine that is not Arch.

`archlinux_env()` answers with a pair -- whether to be on by default, and the
helper to shell out to -- and a two-element tuple is truthy whatever is in it. A
rule that assigned the whole pair to `enabled_by_default` was therefore enabled
on every machine there is, Debian and Windows included, with only its own
`@for_app('pacman')` left between it and a command it knows nothing about.

So the three rules that ask are checked here together, in both environments,
rather than each being trusted to unpack correctly.

"""

import importlib
import pytest
from thebleep import utils
from thebleep.rules import pacman, pacman_invalid_option, pacman_not_found

ASKS = (pacman, pacman_invalid_option, pacman_not_found)


@pytest.fixture
def enabled_where(monkeypatch):
    """Reloads the Arch rules against a given `PATH`, and puts them back after.

    Reloaded because `enabled_by_default` is worked out once, while the rule is
    being imported -- which is the whole point of it, and the reason a mistake
    there is invisible until somebody looks.

    """
    def reload_with(installed):
        monkeypatch.setattr(
            utils, 'which',
            lambda program: '/usr/bin/' + program
            if program in installed else None)
        return {module.__name__.rsplit('.', 1)[1]:
                importlib.reload(module).enabled_by_default
                for module in ASKS}

    yield reload_with

    monkeypatch.undo()
    for module in ASKS:
        importlib.reload(module)


def test_off_where_there_is_no_pacman(enabled_where):
    for name, enabled in enabled_where(set()).items():
        assert not enabled, name


def test_off_on_arch_without_pkgfile(enabled_where):
    """`pkgfile` is what the two lookup rules need; without it they stay off."""
    for name, enabled in enabled_where({'pacman'}).items():
        assert not enabled, name


def test_on_on_arch_with_pkgfile(enabled_where):
    for name, enabled in enabled_where({'pacman', 'pkgfile'}).items():
        assert enabled, name


def test_on_with_an_aur_helper_instead(enabled_where):
    for name, enabled in enabled_where({'paru', 'pkgfile'}).items():
        assert enabled, name
