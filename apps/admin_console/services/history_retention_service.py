"""Retention policy for old task history.

Two independent rules, both configured in Settings -> History and stored in SQLite
(``application_settings``/``history``); ``0`` disables a rule:

* ``media_retention_days``   - delete a finished task's videos, step screenshots and
  replay frames after N days. Logs (steps, traces, ``stdout.log``) are kept.
* ``history_retention_days`` - delete the whole task (all of its SQLite rows and files)
  after N days.

Only terminal sessions (completed / failed / stopped / cancelled) are ever touched, so
nothing that is still running or finalizing a recording is purged.
"""

from __future__ import annotations

import asyncio
import glob
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from artemis.config import DB_PATH, IMAGES_DIR, TEST_DATA_DIR, TRACES_PATH
from artemis.config.constants import MEDIA_PURGED_MARKER
from artemis.config.sqlite_store import get_settings_store
from artemis.data_engine.storage import StorageManager
from artemis.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETENTION_DAYS = 3650
TERMINAL_STATUSES = ("completed", "failed", "stopped", "cancelled")
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm"}
ACTIVE_RECORDING_STATUSES = ("recording", "finalizing")
_SAFE_IMAGE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_REPORTED_ERRORS = 10
_SECONDS_PER_DAY = 86400
# Orphans younger than this may still belong to a task that is starting up.
ORPHAN_GRACE_SECONDS = _SECONDS_PER_DAY


class RetentionSettingsError(ValueError):
    """The submitted retention settings are not valid."""


class _RunStats:
    def __init__(self) -> None:
        self.files_deleted = 0
        self.bytes_freed = 0
        self.media_sessions = 0
        self.history_sessions = 0
        self.orphans = {"images": 0, "replay_folders": 0, "task_folders": 0, "database_rows": 0}
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        logger.warning(f"History retention: {message}")
        if len(self.errors) < _MAX_REPORTED_ERRORS:
            self.errors.append(message)

    def remove_file(self, path: Path) -> None:
        try:
            size = path.stat().st_size
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            self.error(f"could not delete {path.name}: {exc}")
            return
        self.files_deleted += 1
        self.bytes_freed += size

    def remove_tree(self, path: Path) -> None:
        if not path.is_dir():
            return
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    self.bytes_freed += item.stat().st_size
                    self.files_deleted += 1
                except OSError:
                    pass
        try:
            shutil.rmtree(path)
        except OSError as exc:
            self.error(f"could not delete {path.name}: {exc}")


