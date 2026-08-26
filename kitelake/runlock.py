"""Single-writer guard: only one download process per lake, enforced by the OS.

Why this exists. ``BarWriter`` serialises concurrent merges with a ``threading.Lock``, which
covers the download's own worker threads — but a lock in module state is **in-process
only**. Two separate ``kitelake download`` processes share nothing, so they race exactly as
the threads used to: each reads a symbol's parquet, merges its own chunk, writes, and the
loser's chunks vanish. That race already cost 21 million candles once.

It is easy to trigger by accident. ``setsid nohup … &`` makes bash report the job as *Done*
the instant setsid forks, so a download that is running perfectly well looks finished — and
the natural response is to run it again. That happened twice.

``fcntl.flock`` is the right primitive: the kernel drops the lock when the holder exits for
*any* reason, including SIGKILL, so there is no stale-lockfile problem to clean up. The file
records the PID and start time purely so the error message can name what is already running.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["DownloadInProgress", "download_lock", "current_holder"]

LOCK_NAME = "download.lock"


class DownloadInProgress(RuntimeError):
    """Another download already holds this lake's write lock."""


def _lock_path(root: Any = None) -> Path:
    from .volume import manifest_dir

    return manifest_dir(root) / LOCK_NAME


def current_holder(root: Any = None) -> dict[str, Any] | None:
    """Describe the process holding the lock, or None. Never raises.

    Note this is advisory reporting only — the file contents can be stale even though the
    lock itself cannot be, because flock lives in the kernel, not in the file.
    """
    try:
        blob = json.loads(_lock_path(root).read_text())
    except Exception:
        return None
    pid = blob.get("pid")
    alive = False
    if isinstance(pid, int):
        try:
            os.kill(pid, 0)
            alive = True
        except OSError as exc:
            alive = exc.errno == errno.EPERM  # exists but owned by another user
    blob["alive"] = alive
    return blob


class download_lock:  # noqa: N801 - used as a context manager, reads better lowercase
    """Exclusive, per-lake download lock.

    Usage::

        with download_lock():
            ...  # only one process at a time gets here

    Raises:
        DownloadInProgress: if another process holds it, naming that process.
    """

    def __init__(self, root: Any = None, *, note: str = "") -> None:
        self._root = root
        self._note = note
        self._fd: int | None = None
        self.path = _lock_path(root)

    def __enter__(self) -> "download_lock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open without truncating: if we fail to take the lock, the holder's details must
        # survive so the error can name them.
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self._fd)
            self._fd = None
            holder = current_holder(self._root) or {}
            pid = holder.get("pid", "unknown")
            started = holder.get("started_at", "unknown time")
            raise DownloadInProgress(
                f"Another kitelake download is already running for this data folder "
                f"(pid {pid}, started {started}).\n"
                "Two downloads writing the same lake corrupt each other: they each merge a "
                "chunk into the same parquet and the loser's data is silently discarded.\n\n"
                "If you meant to check on the running one:\n"
                "    kitelake status --interval minute\n"
                "    tail -f ~/kitelake-download.log\n\n"
                "If you really want to stop it:\n"
                f"    kill -TERM {pid}\n\n"
                "Note: `setsid nohup … &` makes bash print 'Done' as soon as it forks, so a "
                "healthy download can look finished when it is not."
            ) from exc

        os.truncate(self._fd, 0)
        os.write(
            self._fd,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "note": self._note,
                },
                indent=2,
            ).encode(),
        )
        os.fsync(self._fd)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self._fd)
        finally:
            self._fd = None
        # Leave the file in place: an empty lock file is harmless, and removing it races
        # with another process that may already have opened it.
