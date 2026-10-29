from apps.admin_console.services import media_service
from apps.admin_console.services.media_service import MediaService


def test_resolves_numbered_recording_after_trace_rename(tmp_path, monkeypatch):
    traces = tmp_path / "traces"
    renamed = traces / "web_123_session_PASS_2026-10-12T08-45-02"
    renamed.mkdir(parents=True)
    recording = renamed / "recording_007.mp4"
    recording.write_bytes(b"test video")
    old_path = traces / "web_123_session" / recording.name
    monkeypatch.setattr(media_service, "TRACES_PATH", traces)
    monkeypatch.setattr(media_service, "WORKSPACE_ROOT", tmp_path)

    result = MediaService.resolve_video_url(
        {"session_id": "session", "video_filepath": str(old_path)}, {}, {}
    )
    assert result == MediaService.path_to_video_url(recording)


def test_resolves_recording_repository_path_after_trace_rename(tmp_path, monkeypatch):
    traces = tmp_path / "traces"
    renamed = traces / "web_123_session_FAIL_2026-10-12T08-45-02"
    renamed.mkdir(parents=True)
    recording = renamed / "recording_002.mp4"
    recording.write_bytes(b"test video")
    monkeypatch.setattr(media_service, "TRACES_PATH", traces)
    monkeypatch.setattr(media_service, "WORKSPACE_ROOT", tmp_path)
    old_path = traces / "web_123_session" / recording.name
    result = MediaService.resolve_video_url(
        {"session_id": "session"}, {"session": str(old_path)}, {}
    )
    assert result == MediaService.path_to_video_url(recording)


def test_does_not_match_another_trace_prefix(tmp_path, monkeypatch):
    traces = tmp_path / "traces"
    other = traces / "web_123_session_extra_PASS_2026-10-12T08-45-02"
    other.mkdir(parents=True)
    (other / "recording_007.mp4").write_bytes(b"other video")
    monkeypatch.setattr(media_service, "TRACES_PATH", traces)
    monkeypatch.setattr(media_service, "WORKSPACE_ROOT", tmp_path)
    old_path = traces / "web_123_session" / "recording_007.mp4"
    assert MediaService.resolve_recorded_path(str(old_path)) == old_path
