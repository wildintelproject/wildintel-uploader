"""What ExifTool read of each image, kept on disk, so that a restart of the app in the middle of an import does not read the images again (#140).

Each image is kept under its stamp — its path, its size and its modification time in nanoseconds (see file_memo) —: a file that was changed, or replaced by
another, has another stamp and is read again, so what is found here is never what an earlier file said. It is a SQLite database in the cache folder of the
system (~/.cache/wildintel-uploader on Linux): a cache, that can be removed at any time, and that holds at most LIMIT images, the oldest written forgotten first.

Nothing depends on it: when it cannot be opened, read or written, it is as if it were empty, and the images are read with ExifTool."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

import platformdirs

from wildintel_uploader.core.services.file_memo import Stamp

logger = logging.getLogger(__name__)

APP_NAME = "wildintel-uploader"
FILE_NAME = "exif.sqlite3"
LIMIT = 300_000
# How many paths go in one query: below SQLite's limit of variables.
_CHUNK = 500

_lock = threading.Lock()
_connection: sqlite3.Connection | None = None
_opened_at: Path | None = None


def path() -> Path:
    """Where the database is."""
    return Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False)) / FILE_NAME


def _open() -> sqlite3.Connection:
    """The connection, opened the first time — again if the cache folder changed (the tests move it)."""
    global _connection, _opened_at
    where = path()
    if _connection is None or _opened_at != where:
        if _connection is not None:
            _connection.close()
        where.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(where, check_same_thread=False, timeout=5)
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("CREATE TABLE IF NOT EXISTS exif (path TEXT NOT NULL, size INTEGER NOT NULL, mtime INTEGER NOT NULL, tags TEXT NOT NULL, "
                            "written REAL NOT NULL, PRIMARY KEY (path, size, mtime))")
        _connection.execute("CREATE INDEX IF NOT EXISTS exif_written ON exif (written)")
        _opened_at = where
    return _connection


def get_many(stamps: list[Stamp]) -> dict[Stamp, dict[str, str | None]]:
    """What was kept of the files of these stamps: only those that are kept, and only while the file is the same."""
    if not stamps:
        return {}
    wanted = set(stamps)
    found: dict[Stamp, dict[str, str | None]] = {}
    try:
        with _lock:
            db = _open()
            paths = sorted({s[0] for s in wanted})
            for start in range(0, len(paths), _CHUNK):
                chunk = paths[start:start + _CHUNK]
                rows = db.execute(f"SELECT path, size, mtime, tags FROM exif WHERE path IN ({','.join('?' * len(chunk))})", chunk).fetchall()
                for where, size, mtime, tags in rows:
                    if (where, size, mtime) in wanted:
                        found[(where, size, mtime)] = json.loads(tags)
    except (sqlite3.Error, OSError, ValueError) as exc:
        logger.debug("The EXIF kept on disk could not be read (%s): the images are read again.", exc)
        return {}
    return found


def put_many(values: dict[Stamp, dict[str, str | None]]) -> None:
    """Keeps what was read of these files, in place of what an earlier version of each one said; and forgets the oldest beyond LIMIT."""
    if not values:
        return
    now = time.time()
    try:
        with _lock:
            db = _open()
            with db:
                # an earlier version of the same file is of no use any more
                db.executemany("DELETE FROM exif WHERE path = ?", [(s[0],) for s in values])
                db.executemany("INSERT OR REPLACE INTO exif (path, size, mtime, tags, written) VALUES (?, ?, ?, ?, ?)",
                               [(s[0], s[1], s[2], json.dumps(tags, ensure_ascii=False), now) for s, tags in values.items()])
                over = db.execute("SELECT COUNT(*) FROM exif").fetchone()[0] - LIMIT
                if over > 0:
                    db.execute("DELETE FROM exif WHERE rowid IN (SELECT rowid FROM exif ORDER BY written LIMIT ?)", (over,))
    except (sqlite3.Error, OSError) as exc:
        logger.debug("The EXIF read could not be kept on disk (%s).", exc)


def clear() -> None:
    """Forgets everything that was kept."""
    try:
        with _lock:
            db = _open()
            with db:
                db.execute("DELETE FROM exif")
    except (sqlite3.Error, OSError) as exc:
        logger.debug("The EXIF kept on disk could not be cleared (%s).", exc)
