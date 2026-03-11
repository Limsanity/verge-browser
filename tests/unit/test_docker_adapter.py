from __future__ import annotations

import subprocess
from pathlib import Path

from app.services.docker_adapter import DockerAdapter


def test_create_container_passes_matching_xvfb_and_browser_dimensions(monkeypatch) -> None:
    adapter = DockerAdapter()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="cid-123\n", stderr="")
        if cmd[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout='[{"NetworkSettings":{"Networks":{"bridge":{"IPAddress":"172.17.0.2"}}}}]',
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("app.services.docker_adapter.subprocess.run", fake_run)

    container_id, host = adapter.create_container(
        sandbox_id="sb_test",
        workspace_dir=Path("/tmp/workspace"),
        width=1440,
        height=900,
        default_url="about:blank",
        image="verge-browser-runtime:latest",
    )

    assert container_id == "cid-123"
    assert host == "172.17.0.2"
    docker_run = calls[0]
    assert "XVFB_WHD=1440x900x24" in docker_run
    assert "BROWSER_WINDOW_WIDTH=1440" in docker_run
    assert "BROWSER_WINDOW_HEIGHT=900" in docker_run
