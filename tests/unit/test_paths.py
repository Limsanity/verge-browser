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
