from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_sandbox() -> None:
    created = client.post("/sandboxes", json={})
    assert created.status_code == 201
    payload = created.json()
    sandbox_id = payload["id"]
    fetched = client.get(f"/sandboxes/{sandbox_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == sandbox_id
