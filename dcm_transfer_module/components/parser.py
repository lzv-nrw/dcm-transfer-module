"""
This module defines the `ProgressParser` component of the Transfer
Module-app.
"""

from typing import Optional, Any, Callable
import re
from pathlib import Path
from dataclasses import dataclass, field
import io
from threading import Thread, Event

from dcm_common.models.report import Progress


class RegexParser:
    """
    A `RegexParser` can be used to parse strings into dictionaries with
    typed values.

    Keyword arguments:
    pattern -- the pattern to match (only named groups are included in
               the output)
    types -- a dictionary of types to use for each match group;
             omitting a group will use the default type `str`
             (default `None`)
    """

    def __init__(
        self, pattern: str, types: Optional[dict[str, type]] = None
    ) -> None:
        self._pattern = re.compile(pattern)
        self._types = types or {}

    def _convert_match_types(
        self, groupdict: dict[str, str]
    ) -> dict[str, Any]:
        """
        Returns a dictionary of values converted to the appropriate
        type.
        """
        return {
            k: self._types.get(k, str)(v) if v is not None else v
            for k, v in groupdict.items()
        }

    def parse(self, line: str) -> Optional[dict]:
        """
        Parses a line into a dictionary of (typed) values based on the
        given pattern and type-map.
        Returns `None` if the line does not match the pattern.

        Keyword arguments:
        line -- the string to parse
        """
        match = self._pattern.match(line)
        if match is None:
            return None
        return self._convert_match_types(match.groupdict())


@dataclass
class RsyncProgress:
    """
    Record class for storing parsed result.

    Keyword arguments:
    volume -- data volume progress
              (default "?")
    percent -- progress in percent
              (default 0)
    rate -- current transfer rate
              (default "?")
    time -- time since transfer start
              (default "?")
    xfr -- current file id
              (default 0)
    chk -- ratio of files that require validation to (currently)
           recursively scanned files
           (default `None`)
    """
    volume: str = field(default_factory=lambda: "?")
    percent: int = 0
    rate: str = field(default_factory=lambda: "?")
    time: str = field(default_factory=lambda: "?")
    xfr: int = 0
    chk: Optional[str] = None

    def keys(self):
        return self.__dict__.keys()

    def __getitem__(self, key):
        return getattr(self, key)


class RsyncParser:
    """
    `RsyncParser` is a class for parsing the output
    `--info=progress2`-style of `rsync`.
    """
    _PATTERN = (
        r"\s*(?P<volume>[0-9\.,]+[a-zA-Z]*)"
        + r"\s+(?P<percent>\d+)%"
        + r"\s+(?P<rate>[0-9\.,]+[\/a-zA-Z]+)"
        + r"\s+(?P<time>[\d+:?]+)"
        + r"(\s+\(xfr#(?P<xfr>\d+),\s+(ir-chk|to-chk)=(?P<chk>\d+\/\d+)\))?"
    )
    _TYPES = {
        "percent": int,
        "xfr": int
    }
    _FORMAT = "syncing files, {percent}% @ {rate}"

    def __init__(self) -> None:
        self._regex_parser = RegexParser(self._PATTERN, self._TYPES)
        self._listening = Event()

    @property
    def listening(self) -> bool:
        """
        Returns whether the parser is listening.
        """
        return self._listening.is_set()

    def parse(self, progress: str) -> RsyncProgress:
        """
        Parse the given `progress` and return an `RsyncProgress`.

        Keyword arguments:
        progress -- the output of `rsync --info=progress2 ...`
        """
        return RsyncProgress(**self._regex_parser.parse(progress))

    def _listen_thread(
        self, pipe: Path, progress: Progress, push: Callable
    ) -> None:
        self._listening.set()
        with io.open(pipe, "r", encoding="utf-8") as _pipe:
            for line in _pipe:
                if line != "\n":
                    parsed = self.parse(line)
                    progress.numeric = parsed.percent
                    progress.verbose = self._FORMAT.format(**parsed)
                    push()
        self._listening.clear()

    def listen(
        self, pipe: Path, progress: Progress, push: Optional[Callable] = None
    ) -> None:
        """
        Continuously parse the given `pipe` in a separate `Thread` and
        update `progress` accordingly.

        Keyword arguments:
        pipe -- the path to the named pipe/fifo
        progress -- the `Progress` object to be updated
        push -- function to push the updated `progress` to the host
                process
                (default None)
        """
        if self.listening:
            raise RuntimeError(f"Already listening at '{pipe}'.")
        t = Thread(
            target=self._listen_thread,
            args=(pipe, progress, push or (lambda: None))
        )
        t.start()
        self._listening.wait()
