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
    assert "--name" in docker_run
    assert "verge-sandbox-sb_test" in docker_run
    assert "verge.managed=true" in docker_run
    assert "verge.sandbox.id=sb_test" in docker_run
    assert "XVFB_WHD=1440x900x24" in docker_run
    assert "BROWSER_WINDOW_WIDTH=1440" in docker_run
    assert "BROWSER_WINDOW_HEIGHT=900" in docker_run


def test_remove_managed_containers_removes_all_labeled_containers(monkeypatch) -> None:
    adapter = DockerAdapter()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="cid-1\ncid-2\n", stderr="")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("app.services.docker_adapter.subprocess.run", fake_run)

    adapter.remove_managed_containers()

    assert calls[0] == [
        "docker",
        "ps",
        "-aq",
        "--filter",
        "label=verge.managed=true",
    ]
    assert calls[1] == ["docker", "rm", "-f", "cid-1"]
    assert calls[2] == ["docker", "rm", "-f", "cid-2"]


def test_list_managed_container_refs_reads_sandbox_labels(monkeypatch) -> None:
    adapter = DockerAdapter()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="cid-1\ncid-2\n", stderr="")
        if cmd[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="cid-1\tsb_1\ncid-2\t\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("app.services.docker_adapter.subprocess.run", fake_run)

    refs = adapter.list_managed_container_refs()

    assert calls[0] == [
        "docker",
        "ps",
        "-aq",
        "--filter",
        "label=verge.managed=true",
    ]
    assert calls[1] == [
        "docker",
        "inspect",
        "--format",
        '{{.Id}}\t{{index .Config.Labels "verge.sandbox.id"}}',
        "cid-1",
        "cid-2",
    ]
    assert [(ref.container_id, ref.sandbox_id) for ref in refs] == [("cid-1", "sb_1"), ("cid-2", None)]
