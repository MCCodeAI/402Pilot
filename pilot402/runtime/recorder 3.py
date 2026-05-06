"""JsonlRecorder — concrete ``Recorder`` writing one ``LogRecord`` per JSONL line.

One file per (run_id, scenario, seed). The file is opened in append mode so
a crashed run can be resumed by reading existing lines (round numbers strictly
ascending) and continuing where the count left off — though the loop
orchestrator is responsible for that resume logic; the recorder is dumb on
purpose.

Each ``write`` flushes after the newline. We'd like to batch flushes for
throughput on a 10,000-round run, but the round budget is on the order of
seconds total; the bottleneck is always the policy update, not the disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from pilot402.core.types import LogRecord


@dataclass
class JsonlRecorder:
    """Append-mode JSONL writer.

    Args:
        path: target file. Parent directory is created if missing. The file
              is opened on first ``write`` call (lazy) so constructing a
              recorder for a dry run does not touch disk.
    """

    path: Path
    _fh: IO[str] | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def write(self, record: LogRecord) -> None:
        if self._closed:
            raise RuntimeError(f"JsonlRecorder({self.path}) is already closed.")
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("a", encoding="utf-8")
        self._fh.write(record.model_dump_json() + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._closed:
            return
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self._closed = True

    def __enter__(self) -> "JsonlRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()


__all__ = ["JsonlRecorder"]
