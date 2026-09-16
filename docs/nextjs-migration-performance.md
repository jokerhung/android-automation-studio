# Next frontend performance evidence

Captured on Windows with Node 24.18.1 from the production static exports. Artifact figures are deterministic uncompressed filesystem inventory. ASGI figures measure only in-process FastAPI/HTTPX response overhead and process RSS change: they do not start a network server, render a page, or claim browser/Android performance.

## Reproducible measurement

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/measure_frontend_artifacts.py --measure-asgi --samples 5 --subsequent-requests 5
```

The script exits with code 2 and emits a clear JSON `status: "missing"` error if either artifact is unavailable. The complete per-file inventories are included in its JSON output.

## Current measured output

Captured 2026-09-15 against the available `apps/showcase_ui/dist/frontend/browser` and `apps/showcase_next/out` artifacts. Latency and RSS values are environment-sensitive samples, not deterministic budgets. “First” means the first request on each of five fresh in-process HTTPX clients; “subsequent” pools five additional requests on each client. RSS deltas are sequential observations in one Python process, so import/cache warming can affect them.

```json
{
  "artifacts": {
    "angular": {
      "file_count": 8,
      "total_bytes": 2100424,
      "bytes_by_type": {"html": 63766, "css": 69152, "js": 1685429}
    },
    "next": {
      "file_count": 43,
      "total_bytes": 1056680,
      "bytes_by_type": {"html": 56466, "css": 34446, "js": 946632}
    }
  },
  "comparison": {
    "basis": "next_minus_angular",
    "file_count": 35,
    "total_bytes": -1043744,
    "bytes_by_type": {"html": -7300, "css": -34706, "js": -738797}
  },
  "asgi": {
    "angular": {
      "first_response_median_ms": 3.0146,
      "first_response_p95_ms": 51.5747,
      "subsequent_response_median_ms": 2.645,
      "subsequent_response_p95_ms": 3.5891,
      "process_rss_delta_bytes": 3538944,
      "status_codes": [200]
    },
    "next": {
      "first_response_median_ms": 2.9529,
      "first_response_p95_ms": 3.4294,
      "subsequent_response_median_ms": 2.8841,
      "subsequent_response_p95_ms": 3.5214,
      "process_rss_delta_bytes": 36864,
      "status_codes": [200]
    }
  },
  "browser_performance": false
}
```

## Verified build output

- Optimized compile: approximately 1.5–2.6 seconds in the current warm local environment.
- Static routes generated: Home, Workspace, Task Schedule, Settings, Check and exported 404.
- Shared first-load JavaScript reported by Next: 103 kB.
- Largest route first-load JavaScript reported by Next: Task Schedule, 124 kB.

## Remaining performance gates

- Measure cold FastAPI startup and first response for packaged Angular and Next wheels on the same host. The in-process samples above are not startup measurements.
- Measure Chromium route navigation and hydration for all five routes.
- Exercise long logs, SSE coalescing, live frames and multi-segment replay against controlled fixtures.
- Compare isolated-process RSS under the same workload; the current values are same-process deltas.
- Repeat the agreed measurements on Linux and macOS before changing the default.

## Dependency security evidence

The Next app now pins Playwright 1.55.1 and overrides transitive PostCSS 8.5.28 and Sharp 0.35.4 without upgrading Next across a major version. `npm audit --omit=dev` reports zero known vulnerabilities after the locked update.

## Docker build evidence

A full Linux-container build with `ARTEMIS_FRONTEND=next` now completes as `artemis-next-runtime:verify`. The first runtime launch exposed missing OpenCV/X11 shared libraries (`libxcb.so.1`); the Dockerfile now installs the required GLib/GL/X11 runtime libraries. The rebuilt container starts Uvicorn without Node and returns HTTP 200 for `/`, `/workspace/`, `/task-schedule/`, `/settings/`, and `/check/`, while an unknown UI route and missing `/api/*` return HTTP 404. The container was stopped and removed after the smoke.
