from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from app.config import get_settings
from app.models.sandbox import RuntimeEndpoint, SandboxRecord, SandboxStatus, utcnow
from app.schemas.sandbox import CreateSandboxRequest
from app.services.docker_adapter import docker_adapter
from app.services.registry import registry


class SandboxLifecycleService:
    def create(self, req: CreateSandboxRequest) -> SandboxRecord:
        settings = get_settings()
        sandbox_id = f"sb_{secrets.token_hex(6)}"
        root = (settings.sandbox_base_dir / sandbox_id).resolve()
        workspace = root / settings.workspace_subdir
        downloads = workspace / settings.downloads_subdir
        uploads = workspace / settings.uploads_subdir
        profile = workspace / settings.browser_profile_subdir
        for path in (downloads, uploads, profile):
            path.mkdir(parents=True, exist_ok=True)

        container_id, host = docker_adapter.create_container(
            sandbox_id=sandbox_id,
            workspace_dir=workspace,
            width=req.width,
            height=req.height,
            default_url=req.default_url,
            image=req.image,
        )

        status = SandboxStatus.RUNNING if container_id else SandboxStatus.STARTING
        sandbox = SandboxRecord(
            id=sandbox_id,
            status=status,
            updated_at=utcnow(),
            workspace_dir=workspace,
            downloads_dir=downloads,
            uploads_dir=uploads,
            browser_profile_dir=profile,
            container_id=container_id,
            runtime=RuntimeEndpoint(host=host),
            metadata=req.metadata,
        )
        return registry.put(sandbox)

    def destroy(self, sandbox_id: str) -> bool:
        sandbox = registry.delete(sandbox_id)
        if sandbox is None:
            return False
        if sandbox.container_id:
            docker_adapter.remove_container(sandbox.container_id)
        root = sandbox.workspace_dir.parent
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        return True

    def restart_browser(self, sandbox_id: str) -> bool:
        sandbox = registry.get(sandbox_id)
        if sandbox is None or not sandbox.container_id:
            return False
        sandbox.status = SandboxStatus.STARTING
        sandbox.updated_at = utcnow()
        ok = docker_adapter.restart_browser(sandbox.container_id)
        sandbox.status = SandboxStatus.RUNNING if ok else SandboxStatus.DEGRADED
        sandbox.updated_at = utcnow()
        registry.put(sandbox)
        return ok


lifecycle_service = SandboxLifecycleService()

