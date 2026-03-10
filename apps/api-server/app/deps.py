from fastapi import Header, HTTPException, Request, WebSocket, status

from app.auth.jwt import decode_jwt
from app.services.registry import registry


def get_current_subject(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        return "anonymous"
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authorization header")
    payload = decode_jwt(token)
    return str(payload.get("sub", "anonymous"))


def require_sandbox(sandbox_id: str):
    sandbox = registry.get(sandbox_id)
    if sandbox is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sandbox not found")
    return sandbox


async def get_ws_subject(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization")
    if not auth:
        return "anonymous"
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        await websocket.close(code=4401, reason="invalid authorization header")
        raise RuntimeError("invalid websocket auth")
    payload = decode_jwt(token)
    return str(payload.get("sub", "anonymous"))


def get_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")

