#!/usr/bin/env python3
"""Compare built frontend artifacts and optionally benchmark ASGI static responses.

This measures filesystem inventory and in-process FastAPI/HTTPX request overhead.
It does not launch a server, use a network socket, render a page, or measure browser
performance.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = {
    "next": ROOT / "apps" / "showcase_next" / "out",
}
COUNTED_SUFFIXES = {"html": ".html", "css": ".css", "js": ".js"}


def inventory(selector: str, root: Path) -> dict[str, Any]:
    """Return a stable inventory for one artifact tree."""
    root = root.resolve()
    if not root.is_dir():
        return {
            "selector": selector,
            "status": "missing",
            "root": str(root),
            "error": f"artifact directory does not exist: {root}",
        }
    if not (root / "index.html").is_file():
        return {
            "selector": selector,
            "status": "missing",
            "root": str(root),
            "error": f"artifact is incomplete (index.html is missing): {root}",
        }

    paths = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda p: p.relative_to(root).as_posix())
    files = [{"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size} for path in paths]
    bytes_by_type = {
        name: sum(item["bytes"] for path, item in zip(paths, files) if path.suffix.lower() == suffix)
        for name, suffix in COUNTED_SUFFIXES.items()
    }
    return {
        "selector": selector,
        "status": "ok",
        "root": str(root),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "bytes_by_type": bytes_by_type,
        "files": files,
    }


def compare_inventories(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Return Next-minus-Angular numeric deltas when both builds exist."""
    angular = artifacts.get("angular")
    next_artifact = artifacts["next"]
    if not angular or angular["status"] != "ok" or next_artifact["status"] != "ok":
        return None
    return {
        "basis": "next_minus_angular",
        "file_count": next_artifact["file_count"] - angular["file_count"],
        "total_bytes": next_artifact["total_bytes"] - angular["total_bytes"],
        "bytes_by_type": {
            kind: next_artifact["bytes_by_type"][kind] - angular["bytes_by_type"][kind]
            for kind in COUNTED_SUFFIXES
        },
    }


def _latency_summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, (95 * len(ordered) + 99) // 100 - 1))
    return {
        "samples_ms": [round(value, 6) for value in values],
        "min_ms": round(ordered[0], 6),
        "median_ms": round(statistics.median(ordered), 6),
        "mean_ms": round(statistics.fmean(ordered), 6),
        "p95_ms": round(ordered[rank], 6),
    }


def _rss_bytes() -> int:
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("ASGI RSS measurement requires psutil") from exc
    return int(psutil.Process(os.getpid()).memory_info().rss)


async def measure_asgi_selector(
    selector: str,
    app: Any,
    *,
    samples: int,
    subsequent_requests: int,
    path: str,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
    rss_reader: Callable[[], int] = _rss_bytes,
) -> dict[str, Any]:
    """Measure first and reused-client response latency through ASGITransport."""
    from httpx import ASGITransport, AsyncClient

    previous = os.environ.get("ARTEMIS_FRONTEND")
    os.environ["ARTEMIS_FRONTEND"] = selector
    first_values: list[float] = []
    subsequent_values: list[float] = []
    statuses: list[int] = []
    gc.collect()
    rss_before = rss_reader()
    try:
        for _ in range(samples):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
                started = clock_ns()
                response = await client.get(path)
                first_values.append((clock_ns() - started) / 1_000_000)
                statuses.append(response.status_code)
                for _ in range(subsequent_requests):
                    started = clock_ns()
                    response = await client.get(path)
                    subsequent_values.append((clock_ns() - started) / 1_000_000)
                    statuses.append(response.status_code)
        gc.collect()
        rss_after = rss_reader()
    finally:
        if previous is None:
            os.environ.pop("ARTEMIS_FRONTEND", None)
        else:
            os.environ["ARTEMIS_FRONTEND"] = previous

    return {
        "selector": selector,
        "transport": "httpx.ASGITransport (in-process; no network/server/browser)",
        "path": path,
        "sample_count": samples,
        "subsequent_requests_per_sample": subsequent_requests,
        "status_codes": sorted(set(statuses)),
        "first_response": _latency_summary(first_values),
        "subsequent_response": _latency_summary(subsequent_values),
        "process_rss": {
            "before_bytes": rss_before,
            "after_bytes": rss_after,
            "delta_bytes": rss_after - rss_before,
        },
    }


async def measure_asgi(samples: int, subsequent_requests: int, path: str) -> dict[str, Any]:
    """Load the production FastAPI app once and measure both runtime selectors."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from apps.admin_console.server import app

    results: dict[str, Any] = {}
    for selector in ("next",):
        results[selector] = await measure_asgi_selector(
            selector, app, samples=samples, subsequent_requests=subsequent_requests, path=path
        )
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--angular-root", type=Path, default=None, help="Optional archived Angular export for historical comparison")
    parser.add_argument("--next-root", type=Path, default=DEFAULT_ARTIFACTS["next"])
    parser.add_argument("--measure-asgi", action="store_true", help="measure in-process FastAPI response overhead")
    parser.add_argument("--samples", type=int, default=5, help="independent clients/first-response samples")
    parser.add_argument("--subsequent-requests", type=int, default=5, help="reused-client requests per sample")
    parser.add_argument("--path", default="/", help="ASGI path to request")
    args = parser.parse_args(argv)
    if args.samples < 1 or args.subsequent_requests < 1:
        parser.error("--samples and --subsequent-requests must be positive")
    if not args.path.startswith("/"):
        parser.error("--path must start with /")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = {
        "next": inventory("next", args.next_root),
    }
    if args.angular_root is not None:
        artifacts["angular"] = inventory("angular", args.angular_root)
    output: dict[str, Any] = {
        "schema_version": 1,
        "scope": {
            "artifact_measurement": "uncompressed files and bytes on disk",
            "asgi_measurement": "optional in-process HTTPX/FastAPI response overhead and process RSS delta",
            "browser_performance": False,
        },
        "artifacts": artifacts,
        "comparison": compare_inventories(artifacts),
    }
    missing = [name for name, artifact in artifacts.items() if artifact["status"] != "ok"]
    if args.measure_asgi and not missing:
        output["asgi"] = asyncio.run(measure_asgi(args.samples, args.subsequent_requests, args.path))
    elif args.measure_asgi:
        output["asgi"] = {"status": "skipped", "error": f"missing artifact(s): {', '.join(missing)}"}
    print(json.dumps(output, indent=2, sort_keys=True))
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
