from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings
from app.models.sandbox import SandboxRecord
from app.schemas.files import FileEntry
from app.utils.paths import safe_within_workspace


class FileService:
    def list(self, sandbox: SandboxRecord, path: str) -> list[FileEntry]:
        target = safe_within_workspace(sandbox.workspace_dir, path)
        if not target.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="path not found")
        entries = []
        for item in sorted(target.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name)):
            stat = item.stat()
            entries.append(
                FileEntry(
                    name=item.name,
                    path=str(item),
                    size=stat.st_size,
                    is_dir=item.is_dir(),
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
        return entries

    def read_text(self, sandbox: SandboxRecord, path: str) -> str:
        target = safe_within_workspace(sandbox.workspace_dir, path)
        if not target.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
        return target.read_text(encoding="utf-8")

    def write_text(self, sandbox: SandboxRecord, path: str, content: str, overwrite: bool) -> Path:
        target = safe_within_workspace(sandbox.workspace_dir, path)
        if target.exists() and not overwrite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="file exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(f"{target.suffix}.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
        return target

    async def upload(self, sandbox: SandboxRecord, upload: UploadFile) -> Path:
        settings = get_settings()
        name = Path(upload.filename or "upload.bin").name
        target = safe_within_workspace(sandbox.workspace_dir, str(sandbox.uploads_dir / name))
        size = 0
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.file_upload_limit_bytes:
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="upload too large")
                fh.write(chunk)
        return target

    def delete(self, sandbox: SandboxRecord, path: str) -> None:
        target = safe_within_workspace(sandbox.workspace_dir, path)
        if not target.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="path not found")
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()

    def resolve_file(self, sandbox: SandboxRecord, path: str) -> Path:
        target = safe_within_workspace(sandbox.workspace_dir, path)
        if not target.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
        return target


file_service = FileService()
