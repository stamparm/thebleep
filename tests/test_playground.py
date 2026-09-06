# -*- coding: utf-8 -*-

"""The browser playground, and the ways it could quietly stop being true.

The page at `docs/index.html` shows answers that were recorded when it was
built, so the failure mode worth guarding is not a crash -- it is a page that
goes on confidently showing what the engine used to say. That is what the
regeneration check is for, and it is the same bargain `bench/chart.py --check`
strikes with the README's numbers.

The rest are structural: a file the page fetches that nobody ships, a corpus
group nobody put on the page. Each is six lines that refuse the next instance,
which is cheaper than the sweep that misses one.

"""

import io
import json
import os
import re
import subprocess
import sys

import pytest


@pytest.fixture
def docs(source_root):
    return source_root.joinpath('docs')


@pytest.fixture
def page(docs):
    with io.open(str(docs.joinpath('index.html')), encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture
def cases(docs):
    with io.open(str(docs.joinpath('cases.json')), encoding='utf-8') as handle:
        return json.load(handle)


def test_the_recorded_answers_are_what_the_engine_says_today(source_root,
                                                             tmpdir):
    """`docs/cases.json` is regenerated and compared, not trusted.

    Run as a subprocess for two reasons. The generator installs a fixed PATH
    and a fixed history over `thebleep.utils` and never takes them off again,
    which in-process would leave every later test correcting against a machine
    that is not this one; and it calls `settings.init`, which *creates* a
    config directory -- so without an `XDG_*` of its own this test would write
    into whoever ran it.
    """
    home = tmpdir.mkdir('home')
    finished = subprocess.run(
        [sys.executable,
         os.path.join(str(source_root), 'assets', 'make_playground.py'),
         '--check'],
        env=dict(os.environ,
                 PYTHONPATH=str(source_root),
                 XDG_CONFIG_HOME=str(home),
                 XDG_CACHE_HOME=str(home)),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)

    assert finished.returncode == 0, \
        finished.stdout.decode('utf-8', 'replace')


def test_every_corpus_case_reaches_the_page(cases):
    """A new corpus group must not be invisible on the page.

    The generator names the three groups it publishes. Adding a fourth to
    `tests/corpus/cases.py` and not to that list would leave the page a case
    short and say nothing about it.
    """
    from tests.corpus import cases as corpus

    published = sum(len(group['cases']) for group in cases['groups'])
    assert published == len(corpus.ALL)


def test_the_page_only_fetches_files_that_are_published(page, docs):
    """Everything the page asks for is either shipped or built by the workflow.

    `wheel.json` and the wheel itself are written at deploy time by
    `.github/workflows/pages.yml`; the rest have to be in the repository.
    """
    built_at_deploy = {'wheel.json'}
    fetched = set(re.findall(r"fetch\('([^']+)'\)", page))

    assert fetched, 'the page fetches nothing, which cannot be right'
    for name in fetched - built_at_deploy:
        assert docs.joinpath(name).exists(), name


def test_the_workflow_builds_what_the_page_asks_for(source_root, page):
    """The page reads a filename out of `wheel.json`; something must write it.

    These two live in different files and would drift apart silently: the page
    would ask for a name nothing had written, and the only symptom would be a
    demo that never leaves "starting the engine".
    """
    workflow = source_root.joinpath('.github', 'workflows', 'pages.yml')
    with io.open(str(workflow), encoding='utf-8') as handle:
        written = handle.read()

    assert "fetch('wheel.json')" in page
    assert 'docs/wheel.json' in written
    assert 'wheel-dir docs' in written


@pytest.fixture
def playground(source_root):
    """The page's own module.

    Importing it is safe -- it is constants until something calls a function.
    `install` and `install_filesystem` are emphatically not safe to call here:
    the first patches `thebleep.utils` for the rest of the process, the second
    writes `/etc/passwd`.
    """
    import importlib.util

    path = source_root.joinpath('docs', 'bootstrap.py')
    spec = importlib.util.spec_from_file_location('playground_bootstrap',
                                                  str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_demo_tree_can_actually_be_laid_out(playground):
    """Every file's directory is one the layout creates first.

    `install_filesystem` makes the directories and then opens the files, so a
    file under a directory nobody listed raises halfway through and the page
    comes up with no engine at all.
    """
    made = set(playground.DIRECTORIES)

    for path in playground.FILES:
        parent = path.rsplit('/', 1)[0]
        assert parent in made, path


def test_every_worked_example_talks_about_its_own_path(playground):
    """The path in the command is the path the program complained about.

    These pair a command with a message captured from a real program, and the
    two are edited by hand. A pair that drifted would demonstrate nothing and
    look exactly like a rule that had stopped working.
    """
    for script, output in playground.SCENARIOS:
        argument = script.split()[-1]
        assert argument in output, (script, output)


def test_the_page_lays_the_tree_out_and_the_generator_does_not(page,
                                                               source_root):
    """Only the browser may have a filesystem laid out under it.

    The generator runs on a real machine, where `/etc/passwd` is not ours to
    write. The separation is the whole reason these are two functions, and
    nothing but a test keeps them apart.
    """
    with io.open(str(source_root.joinpath('assets', 'make_playground.py')),
                 encoding='utf-8') as handle:
        generator = handle.read()

    assert 'install_filesystem()' in page
    assert 'install_filesystem' not in generator


def test_the_output_box_does_not_stand_there_naming_one_command(page):
    """It used to hold `sh: 1: gti: not found` whatever you had typed.

    A placeholder that names a command reads as content rather than as a
    prompt, so the box looked stuck on somebody else's mistake -- and it is
    the field a visitor is least sure what to do with in the first place. The
    shell message is filled in from the command now, so no fixed one belongs
    in the markup.
    """
    placeholders = re.findall(r'placeholder="([^"]*)"', page)

    assert placeholders, 'the inputs lost their placeholders'
    for text in placeholders:
        assert 'not found' not in text, text


def test_nothing_on_the_page_offers_to_run_anything(page):
    """The claim the page makes about itself, kept true by a test.

    It says nothing here can execute. A future edit that wires a suggestion up
    to something -- a copy-to-clipboard that shells out, an `eval` of a
    correction -- would make that sentence a lie, and the sentence is the whole
    argument for the tool.
    """
    for forbidden in ('eval(', 'new Function', 'child_process'):
        assert forbidden not in page, forbidden
