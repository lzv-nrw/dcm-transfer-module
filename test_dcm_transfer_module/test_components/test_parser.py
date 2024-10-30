"""ProgressParser-component test-module."""

import os
from time import sleep
from uuid import uuid4
import io

import pytest
from dcm_common.models.report import Progress

from dcm_transfer_module.components.parser \
    import RegexParser, RsyncProgress, RsyncParser


def test_regex_parser_simple_match():
    """
    Test that the parser returns the expected dictionary when given a
    simple match.
    """
    pattern = r"Hello (?P<name>.*)"
    types = {}
    parser = RegexParser(pattern, types)
    assert parser.parse("Hello John") == {"name": "John"}


@pytest.mark.parametrize(
    "line",
    [
        "Hello",
        "Goodbye",
        "",
    ],
    ids=["Hello", "Goodbye", "empty"]
)
def test_regex_parser_no_match(line):
    """
    Test that the parser returns None when given a string that does not match.
    """
    pattern = r"Hello (?P<name>.*)"
    types = {}
    parser = RegexParser(pattern, types)
    assert parser.parse(line) is None


@pytest.mark.parametrize(
    "type_",
    [
        str,
        int,
    ],
    ids=["default", "custom"]
)
def test_regex_parser_group_with_exlicit_type(type_):
    """
    Test that the parser returns the expected dictionary when given a
    string where a group has been matched with a default type.
    """
    pattern = r"Hello (?P<name>.*)"
    types = {"name": type_}
    name = 1234567890
    parser = RegexParser(pattern, types)
    assert parser.parse(f"Hello {name}") == {"name": type_(f"{name}")}


def test_regex_parser_match_but_no_group():
    """
    Test that the parser returns None-values in dictionary when given
    a string where a match is made but without group.
    """
    pattern = r"Hello (?P<name>.+)*"
    types = {}
    parser = RegexParser(pattern, types)
    assert parser.parse("Hello ") == {"name": None}


def test_rsync_progress_unpacking():
    """Test unpacking of RsyncProgress-objects."""
    assert {**RsyncProgress()} == {
        "volume": "?", "percent": 0, "rate": "?", "time": "?", "xfr": 0,
        "chk": None
    }


@pytest.fixture(name="progress_status")
def _progress_status():
    """Basis for progress_string."""
    return RsyncProgress(
        volume="10.2M",
        percent=13,
        rate="10kB/s",
        time="0:02:50",
        xfr=4,
        chk="10/25"
    )


@pytest.fixture(name="progress_string_format")
def _progress_string_format():
    """Fixture for the string representation format of an rsync-progress."""
    return "{volume} {percent}% {rate} {time} (xfr#{xfr}, ir-chk={chk})"


def test_rsync_parser_parse(
    progress_status, progress_string_format
):
    """Test method parse of RsyncParser."""
    assert {**RsyncParser().parse(
        progress_string_format.format(**progress_status)
    )} == {**progress_status}


def test_rsync_parser_listen(
    file_storage, progress_status, progress_string_format
):
    """Test method listen of RsyncParser."""
    # setup fifo and Progress-object
    fifo_path = file_storage / str(uuid4())
    os.mkfifo(fifo_path)
    progress = Progress(verbose="start", numeric=0)

    # run parser continuously
    parser = RsyncParser()
    parser.listen(fifo_path, progress)
    assert parser.listening

    # open fifo and perform test
    with io.open(fifo_path, "w", encoding="utf-8") as fifo:
        assert progress.verbose == "start"
        assert progress.numeric == 0
        fifo.write(
            progress_string_format.format(**progress_status) + "\n"
        )
        fifo.flush()
        sleep(0.01)
        assert progress.numeric == progress_status.percent
        assert progress.verbose != "start"

    sleep(0.01)
    # closed fifo (should terminate Thread on other end)
    assert not parser.listening
