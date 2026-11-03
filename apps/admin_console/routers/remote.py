"""Remote Phone REST API."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from artemis.runtime import device_pool
from ..services.device_stream_service import device_stream_service
from ..services import device_input_service as inputs

router = APIRouter(tags=["remote"])
HEADERS = {"Cache-Control": "no-store"}

def error(exc: inputs.InputError):
    return JSONResponse({"code": exc.code, "detail": exc.detail}, status_code=exc.status, headers=HEADERS)

async def guarded(request: Request, operation, payload: dict):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        return JSONResponse({"code":"invalid_content_type","detail":"Content-Type must be application/json"}, status_code=415, headers=HEADERS)
    if not inputs.control_allowed(request.client.host if request.client else None):
        return JSONResponse({"code":"control_disabled","detail":"Remote control is disabled outside loopback"}, status_code=409, headers=HEADERS)
    try: return JSONResponse(await operation(payload), headers=HEADERS)
    except inputs.InputError as exc: return error(exc)

async def json_body(request: Request) -> dict:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise inputs.InputError(415, "invalid_content_type", "Content-Type must be application/json")
    try:
        value = await request.json()
    except Exception as exc:
        raise inputs.InputError(422, "invalid_json", "Request body must be valid JSON") from exc
    if not isinstance(value, dict): raise inputs.InputError(422, "invalid_json", "Request body must be an object")
    return value

@router.get("/api/remote/devices")
async def remote_devices():
    devices = await device_pool.try_list_devices_async() or []
    result = []
    for d in devices:
        state = await device_stream_service.get_state(d.serial)
        result.append({"serial": d.serial, "model": d.model or d.serial, "state": d.state, "is_busy": d.is_busy,
                       "busy_session_id": d.active_session_id, "screen_width": state["screen_width"],
                       "screen_height": state["screen_height"], "controllable": d.state == "device" and not d.is_busy,
                       "uncontrollable_reason": "busy" if d.is_busy else (None if d.state == "device" else d.state)})
    return JSONResponse({"devices": result}, headers=HEADERS)

@router.get("/api/remote/state")
async def remote_state(device_serial: str):
    devices = await device_pool.try_list_devices_async() or []
    d = next((x for x in devices if x.serial == device_serial), None)
    if d is None: return JSONResponse({"code":"device_not_found","detail":"Device serial was not found"}, status_code=404, headers=HEADERS)
    value = await device_stream_service.get_state(device_serial)
    value.update({"state": d.state, "controllable": d.state == "device" and not d.is_busy,
                  "reason": "busy" if d.is_busy else (None if d.state == "device" else d.state)})
    return JSONResponse(value, headers=HEADERS)

@router.get("/api/remote/stream")
async def remote_stream(device_serial: str):
    devices = await device_pool.try_list_devices_async() or []
    if not any(d.serial == device_serial for d in devices):
        return JSONResponse({"code":"device_not_found","detail":"Device serial was not found"}, status_code=404, headers=HEADERS)
    return StreamingResponse(device_stream_service.mjpeg_frame_generator(device_serial), media_type="multipart/x-mixed-replace; boundary=frame", headers={**HEADERS, "Connection":"keep-alive"})

@router.post("/api/remote/input/tap")
async def remote_tap(request: Request):
    try: return await guarded(request, inputs.tap, await json_body(request))
    except inputs.InputError as exc: return error(exc)
@router.post("/api/remote/input/swipe")
async def remote_swipe(request: Request):
    try: return await guarded(request, inputs.swipe, await json_body(request))
    except inputs.InputError as exc: return error(exc)
@router.post("/api/remote/input/text")
async def remote_text(request: Request):
    try: return await guarded(request, inputs.text, await json_body(request))
    except inputs.InputError as exc: return error(exc)
@router.post("/api/remote/input/key")
async def remote_key(request: Request):
    try: return await guarded(request, inputs.key, await json_body(request))
    except inputs.InputError as exc: return error(exc)
