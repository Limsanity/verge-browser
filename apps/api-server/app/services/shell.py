from __future__ import annotations

import asyncio
import contextlib
import secrets
import time

from fastapi import HTTPException, status

from app.config import get_settings
from app.models.sandbox import SandboxRecord
from app.schemas.shell import ShellExecRequest, ShellExecResponse
from app.utils.paths import safe_within_workspace


class InteractiveShellSession:
    def __init__(self, session_id: str, sandbox_id: str, cwd: str) -> None:
        self.session_id = session_id
        self.sandbox_id = sandbox_id
        self.cwd = cwd
        self.proc: asyncio.subprocess.Process | None = None
        self.output_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self.reader_task: asyncio.Task[None] | None = None


class ShellService:
    def __init__(self) -> None:
        self._sessions: dict[str, InteractiveShellSession] = {}

    async def exec(self, sandbox: SandboxRecord, req: ShellExecRequest) -> ShellExecResponse:
        settings = get_settings()
        cwd = safe_within_workspace(sandbox.workspace_dir, req.cwd)
        started = time.perf_counter()
        if req.argv:
            command = list(req.argv)
            create_kwargs = {"program": command[0], "args": command[1:]}
        else:
            command = req.command or ""
            create_kwargs = {"cmd": command}

        try:
            if req.argv:
                proc = await asyncio.create_subprocess_exec(
                    create_kwargs["program"],
                    *create_kwargs["args"],
                    cwd=str(cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    create_kwargs["cmd"],
                    cwd=str(cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=req.timeout_sec)
        except TimeoutError as exc:
            proc.kill()
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="command timed out") from exc

        if len(stdout) > settings.shell_exec_output_limit or len(stderr) > settings.shell_exec_output_limit:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="command output too large")

        return ShellExecResponse(
            exit_code=proc.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def create_session(self, sandbox: SandboxRecord, cwd: str = "/workspace") -> InteractiveShellSession:
        session_id = secrets.token_hex(8)
        session = InteractiveShellSession(session_id=session_id, sandbox_id=sandbox.id, cwd=str(safe_within_workspace(sandbox.workspace_dir, cwd)))
        session.proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            cwd=session.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        session.reader_task = asyncio.create_task(self._pump_output(session))
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> InteractiveShellSession | None:
        return self._sessions.get(session_id)

    async def send_input(self, session_id: str, data: str) -> None:
        session = self._sessions.get(session_id)
        if session is None or session.proc is None or session.proc.stdin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shell session not found")
        session.proc.stdin.write(data.encode())
        await session.proc.stdin.drain()

    async def recv_output(self, session_id: str) -> bytes:
        session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shell session not found")
        return await session.output_queue.get()

    async def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        if session.proc and session.proc.returncode is None:
            session.proc.terminate()
            with contextlib.suppress(ProcessLookupError):
                await asyncio.wait_for(session.proc.wait(), timeout=2)
        if session.reader_task:
            session.reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session.reader_task

    async def _pump_output(self, session: InteractiveShellSession) -> None:
        assert session.proc is not None
        assert session.proc.stdout is not None
        while True:
            chunk = await session.proc.stdout.read(1024)
            if not chunk:
                break
            await session.output_queue.put(chunk)
        await session.output_queue.put(b"")


shell_service = ShellService()
