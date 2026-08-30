import os
import pytest
import tarfile
from thebleep.rules import dirty_untar
from thebleep.rules.dirty_untar import match, get_new_command, \
                                      tar_extensions  # noqa: E126
from thebleep.types import Command


@pytest.fixture
def tar_error(tmpdir):
    def fixture(filename):
        path = os.path.join(str(tmpdir), filename)

        def reset(path):
            os.mkdir('d')
            with tarfile.TarFile(path, 'w') as archive:
                for file in ('a', 'b', 'c', 'd/e'):
                    with open(file, 'w') as f:
                        f.write('*')

                    archive.add(file)

                    os.remove(file)

            with tarfile.TarFile(path, 'r') as archive:
                archive.extractall()

        os.chdir(str(tmpdir))
        reset(path)

        assert set(os.listdir('.')) == {filename, 'a', 'b', 'c', 'd'}
        assert set(os.listdir('./d')) == {'e'}

    return fixture


parametrize_extensions = pytest.mark.parametrize('ext', tar_extensions)

# (filename as typed by the user, unquoted filename, quoted filename as per shells.quote)
parametrize_filename = pytest.mark.parametrize('filename, unquoted, quoted', [
    ('foo{}', 'foo{}', 'foo{}'),
    ('"foo bar{}"', 'foo bar{}', "'foo bar{}'")])

parametrize_script = pytest.mark.parametrize('script, fixed', [
    ('tar xvf {}', 'mkdir -p {dir} && tar xvf {filename} -C {dir}'),
    ('tar -xvf {}', 'mkdir -p {dir} && tar -xvf {filename} -C {dir}'),
    ('tar --extract -f {}', 'mkdir -p {dir} && tar --extract -f {filename} -C {dir}')])


@parametrize_extensions
@parametrize_filename
@parametrize_script
def test_match(ext, tar_error, filename, unquoted, quoted, script, fixed):
    tar_error(unquoted.format(ext))
    assert match(Command(script.format(filename.format(ext)), ''))


def test_match_does_not_confuse_filename_with_change_directory_option(tar_error):
    tar_error('foo-C.tar')
    assert match(Command('tar xvf foo-C.tar', ''))


def test_nothing_is_deleted_behind_the_suggestion(tar_error):
    """See `test_dirty_unzip` for why the rollback could not be made safe."""
    assert not hasattr(dirty_untar, 'side_effect')

    tar_error('foo.tar')
    with open('a', 'w') as handle:
        handle.write('MY OWN a')
    get_new_command(Command('tar xvf foo.tar', ''))

    assert set(os.listdir('.')) == {'foo.tar', 'a', 'b', 'c', 'd'}
    with open('a') as handle:
        assert handle.read() == 'MY OWN a'


@parametrize_extensions
@parametrize_filename
@parametrize_script
def test_get_new_command(ext, tar_error, filename, unquoted, quoted, script, fixed):
    tar_error(unquoted.format(ext))
    assert (get_new_command(Command(script.format(filename.format(ext)), ''))
            == fixed.format(dir=quoted.format(''), filename=filename.format(ext)))
