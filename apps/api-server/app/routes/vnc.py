from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import websockets

from app.auth.tickets import issue_ticket, verify_ticket
from app.deps import get_current_subject, require_sandbox

router = APIRouter(prefix="/sandboxes/{sandbox_id}/vnc", tags=["vnc"])


@router.post("/tickets")
async def create_vnc_ticket(sandbox_id: str, subject: str = Depends(get_current_subject)) -> dict[str, str]:
    ticket = issue_ticket(sandbox_id=sandbox_id, subject=subject, ticket_type="vnc", scope="connect")
    return {"ticket": ticket}


@router.get("/", response_class=HTMLResponse)
async def vnc_entry(sandbox_id: str, ticket: str = Query(...), sandbox=Depends(require_sandbox)) -> HTMLResponse:
    del sandbox
    verify_ticket(ticket, sandbox_id=sandbox_id, ticket_type="vnc", scope="connect", consume=True)
    html = """
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Verge Browser VNC</title></head>
  <body>
    <h1>VNC Session Ready</h1>
    <p>Connect the noVNC client to <code>/sandboxes/{sandbox_id}/vnc/websockify</code>.</p>
  </body>
</html>
"""
    return HTMLResponse(html.replace("{sandbox_id}", sandbox_id))


@router.websocket("/websockify")
async def vnc_websockify_proxy(websocket: WebSocket, sandbox_id: str) -> None:
    sandbox = require_sandbox(sandbox_id)
    await websocket.accept()
    upstream_url = f"ws://{sandbox.runtime.host}:{sandbox.runtime.vnc_port}"
    try:
        async with websockets.connect(upstream_url, ping_interval=20, ping_timeout=20, max_queue=100) as upstream:
            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if "text" in message:
                        await upstream.send(message["text"])
                    elif "bytes" in message:
                        await upstream.send(message["bytes"])
                    else:
                        break

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            await __import__("asyncio").gather(client_to_upstream(), upstream_to_client())
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011, reason="vnc proxy error")
