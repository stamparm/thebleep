import pytest


@pytest.fixture
def builtins_open(mocker):
    return mocker.patch('builtins.open')


@pytest.fixture
def isfile(mocker):
    return mocker.patch('os.path.isfile', return_value=True)


@pytest.fixture
def history_lines(mocker):
    def aux(lines):
        mock = mocker.patch('io.open')
        mock.return_value.__enter__ \
            .return_value.readlines.return_value = lines

    return aux


@pytest.fixture
def config_exists(mocker):
    # `generic` asks `expanduser(path).exists()`; it used to build a `Path` and
    # expand it, and this mocked the whole chain.
    return mocker.patch('thebleep.shells.generic.expanduser').return_value.exists
