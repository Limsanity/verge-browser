from __future__ import annotations

import asyncio
import base64
import subprocess
from pathlib import Path

import httpx
import orjson
from fastapi import HTTPException, status

from app.models.sandbox import SandboxRecord
from app.schemas.browser import BrowserActionType, BrowserActionsRequest, BrowserActionsResponse, ScreenshotEnvelope, ScreenshotMetadata, ScreenshotType


class BrowserService:
    async def browser_version(self, sandbox: SandboxRecord) -> dict:
        url = f"http://{sandbox.runtime.host}:{sandbox.runtime.cdp_port}/json/version"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception:
            return {}
        return response.json()

    async def screenshot(self, sandbox: SandboxRecord, screenshot_type: ScreenshotType, image_format: str) -> ScreenshotEnvelope:
        if screenshot_type == ScreenshotType.page:
            version = await self.browser_version(sandbox)
            if not version.get("webSocketDebuggerUrl"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="page screenshot unavailable")

        png = self._placeholder_png()
        width = 1280
        height = 1024
        return ScreenshotEnvelope(
            type=screenshot_type,
            format=image_format,  # type: ignore[arg-type]
            media_type=f"image/{image_format}",
            metadata=ScreenshotMetadata(
                width=width,
                height=height,
                page_viewport={"x": 0, "y": 80, "width": width, "height": height - 80},
                window_viewport={"x": 0, "y": 0, "width": width, "height": height},
            ),
            data_base64=base64.b64encode(png).decode(),
        )

    async def execute_actions(self, sandbox: SandboxRecord, request: BrowserActionsRequest) -> BrowserActionsResponse:
        errors: list[str] = []
        executed = 0
        for action in request.actions:
            try:
                await self._run_action(sandbox, action)
                executed += 1
            except Exception as exc:
                errors.append(str(exc))
                if not request.continue_on_error:
                    break
        return BrowserActionsResponse(
            ok=not errors,
            executed=executed,
            screenshot_after=request.screenshot_after,
            errors=errors,
        )

    async def _run_action(self, sandbox: SandboxRecord, action) -> None:
        del sandbox
        if action.type == BrowserActionType.WAIT:
            await asyncio.sleep((action.duration_ms or 0) / 1000)
            return
        cmd = ["xdotool"]
        if action.type == BrowserActionType.MOVE_TO:
            cmd += ["mousemove", str(action.x), str(action.y)]
        elif action.type in {BrowserActionType.CLICK, BrowserActionType.DOUBLE_CLICK, BrowserActionType.RIGHT_CLICK}:
            if action.x is not None and action.y is not None:
                cmd += ["mousemove", str(action.x), str(action.y)]
            button = {"left": "1", "middle": "2", "right": "3"}[
                "right" if action.type == BrowserActionType.RIGHT_CLICK else action.button.value
            ]
            clicks = "2" if action.type == BrowserActionType.DOUBLE_CLICK else "1"
            cmd += ["click", "--repeat", clicks, button]
        elif action.type == BrowserActionType.MOUSE_DOWN:
            cmd += ["mousedown", {"left": "1", "middle": "2", "right": "3"}[action.button.value]]
        elif action.type == BrowserActionType.MOUSE_UP:
            cmd += ["mouseup", {"left": "1", "middle": "2", "right": "3"}[action.button.value]]
        elif action.type == BrowserActionType.DRAG_TO:
            cmd += ["mousemove", "--sync", str(action.x), str(action.y)]
        elif action.type == BrowserActionType.SCROLL:
            direction = "4" if (action.delta_y or 0) > 0 else "5"
            cmd += ["click", "--repeat", str(abs(action.delta_y or 1)), direction]
        elif action.type == BrowserActionType.TYPE_TEXT:
            cmd += ["type", "--delay", "20", action.text or ""]
        elif action.type == BrowserActionType.KEY_PRESS:
            cmd += ["key", action.key or ""]
        elif action.type == BrowserActionType.HOTKEY:
            cmd += ["key", "+".join(action.keys)]
        else:
            raise ValueError(f"unsupported action type: {action.type}")
        await asyncio.to_thread(self._best_effort_run, cmd)

    def _best_effort_run(self, cmd: list[str]) -> None:
        subprocess.run(cmd, check=False, capture_output=True, text=True)

    def _placeholder_png(self) -> bytes:
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )


browser_service = BrowserService()

