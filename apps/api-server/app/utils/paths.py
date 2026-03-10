from pathlib import Path


def safe_within_workspace(workspace: Path, user_path: str) -> Path:
    root = workspace.resolve()
    raw = Path(user_path)
    if raw.is_absolute():
        parts = raw.parts
        if parts[:2] == ("/", "workspace"):
            raw = Path(*parts[2:]) if len(parts) > 2 else Path(".")
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes workspace") from exc
    return resolved
