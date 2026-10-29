"""Public release checks must fail on 404 and unpublished helper changes."""

import io
from urllib.error import HTTPError

import pytest

from scripts import check_installer_release as release


class Response(io.BytesIO):
    status = 200


def test_unpublished_entry_point_returns_download_failure(monkeypatch, capsys):
    target = release.Resource("install.ps1", "https://example.test/install.ps1")
    monkeypatch.setattr(release, "resources", lambda *_: [target])

    def missing(request, **kwargs):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(release.urllib.request, "urlopen", missing)
    assert release.main([]) == 4
    captured = capsys.readouterr()
    assert "HTTP 404" in captured.out
    assert "release owner must publish" in captured.err


def test_helper_mismatch_blocks_release_even_when_installer_is_reachable(tmp_path, monkeypatch):
    local = tmp_path / "helper.py"
    local.write_bytes(b"unpublished helper\n")
    monkeypatch.setattr(
        release.urllib.request, "urlopen", lambda *a, **k: Response(b"old helper\n")
    )
    ok, detail = release.check(
        release.Resource("helper.py", "https://example.test/helper.py", local)
    )
    assert not ok and "differs" in detail


def test_text_match_tolerates_windows_line_endings(tmp_path, monkeypatch):
    local = tmp_path / "install.ps1"
    local.write_bytes(b"Write-Host 'OK'\r\n")
    monkeypatch.setattr(
        release.urllib.request, "urlopen", lambda *a, **k: Response(b"Write-Host 'OK'\n")
    )
    assert release.check(
        release.Resource("install.ps1", "https://example.test/install.ps1", local)
    )[0]


def test_archives_use_head_without_downloading_or_executing(monkeypatch):
    methods = []

    def opened(request, **kwargs):
        methods.append(request.get_method())
        return Response(b"")

    monkeypatch.setattr(release.urllib.request, "urlopen", opened)
    assert release.check(release.Resource("archive", "https://example.test/source.zip"))[0]
    assert methods == ["HEAD"]


def test_both_installers_helpers_and_archive_formats_are_checked():
    targets = release.resources("owner/repository", "release/test")
    labels = {target.label for target in targets}
    assert {
        "install.sh",
        "install.ps1",
        "scripts/install_runtime.py",
        "scripts/bootstrap_common.sh",
        "scripts/bootstrap_common.ps1",
    } <= labels
    assert "source archive (zip)" in labels and "source archive (tar.gz)" in labels
    assert all("release%2Ftest" in target.url for target in targets)


def test_invalid_repository_rejected_before_network():
    with pytest.raises(SystemExit) as exc:
        release.main(["--repo", "https://bad.example/repo"])
    assert exc.value.code == 2
