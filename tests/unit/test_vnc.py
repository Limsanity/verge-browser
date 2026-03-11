from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from app.routes import vnc


def test_create_vnc_session_prunes_expired_entries() -> None:
    now = datetime.now(timezone.utc)
    vnc._vnc_sessions["expired"] = {
        "sandbox_id": "sb_old",
        "expires_at": now - timedelta(seconds=1),
    }

    session_id = vnc._create_vnc_session("sb_new")

    assert session_id in vnc._vnc_sessions
    assert "expired" not in vnc._vnc_sessions
    vnc._vnc_sessions.clear()


def test_validate_vnc_session_rejects_expired_session() -> None:
    vnc._vnc_sessions["expired"] = {
        "sandbox_id": "sb_1",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }

    with pytest.raises(HTTPException) as exc:
        vnc._validate_vnc_session("expired", "sb_1")

    assert exc.value.status_code == 401
    assert "expired" not in vnc._vnc_sessions
    vnc._vnc_sessions.clear()


@pytest.mark.asyncio
async def test_vnc_entry_enables_autoconnect_and_scaling(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    async def fake_proxy_vnc_asset(sandbox, asset_path: str, query: str | None = None) -> HTMLResponse:
        del sandbox
        captured["asset_path"] = asset_path
        captured["query"] = query
        return HTMLResponse("ok")

    monkeypatch.setattr(vnc, "_proxy_vnc_asset", fake_proxy_vnc_asset)
    monkeypatch.setattr(vnc, "verify_ticket", lambda *args, **kwargs: None)

    response = await vnc.vnc_entry("sb_test", ticket="ticket", sandbox=object())

    assert response.status_code == 200
    assert captured["asset_path"] == "vnc.html"
    assert captured["query"] == "path=sandboxes/sb_test/vnc/websockify&resize=scale&autoconnect=true"
    assert "vnc_session=" in response.headers["set-cookie"]
    vnc._vnc_sessions.clear()
