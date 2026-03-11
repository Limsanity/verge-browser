import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.config import get_settings
from app.main import app
from app.main import create_app
from app.models.sandbox import SandboxStatus
from app.services.registry import registry


client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-admin-token"}


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_business_api_requires_admin_token() -> None:
    response = client.get("/sandboxes")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing authorization header"


def test_create_and_get_sandbox() -> None:
    created = client.post("/sandboxes", json={"width": 1440, "height": 900}, headers=AUTH_HEADERS)
    assert created.status_code == 201
    payload = created.json()
    sandbox_id = payload["id"]
    assert payload["alias"] is None
    assert payload["browser"]["viewport"] == {"width": 1440, "height": 900}
    fetched = client.get(f"/sandboxes/{sandbox_id}", headers=AUTH_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == sandbox_id
    assert fetched.json()["browser"]["viewport"] == {"width": 1440, "height": 900}


def test_list_and_update_sandbox_alias() -> None:
    created = client.post("/sandboxes", json={"alias": "shopping", "metadata": {"owner": "agent"}}, headers=AUTH_HEADERS)
    assert created.status_code == 201
    sandbox_id = created.json()["id"]

    listed = client.get("/sandboxes", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert any(item["id"] == sandbox_id and item["alias"] == "shopping" for item in listed.json())

    updated = client.patch(f"/sandboxes/{sandbox_id}", json={"alias": "shopping-2", "metadata": {"owner": "human"}}, headers=AUTH_HEADERS)
    assert updated.status_code == 200
    assert updated.json()["alias"] == "shopping-2"
    assert updated.json()["metadata"] == {"owner": "human"}

    fetched_by_alias = client.get("/sandboxes/shopping-2", headers=AUTH_HEADERS)
    assert fetched_by_alias.status_code == 200
    assert fetched_by_alias.json()["id"] == sandbox_id


def test_list_sandboxes_skips_browser_probe_for_stopped_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    created = client.post("/sandboxes", json={"alias": "sleepy"}, headers=AUTH_HEADERS)
    assert created.status_code == 201
    sandbox_id = created.json()["id"]
    sandbox = registry.get(sandbox_id)
    assert sandbox is not None
    sandbox.status = SandboxStatus.STOPPED
    sandbox.container_id = None
    registry.put(sandbox)

    async def fail_browser_probe(_sandbox):
        raise AssertionError("browser_version should not be called for stopped sandboxes")

    monkeypatch.setattr("app.routes.sandboxes.browser_service.browser_version", fail_browser_probe)

    listed = client.get("/sandboxes", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert any(item["id"] == sandbox_id and item["browser"]["browser_version"] is None for item in listed.json())


def test_alias_conflict_returns_409() -> None:
    first = client.post("/sandboxes", json={"alias": "dup"}, headers=AUTH_HEADERS)
    assert first.status_code == 201

    second = client.post("/sandboxes", json={"alias": "dup"}, headers=AUTH_HEADERS)
    assert second.status_code == 409
    assert second.json()["detail"] == "alias already exists"


def test_alias_cannot_match_existing_sandbox_id() -> None:
    first = client.post("/sandboxes", json={}, headers=AUTH_HEADERS)
    assert first.status_code == 201

    second = client.post("/sandboxes", json={"alias": first.json()["id"]}, headers=AUTH_HEADERS)
    assert second.status_code == 409
    assert second.json()["detail"] == "alias already exists"


def test_vnc_ticket_created_via_alias_works_with_canonical_entry_url() -> None:
    created = client.post("/sandboxes", json={"alias": "vnc-demo"}, headers=AUTH_HEADERS)
    assert created.status_code == 201
    sandbox = created.json()

    ticket = client.post("/sandboxes/vnc-demo/vnc/tickets", headers=AUTH_HEADERS)
    assert ticket.status_code == 200

    entry = client.get(f"/sandboxes/{sandbox['id']}/vnc/", params={"ticket": ticket.json()["ticket"]}, follow_redirects=False)
    assert entry.status_code == 302
    assert entry.headers["location"] == f"/sandboxes/{sandbox['id']}/vnc/vnc.html?path=/sandboxes/{sandbox['id']}/vnc/websockify&resize=scale&autoconnect=true"


def test_vnc_ticket_requires_existing_sandbox() -> None:
    response = client.post("/sandboxes/sb_missing/vnc/tickets", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_admin_console_serves_built_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    admin_dir = tmp_path / "admin"
    assets_dir = admin_dir / "assets"
    assets_dir.mkdir(parents=True)
    (admin_dir / "index.html").write_text("<!doctype html><title>admin</title>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('admin');", encoding="utf-8")

    monkeypatch.setenv("VERGE_ADMIN_STATIC_DIR", str(admin_dir))
    get_settings.cache_clear()
    client = TestClient(create_app())

    try:
        root = client.get("/admin")
        assert root.status_code == 200
        assert "text/html" in root.headers["content-type"]
        assert "<title>admin</title>" in root.text

        asset = client.get("/admin/assets/app.js")
        assert asset.status_code == 200
        assert "console.log('admin');" in asset.text

        spa_fallback = client.get("/admin/sandboxes/demo")
        assert spa_fallback.status_code == 200
        assert "<title>admin</title>" in spa_fallback.text
    finally:
        get_settings.cache_clear()
