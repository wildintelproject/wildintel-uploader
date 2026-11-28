"""Store in a SQLite database in the cache folder of the system (~/.cache/wildintel-uploader on Linux): what ExifTool read of each image (#140), and
what else is known of it — whether it decodes, its hashes —, so that a restart of the app does not find them out again.

Each file is kept under its stamp: one that was changed, or replaced by another, has another stamp and is looked at again. It is a cache, that can
be removed at any time, and that holds at most LIMIT files of each, the oldest written forgotten first. Nothing depends on it: when it cannot be
opened, read or written, it is as if it were empty."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

import platformdirs

from wildintel_uploader.modules.fileinfo.domain.models import Stamp, Tags
from wildintel_uploader.modules.fileinfo.domain.ports import Store

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
        # a cache kept by a version whose stamps had no ctime cannot tell a file replaced: it is let go, and filled again as the images are read
        for table in ("exif", "facts"):
            columns = {row[1] for row in _connection.execute(f"PRAGMA table_info({table})")}
            if columns and "ctime" not in columns:
                _connection.execute(f"DROP TABLE {table}")
        _connection.execute("CREATE TABLE IF NOT EXISTS exif (path TEXT NOT NULL, size INTEGER NOT NULL, mtime INTEGER NOT NULL, ctime INTEGER NOT NULL, "
                            "tags TEXT NOT NULL, written REAL NOT NULL, PRIMARY KEY (path, size, mtime, ctime))")
        _connection.execute("CREATE INDEX IF NOT EXISTS exif_written ON exif (written)")
        _connection.execute("CREATE TABLE IF NOT EXISTS facts (path TEXT NOT NULL, size INTEGER NOT NULL, mtime INTEGER NOT NULL, ctime INTEGER NOT NULL, "
                            "kind TEXT NOT NULL, value TEXT NOT NULL, written REAL NOT NULL, PRIMARY KEY (path, kind, size, mtime, ctime))")
        _connection.execute("CREATE INDEX IF NOT EXISTS facts_written ON facts (kind, written)")
        _opened_at = where
    return _connection


def _rows(query: str, paths: list[str], *extra: object) -> list[tuple]:
    db, rows = _open(), []
    for start in range(0, len(paths), _CHUNK):
        chunk = paths[start:start + _CHUNK]
        rows += db.execute(query.format(marks=",".join("?" * len(chunk))), [*extra, *chunk]).fetchall()
    return rows


def get_many(stamps: list[Stamp]) -> dict[Stamp, Tags]:
    """What was kept of the files of these stamps: only those that are kept, and only while the file is the same."""
    if not stamps:
        return {}
    wanted = set(stamps)
    try:
        with _lock:
            rows = _rows("SELECT path, size, mtime, ctime, tags FROM exif WHERE path IN ({marks})", sorted({s[0] for s in wanted}))
        return {(p, s, m, c): json.loads(tags) for p, s, m, c, tags in rows if (p, s, m, c) in wanted}
    except (sqlite3.Error, OSError, ValueError) as exc:
        logger.debug("The EXIF kept on disk could not be read (%s): the images are read again.", exc)
        return {}


def put_many(values: dict[Stamp, Tags]) -> None:
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
                db.executemany("INSERT OR REPLACE INTO exif (path, size, mtime, ctime, tags, written) VALUES (?, ?, ?, ?, ?, ?)",
                               [(s[0], s[1], s[2], s[3], json.dumps(tags, ensure_ascii=False), now) for s, tags in values.items()])
                over = db.execute("SELECT COUNT(*) FROM exif").fetchone()[0] - LIMIT
                if over > 0:
                    db.execute("DELETE FROM exif WHERE rowid IN (SELECT rowid FROM exif ORDER BY written LIMIT ?)", (over,))
    except (sqlite3.Error, OSError) as exc:
        logger.debug("The EXIF read could not be kept on disk (%s).", exc)


def get_facts(stamps: list[Stamp], kind: str) -> dict[Stamp, str]:
    if not stamps:
        return {}
    wanted = set(stamps)
    try:
        with _lock:
            rows = _rows("SELECT path, size, mtime, ctime, value FROM facts WHERE kind = ? AND path IN ({marks})", sorted({s[0] for s in wanted}), kind)
        return {(p, s, m, c): value for p, s, m, c, value in rows if (p, s, m, c) in wanted}
    except (sqlite3.Error, OSError) as exc:
        logger.debug("What is known of the files could not be read from disk (%s).", exc)
        return {}


def put_facts(values: dict[Stamp, str], kind: str) -> None:
    if not values:
        return
    now = time.time()
    try:
        with _lock:
            db = _open()
            with db:
                db.executemany("DELETE FROM facts WHERE path = ? AND kind = ?", [(s[0], kind) for s in values])
                db.executemany("INSERT OR REPLACE INTO facts (path, size, mtime, ctime, kind, value, written) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               [(s[0], s[1], s[2], s[3], kind, value, now) for s, value in values.items()])
                over = db.execute("SELECT COUNT(*) FROM facts WHERE kind = ?", (kind,)).fetchone()[0] - LIMIT
                if over > 0:
                    db.execute("DELETE FROM facts WHERE rowid IN (SELECT rowid FROM facts WHERE kind = ? ORDER BY written LIMIT ?)", (kind, over))
    except (sqlite3.Error, OSError) as exc:
        logger.debug("What is known of the files could not be kept on disk (%s).", exc)


def clear() -> None:
    """Forgets everything that was kept."""
    try:
        with _lock:
            db = _open()
            with db:
                db.execute("DELETE FROM exif")
                db.execute("DELETE FROM facts")
    except (sqlite3.Error, OSError) as exc:
        logger.debug("What is kept on disk could not be cleared (%s).", exc)


class SqliteStore(Store):
    def get_tags(self, stamps: list[Stamp]) -> dict[Stamp, Tags]:
        return get_many(stamps)

    def put_tags(self, values: dict[Stamp, Tags]) -> None:
        put_many(values)

    def get_facts(self, stamps: list[Stamp], kind: str) -> dict[Stamp, str]:
        return get_facts(stamps, kind)

    def put_facts(self, values: dict[Stamp, str], kind: str) -> None:
        put_facts(values, kind)

    def clear(self) -> None:
        clear()
