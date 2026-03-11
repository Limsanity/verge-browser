from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_sandbox() -> None:
    created = client.post("/sandboxes", json={"width": 1440, "height": 900})
    assert created.status_code == 201
    payload = created.json()
    sandbox_id = payload["id"]
    assert payload["browser"]["viewport"] == {"width": 1440, "height": 900}
    fetched = client.get(f"/sandboxes/{sandbox_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == sandbox_id
    assert fetched.json()["browser"]["viewport"] == {"width": 1440, "height": 900}


def test_vnc_ticket_requires_existing_sandbox() -> None:
    response = client.post("/sandboxes/sb_missing/vnc/tickets")
    assert response.status_code == 404


def test_shell_session_ws_is_scoped_to_sandbox() -> None:
    created_one = client.post("/sandboxes", json={})
    created_two = client.post("/sandboxes", json={})
    assert created_one.status_code == 201
    assert created_two.status_code == 201

    sandbox_one = created_one.json()["id"]
    sandbox_two = created_two.json()["id"]

    session_resp = client.post(f"/sandboxes/{sandbox_one}/shell/sessions")
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    try:
        with client.websocket_connect(f"/sandboxes/{sandbox_two}/shell/sessions/{session_id}/ws"):
            raise AssertionError("websocket handshake unexpectedly succeeded")
    except WebSocketDisconnect as exc:
        assert exc.code == 4404
