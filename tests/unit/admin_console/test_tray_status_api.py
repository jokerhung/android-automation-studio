from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.admin_console.core.state import state
from apps.admin_console.routers import system


def test_tray_status_and_drain_block_new_work():
    app = FastAPI()
    app.include_router(system.router)
    client = TestClient(app)
    old = (state.is_draining, state.is_shutting_down)
    state.is_draining = False
    state.is_shutting_down = False
    try:
        status = client.get("/api/system/tray-status")
        assert status.status_code == 200 and status.json()["running"] is True
        assert status.json()["email_inflight"] == 0
        drained = client.post("/api/system/drain")
        assert drained.status_code == 200 and state.is_draining is True
        assert drained.json()["email_accepting_deliveries"] is False
    finally:
        state.is_draining, state.is_shutting_down = old
