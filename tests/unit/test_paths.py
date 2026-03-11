from pathlib import Path

import pytest

from app.utils.paths import safe_within_workspace


def test_safe_within_workspace_accepts_relative_path() -> None:
    workspace = Path("/tmp/workspace")
    result = safe_within_workspace(workspace, "a/b.txt")
    assert result == (workspace / "a/b.txt").resolve()


def test_safe_within_workspace_rejects_escape() -> None:
    workspace = Path("/tmp/workspace")
    with pytest.raises(ValueError):
        safe_within_workspace(workspace, "../etc/passwd")


def test_safe_within_workspace_accepts_workspace_absolute_path() -> None:
    workspace = Path("/tmp/workspace")
    result = safe_within_workspace(workspace, "/workspace/a/b.txt")
    assert result == (workspace / "a/b.txt").resolve()


def test_safe_within_workspace_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        safe_within_workspace(workspace, "escape/secrets.txt")
