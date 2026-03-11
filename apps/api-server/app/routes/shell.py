import asyncio

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.deps import require_sandbox
from app.schemas.shell import ShellExecRequest, ShellExecResponse, ShellSessionResponse
from app.services.shell import shell_service

router = APIRouter(prefix="/sandboxes/{sandbox_id}/shell", tags=["shell"])


@router.post("/exec", response_model=ShellExecResponse)
async def exec_shell(payload: ShellExecRequest, sandbox=Depends(require_sandbox)) -> ShellExecResponse:
    return await shell_service.exec(sandbox, payload)


@router.post("/sessions", response_model=ShellSessionResponse)
async def create_shell_session(
    sandbox_id: str,
    cwd: str = Query("/workspace"),
    sandbox=Depends(require_sandbox),
) -> ShellSessionResponse:
    session = await shell_service.create_session(sandbox, cwd=cwd)
    return ShellSessionResponse(
        session_id=session.session_id,
        ws_url=f"/sandboxes/{sandbox_id}/shell/sessions/{session.session_id}/ws",
    )


@router.websocket("/sessions/{session_id}/ws")
async def shell_session_ws(websocket: WebSocket, sandbox_id: str, session_id: str) -> None:
    require_sandbox(sandbox_id)
    session = await shell_service.get_session(session_id)
    if session is None or session.sandbox_id != sandbox_id:
        await websocket.close(code=4404, reason="shell session not found")
        return
    await websocket.accept()
    try:
        async def inbound() -> None:
            while True:
                data = await websocket.receive_text()
                await shell_service.send_input(session_id, data)

        async def outbound() -> None:
            while True:
                chunk = await shell_service.recv_output(session_id)
                if chunk == b"":
                    break
                await websocket.send_text(chunk.decode(errors="replace"))

        await asyncio.gather(inbound(), outbound())
    except WebSocketDisconnect:
        pass
    finally:
        await shell_service.close_session(session_id)
