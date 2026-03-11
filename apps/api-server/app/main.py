from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.routes.browser import router as browser_router
from app.routes.files import router as files_router
from app.routes.health import router as health_router
from app.routes.sandboxes import router as sandbox_router
from app.routes.vnc import router as vnc_router
from app.services.docker_adapter import docker_adapter
from app.services.registry import registry
from app.models.sandbox import SandboxStatus


def _reconcile_runtime_state() -> None:
    known_sandbox_ids = {sandbox.id for sandbox in registry.all()}
    for container in docker_adapter.list_managed_container_refs():
        sandbox_id = container.sandbox_id
        if sandbox_id not in known_sandbox_ids:
            docker_adapter.remove_container(container.container_id)
            continue

        sandbox = registry.get(sandbox_id)
        if sandbox is None:
            docker_adapter.remove_container(container.container_id)
            continue

        if not docker_adapter.container_exists(container.container_id):
            docker_adapter.remove_container(container.container_id)
            continue

        sandbox.container_id = container.container_id
        sandbox.runtime.host = docker_adapter.inspect_container_ip(container.container_id) or "127.0.0.1"
        sandbox.status = SandboxStatus.RUNNING
        sandbox.metadata.pop("runtime_error", None)
        registry.put(sandbox)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    registry.load_from_disk(
        settings.sandbox_base_dir,
        workspace_subdir=settings.workspace_subdir,
        downloads_subdir=settings.downloads_subdir,
        uploads_subdir=settings.uploads_subdir,
        browser_profile_subdir=settings.browser_profile_subdir,
    )
    _reconcile_runtime_state()
    yield


def _configure_admin_routes(app: FastAPI, admin_static_dir: Path) -> None:
    index_file = admin_static_dir / "index.html"
    if not index_file.is_file():
        return

    admin_root = admin_static_dir.resolve()

    def _resolve_asset_path(asset_path: str) -> Path:
        resolved = (admin_root / asset_path).resolve()
        try:
            resolved.relative_to(admin_root)
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc
        return resolved

    @app.get("/admin", include_in_schema=False)
    async def admin_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/admin/", include_in_schema=False)
    async def admin_index_with_slash() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/admin/{asset_path:path}", include_in_schema=False)
    async def admin_asset_or_index(asset_path: str) -> FileResponse:
        resolved = _resolve_asset_path(asset_path)
        if resolved.is_file():
            return FileResponse(resolved)
        return FileResponse(index_file)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    _configure_admin_routes(app, settings.admin_static_dir)
    app.include_router(health_router)
    app.include_router(sandbox_router)
    app.include_router(browser_router)
    app.include_router(vnc_router)
    app.include_router(files_router)
    return app


app = create_app()
