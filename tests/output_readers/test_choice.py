# -*- encoding: utf-8 -*-

"""Which reader answers, and what happens when the chosen one cannot.

The README's claim about instant mode is that where it does not work it does not
go wrong -- the mark is missing, or the command has scrolled out of the
recording, and the correction carries on by the ordinary route. It did not: the
recorded reader's answer was returned whatever it was, so `None` meant no
correction at all rather than a question.

The other half of these is that the fallback did not hand anything consent it
would not otherwise have had. Falling back reaches `replay.is_allowed`, which is
the same gate a correction outside instant mode goes through.

"""

import pytest
from thebleep import output_readers


@pytest.fixture
def recorded(mocker):
    from thebleep.output_readers import read_log

    return mocker.patch.object(read_log, 'get_output')


@pytest.fixture
def allowed(mocker):
    from thebleep import replay

    return mocker.patch.object(replay, 'is_allowed')


@pytest.fixture
def rerun(mocker):
    from thebleep.output_readers import rerun

    mocker.patch.object(rerun, 'get_output', return_value=u'from a second run')
    return rerun.get_output


@pytest.fixture(autouse=True)
def instant_mode(settings):
    settings.instant_mode = True


def test_the_recording_answers_and_nothing_runs_again(recorded, allowed,
                                                      rerun):
    recorded.return_value = u'ehco: command not found'
    assert output_readers.get_output(u'ehco x', u'ehco x') == \
        u'ehco: command not found'
    assert not allowed.called
    assert not rerun.called


def test_a_command_that_printed_nothing_is_still_an_answer(recorded, allowed,
                                                           rerun):
    """`''` is what the recording says about `true`, and it is not a failure."""
    recorded.return_value = u''
    assert output_readers.get_output(u'true', u'true') == u''
    assert not allowed.called


def test_no_answer_falls_through_to_the_ordinary_route(recorded, allowed,
                                                       rerun):
    recorded.return_value = None
    allowed.return_value = True
    assert output_readers.get_output(u'ehco x', u'ehco x') == \
        u'from a second run'
    assert allowed.called


def test_no_answer_and_no_consent_runs_nothing(recorded, allowed, rerun):
    """The fallback is to *ask*, so a no is a no and the correction goes on
    from the command alone."""
    recorded.return_value = None
    allowed.return_value = False
    assert output_readers.get_output(u'deploy prod', u'deploy prod') is None
    assert allowed.called
    assert not rerun.called


def test_the_shell_logger_still_wins_over_both(recorded, allowed, rerun,
                                               mocker):
    mocker.patch.object(output_readers, '_shell_logger_available',
                        return_value=True)
    from thebleep.output_readers import shell_logger

    mocker.patch.object(shell_logger, 'get_output', return_value=u'logged')
    assert output_readers.get_output(u'ehco x', u'ehco x') == u'logged'
    assert not recorded.called
