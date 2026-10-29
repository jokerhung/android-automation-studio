"""Hermetic FastAPI host for browser smoke-testing the Next static export."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
EXPORT = ROOT / "out"
ADMIN = REPOSITORY / "apps" / "admin_console" / "index.html"
ROUTES = {
    "": "index.html",
    "workspace": "workspace/index.html",
    "task-schedule": "task-schedule/index.html",
    "settings": "settings/index.html",
    "check": "check/index.html",
}
PROTECTED = ("api/", "images/", "videos/", "local_file", "docs", "openapi.json", "redoc")
VIDEO = b"\x00\x00\x00\x18ftypmp42ARTEMIS-acceptance-video"
MJPEG_BOUNDARY = "artemis-acceptance-frame"
MJPEG_FRAME = b"\xff\xd8ARTEMIS-MJPEG-FRAME\xff\xd9"

app = FastAPI(
    title="ARTEMIS static export acceptance fixture",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def resolve(relative: str) -> Path | None:
    try:
        root = EXPORT.resolve()
        target = (root / relative).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_file() and target.is_relative_to(root) else None


def response(path: Path, relative: str, status_code: int = 200) -> FileResponse:
    if path.suffix.lower() in {".html", ".json"}:
        cache = "no-cache"
    elif relative.startswith("_next/static/"):
        cache = "public, max-age=31536000, immutable"
    else:
        cache = "public, max-age=3600"
    return FileResponse(path, status_code=status_code, headers={"Cache-Control": cache})


@app.get("/videos/sample.mp4", include_in_schema=False)
async def controlled_video(request: Request):
    headers = {"Accept-Ranges": "bytes", "X-Artemis-Acceptance": "controlled"}
    range_header = request.headers.get("range")
    if range_header is None:
        return Response(VIDEO, media_type="video/mp4", headers=headers)

    try:
        unit, requested = range_header.split("=", 1)
        if unit.strip().lower() != "bytes" or "," in requested:
            raise ValueError
        start_text, end_text = requested.strip().split("-", 1)
        if not start_text:
            length = int(end_text)
            if length <= 0:
                raise ValueError
            start = max(0, len(VIDEO) - length)
            end = len(VIDEO) - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else len(VIDEO) - 1
            if start < 0 or start >= len(VIDEO) or end < start:
                raise ValueError
            end = min(end, len(VIDEO) - 1)
    except (TypeError, ValueError):
        return Response(
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{len(VIDEO)}"},
        )

    body = VIDEO[start : end + 1]
    return Response(
        body,
        status_code=206,
        media_type="video/mp4",
        headers={**headers, "Content-Range": f"bytes {start}-{end}/{len(VIDEO)}"},
    )


@app.get("/api/stream/device-live", include_in_schema=False)
async def controlled_mjpeg():
    part = (
        f"--{MJPEG_BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(MJPEG_FRAME)}\r\n\r\n"
    ).encode("ascii") + MJPEG_FRAME + b"\r\n"
    body = part + part + f"--{MJPEG_BOUNDARY}--\r\n".encode("ascii")
    return Response(
        body,
        media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
        headers={"X-Artemis-Acceptance": "controlled"},
    )


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def controlled_api(path: str):
    # This process is the entire acceptance backend. It never imports Artemis
    # runtime services, opens settings, sends email, or talks to a device.
    return JSONResponse(
        {"detail": "Controlled acceptance API: endpoint not found", "path": path},
        status_code=404,
        headers={"X-Artemis-Acceptance": "controlled"},
    )


@app.get("/", include_in_schema=False)
async def root():
    return await static("")


@app.get("/{full_path:path}", include_in_schema=False)
async def static(full_path: str):
    clean = full_path.strip("/")
    if any(clean == prefix.rstrip("/") or clean.startswith(prefix) for prefix in PROTECTED):
        raise HTTPException(status_code=404, detail="Endpoint not found")
    if clean == "admin" or clean.startswith("admin/"):
        if ADMIN.is_file():
            return response(ADMIN, "index.html")
        raise HTTPException(status_code=404, detail="Admin console not found")
    if clean:
        emitted = resolve(clean)
        if emitted:
            return response(emitted, clean)
    route = ROUTES.get(clean)
    if route:
        emitted = resolve(route)
        if emitted:
            return response(emitted, route)
    elif clean.startswith("_next/") or Path(clean).suffix:
        raise HTTPException(status_code=404, detail="Static asset not found")
    not_found = resolve("404.html")
    if not_found:
        return response(not_found, "404.html", 404)
    return HTMLResponse("Next static export is missing; run npm run build.", status_code=503)


if __name__ == "__main__":
    if not (EXPORT / "index.html").is_file():
        raise SystemExit(
            "Next static export is missing; run npm run build before acceptance smoke."
        )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("ARTEMIS_ACCEPTANCE_PORT", "4173")),
        log_level="warning",
    )
