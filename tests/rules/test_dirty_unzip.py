# -*- coding: utf-8 -*-

import os
import pytest
import zipfile
from thebleep.rules import dirty_unzip
from thebleep.rules.dirty_unzip import match, get_new_command
from thebleep.types import Command
from unicodedata import normalize


@pytest.fixture
def zip_error(tmpdir):
    def zip_error_inner(filename):
        path = os.path.join(str(tmpdir), filename)

        def reset(path):
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('a', '1')
                archive.writestr('b', '2')
                archive.writestr('c', '3')

                archive.writestr('d/e', '4')

                archive.extractall()

        os.chdir(str(tmpdir))
        reset(path)

        dir_list = os.listdir(u'.')
        if filename not in dir_list:
            filename = normalize('NFD', filename)

        assert set(dir_list) == {filename, 'a', 'b', 'c', 'd'}
        assert set(os.listdir('./d')) == {'e'}
    return zip_error_inner


@pytest.mark.parametrize('script,filename', [
    (u'unzip café', u'café.zip'),
    (u'unzip café.zip', u'café.zip'),
    (u'unzip foo', u'foo.zip'),
    (u'unzip foo.zip', u'foo.zip')])
def test_match(zip_error, script, filename):
    zip_error(filename)
    assert match(Command(script, ''))


def test_match_does_not_confuse_filename_with_destination_option(zip_error):
    zip_error(u'foo-d.zip')
    assert match(Command(u'unzip foo-d.zip', ''))


def test_nothing_is_deleted_behind_the_suggestion(zip_error):
    """Accepting `unzip -d` used to delete every file named in the archive.

    It could not tell an extracted file from one the user already had under the
    same name, and its containment test was a string prefix rather than a path
    containment check, so from `/tmp/foo` a member named `../foobar/precious`
    passed it. Both are unfixable from inside a rule: nothing in the archive
    says what was there before.

    """
    assert not hasattr(dirty_unzip, 'side_effect')

    zip_error(u'foo.zip')
    open('a', 'w').write('MY OWN a')
    get_new_command(Command(u'unzip foo.zip', ''))

    assert set(os.listdir(u'.')) == {u'foo.zip', 'a', 'b', 'c', 'd'}
    assert open('a').read() == 'MY OWN a'


@pytest.mark.parametrize('script,fixed,filename', [
    (u'unzip café', u"unzip café -d 'café'", u'café.zip'),
    (u'unzip foo', u'unzip foo -d foo', u'foo.zip'),
    (u"unzip 'foo bar.zip'", u"unzip 'foo bar.zip' -d 'foo bar'", u'foo.zip'),
    (u'unzip foo.zip', u'unzip foo.zip -d foo', u'foo.zip')])
def test_get_new_command(zip_error, script, fixed, filename):
    zip_error(filename)
    assert get_new_command(Command(script, '')) == fixed
