from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from admin_console.routers import history_settings as router_module
from admin_console.replay_manager import ReplayManager
from admin_console.services.history_retention_service import (
    HistoryRetentionService,
    RetentionSettingsError,
)
from artemis.config.constants import MEDIA_PURGED_MARKER
from artemis.config.sqlite_store import SettingsStore
from artemis.data_engine.storage import StorageManager

DAY = 86400
NOW = 100 * DAY
OLD = NOW - 40 * DAY
RECENT = NOW - 2 * DAY


class Env:
    def __init__(self, root: Path):
        self.root = root
        self.traces = root / "traces"
        self.images = self.traces / "images"
        self.replay = self.traces / "replay" / "data"
        for folder in (self.images, self.replay):
            folder.mkdir(parents=True)
        self.db = self.traces / "data_engine.db"
        StorageManager(self.db, self.traces)  # creates the schema
        self.settings = SettingsStore(root / "settings.sqlite3")
        self.service = HistoryRetentionService(
            store=self.settings,
            db_path=self.db,
            traces_path=self.traces,
            images_dir=self.images,
            replay_data_dir=self.replay,
            clock=lambda: NOW,
        )

    def sql(self, query: str, params=()):
        conn = sqlite3.connect(self.db)
        try:
            rows = conn.execute(query, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def count(self, table: str, where: str = "1=1", params=()) -> int:
        return self.sql(f"SELECT COUNT(*) FROM {table} WHERE {where}", params)[0][0]

    def image(self, name: str) -> Path:
        path = self.images / f"{name}.jpg"
        path.write_bytes(b"jpg" * 10)
        self.sql("INSERT OR IGNORE INTO images(image_name,timestamp) VALUES(?,?)", (name, 1.0))
        return path

    def session(
        self, *, status="completed", ended=OLD, images=(), recording="ready", stale_path=False
    ) -> dict:
        sid = str(uuid.uuid4())
        video_dir = self.traces / f"web_1_{sid[:8]}_PASS"
        video_dir.mkdir()
        video = video_dir / "recording.mp4"
        video.write_bytes(b"v" * 100)
        # The database keeps the folder name from before the _PASS/_FAIL rename.
        recorded = (self.traces / video_dir.name.removesuffix("_PASS") / "recording.mp4") if stale_path else video
        manifest = video_dir / "recording.json"
        manifest.write_text("{}")
        steps_json = video_dir / "steps.json"
        steps_json.write_text("[]")
        session_dir = self.traces / sid
        session_dir.mkdir()
        log = session_dir / "stdout.log"
        log.write_text("log line")
        chunked = self.replay / f"{sid}_chunked" / "step_01"
        chunked.mkdir(parents=True)
        (chunked / "pre.jpg").write_bytes(b"x")
        self.sql(
            "INSERT INTO sessions(session_id,initial_goal,start_time,end_time,status,video_filepath)"
            " VALUES(?,?,?,?,?,?)",
            (sid, "goal", ended - 60, ended, status, str(recorded)),
        )
        self.sql(
            "INSERT INTO video_recordings(video_id,session_id,local_video_path,status)"
            " VALUES(?,?,?,?)",
            (str(uuid.uuid4()), sid, str(recorded), recording),
        )
        for index, name in enumerate(images):
            self.image(name)
            self.sql(
                "INSERT INTO steps(step_id,session_id,step_number,pre_image_name,summary)"
                " VALUES(?,?,?,?,?)",
                (str(uuid.uuid4()), sid, index, name, "step"),
            )
        step_id = str(uuid.uuid4())
        self.sql(
            "INSERT INTO steps(step_id,session_id,step_number,summary) VALUES(?,?,?,?)",
            (step_id, sid, 99, "last"),
        )
        self.sql(
            "INSERT INTO traces(trace_id,session_id,step_id,type,name,timestamp,payload)"
            " VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), sid, step_id, "log", "x", ended, "{}"),
        )
        self.sql(
            "INSERT INTO history_chunks(chunk_id,session_id) VALUES(?,?)",
            (str(uuid.uuid4()), sid),
        )
        return {
            "id": sid, "video": video, "manifest": manifest, "steps_json": steps_json,
            "log": log, "chunked": self.replay / f"{sid}_chunked", "dir": session_dir,
            "video_dir": video_dir,
        }


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def configure(env: Env, media: int, history: int) -> None:
    env.service.update_settings(media, history)


def test_defaults_are_off_and_updates_persist_in_sqlite(env):
    assert env.service.get_settings()["media_retention_days"] == 0
    assert env.service.get_settings()["history_retention_days"] == 0
    saved = env.service.update_settings(7, 30)
    assert (saved["media_retention_days"], saved["history_retention_days"]) == (7, 30)
    assert saved["storage"] == "sqlite"
    # A fresh service over the same database sees the saved values.
    again = HistoryRetentionService(store=SettingsStore(env.root / "settings.sqlite3"))
    assert again.get_settings()["history_retention_days"] == 30


@pytest.mark.parametrize(
    ("media", "history"),
    [(-1, 0), (0, -5), (3651, 0), (True, 0), (1.5, 0), ("7", 0), (30, 7)],
)
def test_invalid_settings_are_rejected(env, media, history):
    with pytest.raises(RetentionSettingsError):
        env.service.update_settings(media, history)
    assert env.service.get_settings()["media_retention_days"] == 0


def test_history_may_equal_media_and_either_rule_can_be_off(env):
    env.service.update_settings(7, 7)
    env.service.update_settings(0, 30)
    env.service.update_settings(7, 0)


def test_nothing_runs_while_both_rules_are_off(env):
    old = env.session(images=["aa"])
    assert env.service.run_once()["status"] == "disabled"
    assert old["video"].exists() and (env.images / "aa.jpg").exists()


def test_media_purge_keeps_logs_and_history_but_removes_media(env):
    old = env.session(images=["aa", "bb"])
    recent = env.session(ended=RECENT, images=["cc"])
    configure(env, 30, 0)

    result = env.service.run_once()

    assert result["status"] == "completed" and result["media_sessions_purged"] == 1
    assert not old["video"].exists() and not old["manifest"].exists()
    assert not (env.images / "aa.jpg").exists() and not (env.images / "bb.jpg").exists()
    assert not old["chunked"].exists()
    assert env.count("images", "image_name IN ('aa','bb')") == 0
    # Logs and task history survive.
    assert old["log"].exists() and old["steps_json"].exists()
    assert env.count("sessions", "session_id=?", (old["id"],)) == 1
    assert env.count("steps", "session_id=?", (old["id"],)) == 3
    assert env.count("traces", "session_id=?", (old["id"],)) == 1
    assert env.count("steps", "session_id=? AND pre_image_name IS NOT NULL", (old["id"],)) == 0
    assert (old["dir"] / MEDIA_PURGED_MARKER).exists()
    # The recent task keeps all of its media.
    assert recent["video"].exists() and (env.images / "cc.jpg").exists() and recent["chunked"].exists()
    assert result["files_deleted"] >= 4 and result["bytes_freed"] > 0


def test_media_purge_finds_a_recording_folder_renamed_after_the_run(env):
    old = env.session(images=["aa"], stale_path=True)
    assert not (env.traces / old["video_dir"].name.removesuffix("_PASS")).exists()
    configure(env, 30, 0)
    env.service.run_once()
    assert not old["video"].exists() and not old["manifest"].exists()
    assert env.count("sessions", "session_id=?", (old["id"],)) == 1


def test_media_purge_is_idempotent(env):
    env.session(images=["aa"])
    configure(env, 30, 0)
    env.service.run_once()
    second = env.service.run_once()
    assert second["status"] == "completed" and second["errors"] == []


def test_a_screenshot_still_used_by_a_recent_task_is_kept(env):
    old = env.session(images=["shared"])
    recent = env.session(ended=RECENT)
    env.sql(
        "UPDATE steps SET pre_image_name='shared' WHERE session_id=? AND step_number=99",
        (recent["id"],),
    )
    configure(env, 30, 0)
    env.service.run_once()
    assert (env.images / "shared.jpg").exists() and env.count("images", "image_name='shared'") == 1
    assert env.count("steps", "session_id=? AND pre_image_name='shared'", (old["id"],)) == 0


@pytest.mark.parametrize("status", ["running", "queued", "paused"])
def test_unfinished_tasks_are_never_touched(env, status):
    live = env.session(status=status, images=["aa"])
    configure(env, 1, 1)
    env.service.run_once()
    assert live["video"].exists() and (env.images / "aa.jpg").exists()
    assert env.count("sessions", "session_id=?", (live["id"],)) == 1


@pytest.mark.parametrize("state", ["recording", "finalizing"])
def test_a_session_still_finalizing_its_recording_is_skipped(env, state):
    pending = env.session(images=["aa"], recording=state)
    configure(env, 30, 30)
    result = env.service.run_once()
    assert pending["video"].exists() and (env.images / "aa.jpg").exists()
    assert result["media_sessions_purged"] == 0 and result["history_sessions_deleted"] == 0


def test_history_purge_removes_the_whole_task(env):
    old = env.session(images=["aa"])
    middle = env.session(ended=NOW - 10 * DAY, images=["bb"])
    recent = env.session(ended=RECENT)
    configure(env, 5, 30)

    result = env.service.run_once()

    assert result["history_sessions_deleted"] == 1 and result["media_sessions_purged"] == 2
    for table in ("sessions", "steps", "traces", "history_chunks", "video_recordings"):
        key = "session_id=?"
        assert env.count(table, key, (old["id"],)) == 0, table
    assert not old["dir"].exists() and not old["video"].exists() and not old["chunked"].exists()
    assert not (env.images / "aa.jpg").exists()
    # 10 days old: media is gone (rule 5d) but the task itself stays (rule 30d).
    assert env.count("sessions", "session_id=?", (middle["id"],)) == 1
    assert not middle["video"].exists() and middle["log"].exists()
    assert env.count("sessions", "session_id=?", (recent["id"],)) == 1 and recent["video"].exists()


def test_history_only_rule_also_deletes_media_of_removed_tasks(env):
    old = env.session(images=["aa"])
    configure(env, 0, 30)
    env.service.run_once()
    assert not old["video"].exists() and not (env.images / "aa.jpg").exists()
    assert env.count("sessions", "session_id=?", (old["id"],)) == 0


def test_last_run_is_saved_with_the_settings(env):
    env.session(images=["aa"])
    configure(env, 30, 0)
    env.service.run_once()
    last = env.service.get_settings()["last_run"]
    assert last["media_sessions_purged"] == 1 and last["ran_at"] == NOW


def test_a_second_concurrent_run_reports_busy(env):
    configure(env, 30, 0)
    assert env.service._run_lock.acquire(blocking=False)
    try:
        assert env.service.run_once() == {"status": "busy"}
    finally:
        env.service._run_lock.release()


def test_replay_does_not_rechunk_a_session_whose_media_was_purged(env):
    old = env.session(images=["aa"])
    configure(env, 30, 0)
    env.service.run_once()
    manager = ReplayManager.__new__(ReplayManager)
    manager.traces_path, manager.test_data_dir, manager.db_path = env.traces, env.replay, env.db
    manager.chunk_session_traces = lambda *_: pytest.fail("must not re-chunk purged media")
    assert manager._ensure_session_chunked(old["id"]) == old["chunked"]
    assert not old["chunked"].exists()


@pytest.fixture
def client(env, monkeypatch):
    monkeypatch.setattr(router_module, "history_retention_service", env.service)
    monkeypatch.setattr(router_module, "_require_server_bound_request", lambda *_: None)
    app = FastAPI()
    app.include_router(router_module.router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_reads_saves_and_validates(client, env):
    async with client as http:
        first = (await http.get("/api/settings/history")).json()
        assert (first["media_retention_days"], first["history_retention_days"]) == (0, 0)

        saved = await http.put("/api/settings/history", json={"media_retention_days": 7, "history_retention_days": 30})
        assert saved.status_code == 200 and saved.json()["history_retention_days"] == 30
        assert env.service.get_settings()["media_retention_days"] == 7

        for body in (
            {"media_retention_days": 30, "history_retention_days": 7},
            {"media_retention_days": -1, "history_retention_days": 0},
            {"media_retention_days": 99999, "history_retention_days": 0},
        ):
            assert (await http.put("/api/settings/history", json=body)).status_code == 422
        for body in ({"media_retention_days": "7", "history_retention_days": 0}, {"media_retention_days": 7}):
            assert (await http.put("/api/settings/history", json=body)).status_code == 422
        assert env.service.get_settings()["media_retention_days"] == 7


@pytest.mark.asyncio
async def test_api_run_now_and_busy(client, env):
    old = env.session(images=["aa"])
    env.service.update_settings(30, 0)
    async with client as http:
        ran = await http.post("/api/settings/history/run")
        assert ran.status_code == 200 and ran.json()["media_sessions_purged"] == 1
        assert ran.json()["settings"]["last_run"]["media_sessions_purged"] == 1
        assert not old["video"].exists()

        assert env.service._run_lock.acquire(blocking=False)
        try:
            assert (await http.post("/api/settings/history/run")).status_code == 409
        finally:
            env.service._run_lock.release()


@pytest.mark.asyncio
async def test_api_rejects_cross_origin_requests(env, monkeypatch):
    monkeypatch.setattr(router_module, "history_retention_service", env.service)
    monkeypatch.setattr(router_module, "_require_server_bound_request", lambda *_: None)
    app = FastAPI()
    app.include_router(router_module.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        denied = await http.put(
            "/api/settings/history",
            json={"media_retention_days": 1, "history_retention_days": 2},
            headers={"origin": "http://evil.example"},
        )
    assert denied.status_code == 403
    assert env.service.get_settings()["media_retention_days"] == 0


@pytest.fixture
def sessions_client(env, monkeypatch):
    from admin_console.routers import sessions as sessions_module

    monkeypatch.setattr(sessions_module, "history_retention_service", env.service)
    app = FastAPI()
    app.include_router(sessions_module.router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_workspace_delete_button_removes_every_file_of_the_task(sessions_client, env):
    doomed = env.session(ended=RECENT, images=["aa", "bb", "shared"], stale_path=True)
    keeper = env.session(ended=RECENT)
    env.sql("UPDATE steps SET pre_image_name='shared' WHERE session_id=? AND step_number=99", (keeper["id"],))

    async with sessions_client as http:
        response = await http.post(f"/api/sessions/{doomed['id']}/delete")

    assert response.status_code == 200 and response.json()["status"] == "success"
    # Database rows
    for table in ("sessions", "steps", "traces", "history_chunks", "video_recordings"):
        assert env.count(table, "session_id=?", (doomed["id"],)) == 0, table
    # Logs, recording folder (even when renamed after the run) and video
    assert not doomed["dir"].exists() and not doomed["video"].exists() and not doomed["video_dir"].exists()
    # Step screenshots and replay frames
    assert not (env.images / "aa.jpg").exists() and not (env.images / "bb.jpg").exists()
    assert env.count("images", "image_name IN ('aa','bb')") == 0
    assert not doomed["chunked"].exists()
    # A screenshot another task still uses stays, and so does the other task.
    assert (env.images / "shared.jpg").exists() and env.count("images", "image_name='shared'") == 1
    assert keeper["video"].exists() and keeper["dir"].exists() and keeper["chunked"].exists()


@pytest.mark.asyncio
async def test_workspace_delete_also_removes_a_task_whose_recording_never_finalized(sessions_client, env):
    stuck = env.session(images=["aa"], recording="finalizing")
    async with sessions_client as http:
        assert (await http.post(f"/api/sessions/{stuck['id']}/delete")).status_code == 200
    assert not stuck["video"].exists() and not (env.images / "aa.jpg").exists()
    assert env.count("sessions", "session_id=?", (stuck["id"],)) == 0


@pytest.mark.asyncio
async def test_workspace_delete_rejects_a_malformed_id_without_touching_anything(sessions_client, env):
    keep = env.session(images=["aa"])
    async with sessions_client as http:
        assert (await http.post("/api/sessions/not-a-uuid/delete")).status_code == 500
    assert keep["video"].exists() and (env.images / "aa.jpg").exists()


def _age(path: Path, when: float) -> Path:
    import os

    os.utime(path, (when, when))
    return path


def _orphan_task_folder(env: Env, *, when: float) -> Path:
    folder = env.traces / str(uuid.uuid4())
    folder.mkdir()
    (folder / "stdout.log").write_text("left behind")
    return _age(folder, when)


def _orphan_replay(env: Env, *, when: float) -> Path:
    folder = env.replay / f"{uuid.uuid4()}_chunked"
    (folder / "step_01").mkdir(parents=True)
    (folder / "step_01" / "pre.jpg").write_bytes(b"x" * 50)
    return _age(folder, when)


def test_sweep_removes_leftovers_of_tasks_deleted_long_ago_but_nothing_else(env):
    live = env.session(ended=RECENT, images=["live"])
    stale_task = _orphan_task_folder(env, when=NOW - 3 * DAY)
    young_task = _orphan_task_folder(env, when=NOW - 60)
    scheduled = _orphan_task_folder(env, when=NOW - 3 * DAY)
    env.sql(
        "INSERT INTO task_schedule_runs(id,schedule_id,schedule_version,due_at,trigger,task_snapshot_json,"
        "status,session_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "s", 1, "t", "due", "{}", "failed", scheduled.name, "t", "t"),
    )
    stale_replay = _orphan_replay(env, when=NOW - 3 * DAY)
    young_replay = _orphan_replay(env, when=NOW - 60)
    configure(env, 30, 0)

    result = env.service.run_once()

    assert not stale_task.exists() and not stale_replay.exists()
    assert young_task.exists() and young_replay.exists(), "tasks that may be starting are kept"
    assert scheduled.exists(), "a folder a schedule run still points to is kept"
    assert live["dir"].exists() and live["chunked"].exists() and live["video"].exists()
    for name in ("images", "replay"):
        assert (env.traces / name).is_dir()
    assert result["orphans_removed"]["task_folders"] == 1
    assert result["orphans_removed"]["replay_folders"] == 1


def test_sweep_removes_screenshots_no_step_uses_but_only_older_than_every_remaining_task(env):
    env.session(ended=RECENT, images=["used"])
    oldest_start = RECENT - 60
    for name, stamp in (("old_orphan", oldest_start - DAY), ("new_orphan", oldest_start + 10)):
        env.image(name)
        env.sql("UPDATE images SET timestamp=? WHERE image_name=?", (stamp, name))
    env.sql("UPDATE images SET timestamp=? WHERE image_name='used'", (oldest_start - DAY,))
    configure(env, 30, 0)

    result = env.service.run_once()

    assert not (env.images / "old_orphan.jpg").exists() and env.count("images", "image_name='old_orphan'") == 0
    assert (env.images / "new_orphan.jpg").exists(), "could belong to a kept task"
    assert (env.images / "used.jpg").exists() and env.count("images", "image_name='used'") == 1
    assert result["orphans_removed"]["images"] == 1


def test_sweep_removes_rows_whose_task_is_gone(env):
    env.session(ended=RECENT)
    ghost = str(uuid.uuid4())
    ghost_video = env.traces / "web_ghost" / "recording.mp4"
    ghost_video.parent.mkdir()
    ghost_video.write_bytes(b"v")
    env.sql("INSERT INTO history_chunks(chunk_id,session_id) VALUES(?,?)", (str(uuid.uuid4()), ghost))
    env.sql(
        "INSERT INTO video_recordings(video_id,session_id,local_video_path,status) VALUES(?,?,?,?)",
        (str(uuid.uuid4()), ghost, str(ghost_video), "ready"),
    )
    configure(env, 30, 0)

    result = env.service.run_once()

    assert env.count("history_chunks", "session_id=?", (ghost,)) == 0
    assert env.count("video_recordings", "session_id=?", (ghost,)) == 0
    assert not ghost_video.exists()
    assert result["orphans_removed"]["database_rows"] == 2
    assert env.count("history_chunks") == 1, "the live task's rows are untouched"


def test_sweep_does_not_run_while_both_rules_are_off(env):
    stale = _orphan_replay(env, when=NOW - 3 * DAY)
    assert env.service.run_once()["status"] == "disabled"
    assert stale.exists()


def test_sweep_is_idempotent(env):
    _orphan_replay(env, when=NOW - 3 * DAY)
    configure(env, 30, 0)
    env.service.run_once()
    again = env.service.run_once()
    assert again["orphans_removed"] == {"images": 0, "replay_folders": 0, "task_folders": 0, "database_rows": 0}
    assert again["errors"] == []