class HistoryRetentionService:
    def __init__(
        self,
        *,
        store=None,
        db_path: str | Path | None = None,
        traces_path: str | Path | None = None,
        images_dir: str | Path | None = None,
        replay_data_dir: str | Path | None = None,
        clock: Callable[[], float] = time.time,
        interval_seconds: float = 3600,
        initial_delay_seconds: float = 120,
    ) -> None:
        self._store = store
        self.db_path = Path(db_path) if db_path is not None else Path(DB_PATH)
        self.traces_path = Path(traces_path) if traces_path is not None else Path(TRACES_PATH)
        self.images_dir = Path(images_dir) if images_dir is not None else Path(IMAGES_DIR)
        self.replay_data_dir = (
            Path(replay_data_dir) if replay_data_dir is not None else Path(TEST_DATA_DIR)
        )
        self._clock = clock
        self._interval = interval_seconds
        self._initial_delay = initial_delay_seconds
        self._run_lock = threading.Lock()
        self._task: asyncio.Task | None = None

    @property
    def store(self):
        return self._store or get_settings_store()

    # ------------------------------------------------------------------ settings

    def get_settings(self) -> dict[str, Any]:
        document, version = self.store.history()
        return {
            "media_retention_days": int(document.get("media_retention_days") or 0),
            "history_retention_days": int(document.get("history_retention_days") or 0),
            "last_run": document.get("last_run"),
            "version": version,
            "storage": "sqlite",
        }

    def update_settings(self, media_days: Any, history_days: Any) -> dict[str, Any]:
        media = self._validate_days(media_days)
        history = self._validate_days(history_days)
        if media and history and history < media:
            raise RetentionSettingsError(
                "Task history must be kept at least as long as screenshots and videos."
            )
        self.store.history()
        self.store.update(
            "history",
            lambda document: {
                **document,
                "media_retention_days": media,
                "history_retention_days": history,
            },
        )
        return self.get_settings()

    @staticmethod
    def _validate_days(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise RetentionSettingsError("Retention days must be a whole number.")
        if value < 0 or value > MAX_RETENTION_DAYS:
            raise RetentionSettingsError(
                f"Retention days must be between 0 and {MAX_RETENTION_DAYS}."
            )
        return value

    # --------------------------------------------------------------------- runs

    def run_once(self, now: float | None = None) -> dict[str, Any]:
        """Apply both rules once. Safe to call concurrently: a second caller gets ``busy``."""
        if not self._run_lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            return self._run(self._clock() if now is None else now)
        finally:
            self._run_lock.release()

    def _run(self, now: float) -> dict[str, Any]:
        settings = self.get_settings()
        media_days = settings["media_retention_days"]
        history_days = settings["history_retention_days"]
        stats = _RunStats()
        if not media_days and not history_days:
            return {"status": "disabled", "ran_at": now}

        if media_days:
            for session_id in self._expired_sessions(now - media_days * _SECONDS_PER_DAY):
                if self._purge_media(session_id, stats, mark=True):
                    stats.media_sessions += 1
        if history_days:
            storage = StorageManager(self.db_path, self.traces_path)
            for session_id in self._expired_sessions(now - history_days * _SECONDS_PER_DAY):
                if self._purge_history(storage, session_id, stats):
                    stats.history_sessions += 1
        self._sweep_orphans(now, stats)
        if stats.media_sessions or stats.history_sessions or any(stats.orphans.values()):
            self._compact()

        result = {
            "status": "completed",
            "ran_at": now,
            "media_sessions_purged": stats.media_sessions,
            "history_sessions_deleted": stats.history_sessions,
            "orphans_removed": stats.orphans,
            "files_deleted": stats.files_deleted,
            "bytes_freed": stats.bytes_freed,
            "errors": stats.errors,
        }
        try:
            self.store.update("history", lambda document: {**document, "last_run": result})
        except Exception as exc:  # reporting must never fail the cleanup itself
            logger.warning(f"History retention: could not save last run: {exc}")
        logger.info(f"History retention finished: {result}")
        return result

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _expired_sessions(self, cutoff: float) -> list[str]:
        placeholders = ",".join("?" * len(TERMINAL_STATUSES))
        query = (
            "SELECT session_id FROM sessions "
            f"WHERE lower(coalesce(status,'')) IN ({placeholders}) "
            "AND coalesce(end_time,start_time) IS NOT NULL "
            "AND coalesce(end_time,start_time) < ? ORDER BY coalesce(end_time,start_time)"
        )
        conn = self._connect()
        try:
            return [row[0] for row in conn.execute(query, (*TERMINAL_STATUSES, cutoff))]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    # -------------------------------------------------------------------- media

    def _inside_traces(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.traces_path.resolve())
            return True
        except (ValueError, OSError):
            return False

    def _purge_media(
        self, session_id: str, stats: _RunStats, *, mark: bool, force: bool = False
    ) -> bool:
        """Delete a session's videos, screenshots and replay frames. Returns True if it ran.

        A recording that is still being finalized is skipped unless force is set.
        """
        conn = self._connect()
        try:
            active = conn.execute(
                "SELECT 1 FROM video_recordings WHERE session_id=? AND status IN (?,?) LIMIT 1",
                (session_id, *ACTIVE_RECORDING_STATUSES),
            ).fetchone()
            if active and not force:
                return False
            self._purge_videos(conn, session_id, stats)
            self._purge_screenshots(conn, session_id, stats)
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            stats.error(f"session {session_id[:8]}: {exc}")
            return False
        finally:
            conn.close()

        stats.remove_tree(self.replay_data_dir / f"{session_id}_chunked")
        if mark:
            self._write_marker(session_id, stats)
        return True

    def _purge_videos(self, conn: sqlite3.Connection, session_id: str, stats: _RunStats) -> None:
        raw_paths: list[str] = []
        for query in (
            "SELECT local_video_path FROM video_recordings WHERE session_id=?",
            "SELECT video_filepath FROM sessions WHERE session_id=?",
        ):
            raw_paths += [row[0] for row in conn.execute(query, (session_id,)) if row[0]]

        directories = {self.traces_path / session_id}
        recorded_folders: set[str] = set()
        for raw in raw_paths:
            path = Path(raw)
            if not path.is_absolute():
                path = self.traces_path.parent / path
            if not self._inside_traces(path):
                continue
            if path.suffix.lower() in VIDEO_SUFFIXES:
                stats.remove_file(path)
            directories.add(path.parent)
            recorded_folders.add(path.parent.name)

        # The recording folder is renamed after the run (``<name>_PASS_<time>`` /
        # ``<name>_FAIL_<time>``) while the database keeps the original path.
        reserved = {"", self.traces_path.name, self.images_dir.name, "replay"}
        for folder in recorded_folders - reserved:
            for sibling in self.traces_path.iterdir():
                if sibling.is_dir() and sibling.name.startswith(folder):
                    directories.add(sibling)

        protected = {self.traces_path.resolve(), self.images_dir.resolve()}
        for directory in directories:
            if not directory.is_dir() or not self._inside_traces(directory):
                continue
            if directory.resolve() in protected:
                continue
            for item in directory.iterdir():
                if item.is_file() and (
                    item.suffix.lower() in VIDEO_SUFFIXES or item.name.startswith("recording.")
                ):
                    stats.remove_file(item)

    def _purge_screenshots(
        self, conn: sqlite3.Connection, session_id: str, stats: _RunStats
    ) -> None:
        names = {
            name
            for row in conn.execute(
                "SELECT pre_image_name, post_image_name FROM steps WHERE session_id=?",
                (session_id,),
            )
            for name in row
            if name
        }
        if not names:
            return
        # Drop this session's references first, so whatever is still referenced afterwards
        # belongs to another session and must stay.
        conn.execute(
            "UPDATE steps SET pre_image_name=NULL, post_image_name=NULL WHERE session_id=?",
            (session_id,),
        )
        for name in names:
            if not _SAFE_IMAGE_NAME.match(name):
                continue
            if conn.execute(
                "SELECT 1 FROM steps WHERE pre_image_name=? OR post_image_name=? LIMIT 1",
                (name, name),
            ).fetchone():
                continue
            for image in self.images_dir.glob(glob.escape(name) + ".*"):
                if image.is_file():
                    stats.remove_file(image)
            conn.execute("DELETE FROM images WHERE image_name=?", (name,))

    def _write_marker(self, session_id: str, stats: _RunStats) -> None:
        try:
            directory = self.traces_path / session_id
            directory.mkdir(parents=True, exist_ok=True)
            (directory / MEDIA_PURGED_MARKER).touch()
        except OSError as exc:
            stats.error(f"session {session_id[:8]}: could not write marker: {exc}")

    # ------------------------------------------------------------------ orphans

    def _sweep_orphans(self, now: float, stats: _RunStats) -> None:
        """Remove leftovers of tasks that were deleted before deletion was complete.

        Earlier versions only removed a task's rows and recording; step screenshots,
        replay frames and some rows stayed behind. Nothing here touches a task that
        still exists, and anything younger than ORPHAN_GRACE_SECONDS is left alone.
        """
        grace_cutoff = now - ORPHAN_GRACE_SECONDS
        conn = self._connect()
        try:
            session_ids = {row[0] for row in conn.execute("SELECT session_id FROM sessions")}
            scheduled = self._scheduled_session_ids(conn)
            self._sweep_orphan_rows(conn, stats)
            self._sweep_orphan_images(conn, stats, grace_cutoff)
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            stats.error(f"orphan sweep: {exc}")
            return
        finally:
            conn.close()

        for chunked in self._children(self.replay_data_dir):
            session_id = chunked.name.removesuffix("_chunked")
            if chunked.name.endswith("_chunked") and session_id not in session_ids:
                if self._is_older(chunked, grace_cutoff):
                    stats.remove_tree(chunked)
                    stats.orphans["replay_folders"] += 1
        for folder in self._children(self.traces_path):
            if not self._is_task_folder(folder.name) or folder.name in session_ids | scheduled:
                continue
            if self._is_older(folder, grace_cutoff):
                stats.remove_tree(folder)
                stats.orphans["task_folders"] += 1

    @staticmethod
    def _children(directory: Path) -> list[Path]:
        try:
            return [item for item in directory.iterdir() if item.is_dir()]
        except OSError:
            return []

    @staticmethod
    def _is_task_folder(name: str) -> bool:
        try:
            return str(UUID(name)) == name.lower()
        except ValueError:
            return False

    @staticmethod
    def _is_older(path: Path, cutoff: float) -> bool:
        try:
            return path.stat().st_mtime < cutoff
        except OSError:
            return False

    @staticmethod
    def _scheduled_session_ids(conn: sqlite3.Connection) -> set[str]:
        try:
            rows = conn.execute(
                "SELECT session_id FROM task_schedule_runs WHERE session_id IS NOT NULL"
            )
            return {row[0] for row in rows}
        except sqlite3.OperationalError:  # schedules were never used
            return set()

    def _sweep_orphan_rows(self, conn: sqlite3.Connection, stats: _RunStats) -> None:
        for path_row in conn.execute(
            "SELECT local_video_path FROM video_recordings "
            "WHERE session_id NOT IN (SELECT session_id FROM sessions)"
        ).fetchall():
            video = Path(path_row[0]) if path_row[0] else None
            if video and self._inside_traces(video) and video.suffix.lower() in VIDEO_SUFFIXES:
                stats.remove_file(video)
        for table in ("video_recordings", "history_chunks"):
            removed = conn.execute(
                f"DELETE FROM {table} WHERE session_id NOT IN (SELECT session_id FROM sessions)"
            ).rowcount
            stats.orphans["database_rows"] += max(removed, 0)

    def _sweep_orphan_images(
        self, conn: sqlite3.Connection, stats: _RunStats, grace_cutoff: float
    ) -> None:
        # An image captured before the oldest remaining task started cannot belong to one,
        # so if no step references it any more it is left over from a deleted task.
        oldest = conn.execute("SELECT MIN(start_time) FROM sessions").fetchone()[0]
        cutoff = min(grace_cutoff, oldest) if oldest else grace_cutoff
        names = [
            row[0]
            for row in conn.execute(
                "SELECT image_name FROM images WHERE timestamp < ? "
                "AND image_name NOT IN (SELECT pre_image_name FROM steps "
                "WHERE pre_image_name IS NOT NULL) "
                "AND image_name NOT IN (SELECT post_image_name FROM steps "
                "WHERE post_image_name IS NOT NULL)",
                (cutoff,),
            )
        ]
        for name in names:
            if _SAFE_IMAGE_NAME.match(name):
                for image in self.images_dir.glob(glob.escape(name) + ".*"):
                    if image.is_file():
                        stats.remove_file(image)
            conn.execute("DELETE FROM images WHERE image_name=?", (name,))
            stats.orphans["images"] += 1

    # ------------------------------------------------------------------ history

    def _purge_history(self, storage: StorageManager, session_id: str, stats: _RunStats) -> bool:
        try:
            parsed = UUID(session_id)
        except ValueError:
            stats.error(f"session {session_id[:8]}: id is not a UUID, skipped")
            return False
        if not self._purge_media(session_id, stats, mark=False):
            return False
        try:
            storage.delete_session(parsed, vacuum=False)
        except Exception as exc:
            stats.error(f"session {session_id[:8]}: {exc}")
            return False
        return True

    def delete_session(self, session_id: str) -> dict[str, Any]:
        """Delete one task completely: database rows, logs, videos, screenshots, replay frames.

        Used by the workspace Delete button. Raises ValueError for a malformed id.
        """
        parsed = UUID(session_id)
        stats = _RunStats()
        self._purge_media(str(parsed), stats, mark=False, force=True)
        StorageManager(self.db_path, self.traces_path).delete_session(parsed)
        return {"files_deleted": stats.files_deleted, "bytes_freed": stats.bytes_freed, "errors": stats.errors}

    def _compact(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=60, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=60000")
            conn.execute("VACUUM")
        except sqlite3.Error as exc:
            logger.warning(f"History retention: VACUUM skipped: {exc}")
        finally:
            conn.close()

    # --------------------------------------------------------------- scheduling

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        await asyncio.sleep(self._initial_delay)
        while True:
            try:
                await asyncio.to_thread(self.run_once)
            except Exception as exc:
                logger.warning(f"History retention run failed: {exc}")
            await asyncio.sleep(self._interval)


history_retention_service = HistoryRetentionService()
