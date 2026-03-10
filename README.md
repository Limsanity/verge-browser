# Verge Browser

Verge Browser is a browser sandbox platform for agents.

It provides a single-session isolated runtime with:

- a real GUI Chromium instance
- Chrome DevTools Protocol (CDP) access
- VNC / noVNC human takeover
- GUI-level screenshots and input automation
- a shared `/workspace` file system
- shell execution and interactive terminal sessions
- a unified REST and WebSocket control plane

## Status

This repository is in active build-out.

The current codebase includes a working FastAPI service skeleton, sandbox lifecycle primitives, browser/files/shell/VNC route scaffolding, runtime container assets, and baseline tests. Some capabilities are intentionally still stubbed or partial, especially around real screenshot capture, full noVNC integration, and production-grade runtime orchestration.

## Why This Exists

Most browser automation systems focus on headless page control. That is not enough for agent workflows that need to combine:

- browser automation through CDP
- visual reasoning over the full browser window
- human takeover when automation stalls
- shared files and shell access inside the same environment

Verge Browser is designed to close that gap with a runtime model that keeps browser, GUI, shell, and files in one isolated sandbox.

## Architecture

At a high level, the platform is split into two parts:

1. API server
   Exposes REST and WebSocket endpoints for sandbox lifecycle, browser control, shell access, files, CDP proxying, and ticket-based VNC access.

2. Sandbox runtime
   Runs Chromium, Xvfb, Openbox, x11vnc, websockify, and supervisor inside a single isolated container with a shared `/workspace`.

```text
Client / Agent / Human
        |
        v
+------------------------------+
| FastAPI Gateway / API Server |
| Auth + REST + WS + Tickets   |
+------------------------------+
        |
        v
+-----------------------------------------------+
| Sandbox Runtime Container                     |
| Xvfb + Openbox + Chromium + x11vnc + tmux     |
| websockify + supervisor + /workspace          |
+-----------------------------------------------+
```

## Current Capabilities

The repository currently implements:

- FastAPI application bootstrap and configuration
- sandbox create / get / delete flow with an in-memory registry
- browser routes for info, screenshot, actions, restart, and CDP metadata
- CDP browser WebSocket proxy skeleton
- VNC ticket issuance and VNC WebSocket proxy skeleton
- shell one-shot command execution
- interactive shell session creation with WebSocket streaming
- file list, read, write, upload, download, and delete APIs
- `/workspace` path safety checks
- ticket signing, verification, and one-time consumption
- runtime Dockerfile, supervisor configuration, and startup scripts

## Repository Layout

```text
apps/
  api-server/         FastAPI application
  sandbox-runtime/    Runtime scripts and supervisor config
deployments/          Local deployment assets
docker/               Runtime container build files
tests/                Unit tests
```

## Quick Start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Start the API server

```bash
uvicorn app.main:app --app-dir apps/api-server --host 0.0.0.0 --port 8000 --reload
```

### 3. Run tests

```bash
PYTHONPATH=apps/api-server pytest
```

## Runtime Image

Build the sandbox runtime image with:

```bash
docker build -f docker/runtime/Dockerfile -t verge-browser-runtime:latest .
```

The runtime image is intended to host:

- Chromium
- Xvfb
- Openbox
- x11vnc
- noVNC / websockify
- tmux
- xdotool
- supervisor

## API Surface

The current API structure follows the `/sandboxes/{sandbox_id}/...` convention from the design document.

Representative endpoints:

- `POST /sandboxes`
- `GET /sandboxes/{id}`
- `DELETE /sandboxes/{id}`
- `GET /sandboxes/{id}/browser/info`
- `GET /sandboxes/{id}/browser/screenshot`
- `POST /sandboxes/{id}/browser/actions`
- `POST /sandboxes/{id}/browser/restart`
- `GET /sandboxes/{id}/browser/cdp/info`
- `WS /sandboxes/{id}/browser/cdp/browser`
- `POST /sandboxes/{id}/vnc/tickets`
- `WS /sandboxes/{id}/vnc/websockify`
- `POST /sandboxes/{id}/shell/exec`
- `POST /sandboxes/{id}/shell/sessions`
- `WS /sandboxes/{id}/shell/sessions/{session_id}/ws`
- `GET /sandboxes/{id}/files/list`
- `GET /sandboxes/{id}/files/read`
- `POST /sandboxes/{id}/files/write`
- `POST /sandboxes/{id}/files/upload`
- `GET /sandboxes/{id}/files/download`
- `DELETE /sandboxes/{id}/files`

## What Is Still In Progress

The following areas still need deeper implementation work before the project reaches the full V1 target described in [`docs/tech.md`](./docs/tech.md):

- real browser window capture instead of placeholder screenshots
- full page screenshot support through live CDP target selection
- complete noVNC static asset serving and session handoff flow
- stronger Docker lifecycle management and health-driven state transitions
- production-ready browser restart and degraded-state recovery
- broader integration and end-to-end coverage

## Development Notes

- The project targets Python 3.11+.
- The API server is implemented with FastAPI.
- WebSocket proxying is designed around CDP and VNC relay use cases.
- File operations are constrained to the sandbox workspace root.
- The current implementation favors a practical MVP structure over premature distribution or multi-tenant orchestration.

## Roadmap

The intended implementation order remains:

1. Harden the runtime container until Chromium, CDP, and VNC are reliable.
2. Replace placeholder browser services with real screenshot and window-inspection logic.
3. Complete CDP proxy behavior and Playwright compatibility validation.
4. Finish VNC ticket-to-session flow and noVNC delivery.
5. Expand shell, file, and integration testing coverage.
6. Add deployment polish, observability, and production hardening.

## License

No license has been added yet.
