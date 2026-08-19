# -*- coding: utf-8 -*-

"""The README as PyPI will render it.

The README is the package's long description, and its links are relative so that
they work on GitHub from any branch, fork or private checkout. PyPI has no
repository to resolve them against, so `setup.py` makes them absolute and pins
them to the release tag.

It knew about one of Markdown's two ways to write a link. `[text](target)` was
rewritten; a reference definition at the foot of the file, `[name]: target`, was
not -- so the first badge on the PyPI page, whose `[version-link]` resolves to
`CHANGELOG.md`, was a dead relative link.

"""

import io
import re
import pytest


@pytest.fixture
def setup_namespace(source_root, monkeypatch):
    """`setup.py`, run without letting it call `setup()`."""
    import setuptools

    called = {}
    monkeypatch.setattr(setuptools, 'setup', lambda **kwargs: called.update(
        kwargs))
    path = str(source_root.joinpath('setup.py'))
    with io.open(path, encoding='utf-8') as handle:
        source = handle.read()
    namespace = {'__file__': path, '__name__': 'setup'}
    exec(compile(source, path, 'exec'), namespace)
    namespace['_called'] = called
    return namespace


@pytest.fixture
def for_pypi(setup_namespace):
    return setup_namespace['for_pypi']


@pytest.fixture
def version(setup_namespace):
    return setup_namespace['VERSION']


@pytest.fixture
def long_description(setup_namespace):
    """What is actually handed to `setup()` as the long description."""
    return setup_namespace['_called']['long_description']


class TestTheTransformation(object):
    def test_an_inline_link_to_a_file(self, for_pypi, version):
        assert for_pypi('see [the licence](LICENSE.md) for it') == \
            'see [the licence](https://github.com/stamparm/thebleep/blob/' \
            '{}/LICENSE.md) for it'.format(version)

    def test_an_inline_link_to_a_directory(self, for_pypi, version):
        assert '/blob/{}/bench/'.format(version) in for_pypi('[b](bench/)')

    def test_an_image_goes_to_raw(self, for_pypi, version):
        """A blob URL renders as a page, not as an image."""
        assert for_pypi('![demo](assets/demo.svg)') == \
            '![demo](https://raw.githubusercontent.com/stamparm/thebleep/' \
            '{}/assets/demo.svg)'.format(version)

    def test_a_reference_definition(self, for_pypi, version):
        assert for_pypi('[version-link]:    CHANGELOG.md') == \
            '[version-link]:    https://github.com/stamparm/thebleep/blob/' \
            '{}/CHANGELOG.md'.format(version)

    def test_an_absolute_reference_definition_is_left_alone(self, for_pypi):
        line = '[license-badge]:   https://img.shields.io/badge/x.svg'
        assert for_pypi(line) == line

    def test_an_external_link_is_left_alone(self, for_pypi):
        text = '[PEP 668](https://peps.python.org/pep-0668/)'
        assert for_pypi(text) == text

    def test_an_anchor_stays_an_anchor(self, for_pypi):
        """PyPI renders the headings, so an anchor still goes somewhere."""
        text = '[Settings](#settings)'
        assert for_pypi(text) == text

    def test_a_mailto_is_left_alone(self, for_pypi):
        text = '[me](mailto:someone@example.com)'
        assert for_pypi(text) == text

    def test_a_definition_that_is_not_at_the_start_of_a_line(self, for_pypi):
        """`a[b]: c` inside a sentence is not a reference definition."""
        text = 'the value of a[b]: not-a-link'
        assert for_pypi(text) == text


class TestTheRenderedPage(object):
    """The long description as built, rather than the transformation alone."""

    def test_nothing_relative_is_left_in_it(self, long_description):
        targets = re.findall(r'\]\(([^)]+)\)', long_description)
        targets += [target for _, target in re.findall(
            r'(?m)^(\[[^\]]+\]:\s+)(\S+)$', long_description)]
        assert targets, 'no links were found to check'
        relative = [target for target in targets
                    if not target.startswith(('http:', 'https:', 'mailto:',
                                              '#'))]
        assert relative == [], relative

    def test_every_absolute_link_is_pinned_to_this_release(
            self, long_description, version):
        """Not to `master`, so that the 4.0.0 page keeps showing 4.0.0."""
        # Only the links this transformation makes. Two written by hand are
        # deliberately not pinned and are not the transformation's business: the
        # workflow badge, which has to point at the live workflow, and the
        # `curl | sh` one-liner, which has to fetch the current installer.
        text = long_description.replace(
            'raw.githubusercontent.com/stamparm/thebleep/master/install.sh', '')
        ours = re.findall(
            r'https://raw\.githubusercontent\.com/stamparm/thebleep/([^/)\s]+)/'
            r'|https://github\.com/stamparm/thebleep/blob/([^/)\s]+)/', text)
        found = {ref for pair in ours for ref in pair if ref}
        assert found, 'no repository links were found to check'
        assert found == {version}, sorted(found)

    def test_the_badges_still_work(self, long_description, version):
        """The version badge is the first thing on the page."""
        assert '[version-link]:    https://github.com/stamparm/thebleep/' \
            'blob/{}/CHANGELOG.md'.format(version) in long_description

    def test_the_demo_image_comes_from_raw(self, long_description):
        assert 'raw.githubusercontent.com' in long_description
        assert '](https://github.com/stamparm/thebleep/blob/' not in \
            long_description.split('assets/demo.svg')[0][-120:]
