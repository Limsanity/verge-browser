# 基于 Xpra 的 Browser Sandbox 终态技术方案

## 1. 文档目标

本文档定义本仓库在 Ubuntu Server 容器部署场景下，彻底切换为 `xpra` 远程会话架构后的终态方案。

终态目标明确如下：

1. 运行时不再使用 `x11vnc`、`websockify`、`noVNC`。
2. 运行时不再使用独立 `Xvfb` 进程，显示会话由 `xpra` 直接承载。
3. 人工接管能力统一由 `xpra` 的 HTML5 client 提供。
4. 对外接口不再使用 `vnc` 语义，统一升级为 `session` 语义。
5. 文档、测试、管理端、脚本、SDK/CLI 示例全部以 `xpra session` 为唯一实现。
6. 保留 X11 语义，以便继续复用 `xdotool`、窗口枚举、X11 截图等现有 GUI 自动化链路。

本文档只描述终态，不讨论兼容期、双栈、迁移路径或灰度方案。

## 2. 终态设计原则

### 2.1 单容器单会话不变

每个 sandbox 仍然对应一个独立容器。容器内运行：

- `xpra`
- Chromium
- fcitx
- CDP relay
- supervisor

### 2.2 图形会话由 Xpra 独占承载

终态中，`xpra` 既负责：

- 创建 X11 display
- 承载 Chromium 图形会话
- 提供 HTML5 远程接管入口
- 提供 WebSocket 通道

系统中不再存在：

- `Xvfb`
- `x11vnc`
- `websockify`
- `noVNC`

### 2.3 远程接管语义统一为 Session

对外产品语义不再是 “VNC”，而是：

- Live Session
- Remote Session

本方案统一使用 `session` 作为 API 和实现命名。

### 2.4 保持 X11 工具链

虽然远程接管从 VNC 切到 Xpra，但不切到 Wayland。

原因是终态仍需要以下能力继续工作：

- `xdotool`
- `wmctrl`
- `x11-utils`
- ImageMagick `import`

这意味着当前 [apps/api-server/app/services/browser.py](apps/api-server/app/services/browser.py) 的大部分 GUI 自动化能力可以保留，只需要切换 display 来源和 readiness 逻辑。

## 3. 终态系统架构

### 3.1 总体架构

```text
Client / Agent / Human Operator
        |
        v
+----------------------------------+
| FastAPI Gateway / API Server     |
| REST + WS + Auth + Tickets       |
+----------------------------------+
        |
        +------------------------------+
        |                              |
        v                              v
+----------------------+      +----------------------+
| Browser APIs         |      | Session APIs         |
| screenshot/actions   |      | xpra html5/ws proxy  |
+----------------------+      +----------------------+
        |
        v
+----------------------------------------------------+
| Sandbox Container                                   |
|                                                    |
|  +--------------------+                            |
|  | Xpra Server        |                            |
|  | display=:100       |                            |
|  | html5 + ws         |                            |
|  +---------+----------+                            |
|            |                                       |
|            +-------------------+                   |
|                                |                   |
|                        +---------------+           |
|                        | Chromium      |           |
|                        +---------------+           |
|                                |                   |
|                        +---------------+           |
|                        | CDP relay     |           |
|                        +---------------+           |
|                                                    |
|  +----------------------+  +---------------------+ |
|  | /workspace           |  | supervisord         | |
|  +----------------------+  +---------------------+ |
|                                                    |
+----------------------------------------------------+
```

### 3.2 会话流

人工接管完整链路：

1. 用户调用 `POST /sandbox/{sandbox_id}/session/apply`
2. FastAPI 签发 `session` ticket
3. 用户访问 `GET /sandbox/{sandbox_id}/session/?ticket=...`
4. 服务端校验 ticket，写入短时 session cookie
5. FastAPI 返回或重定向到 Xpra HTML5 客户端入口
6. 页面后续静态资源和 WebSocket 都通过 FastAPI 代理到容器内的 Xpra 服务

CDP 链路保持不变：

1. 用户调用 `POST /sandbox/{sandbox_id}/cdp/apply`
2. WebSocket 代理转发到容器内 Chromium 的 CDP endpoint

GUI 自动化链路保持 X11 语义：

1. BrowserService 使用容器内 X11 工具注入动作
2. Chromium 窗口仍存在于 Xpra 提供的 X11 display 中

## 4. 终态运行时设计

## 4.1 运行时进程清单

终态 Supervisor 仅保留以下核心进程：

1. `xpra`
2. `fcitx`
3. `chromium`
4. `cdp-proxy`

不再存在的进程：

1. `xvfb`
2. `x11vnc`
3. `websockify`

### 4.2 进程职责

#### `xpra`

职责：

- 启动 X11 display
- 承载浏览器图形会话
- 提供 HTML5 静态资源和 WebSocket 通道
- 对内监听固定端口

#### `chromium`

职责：

- 连接到 `xpra` 创建的 display
- 使用持久化 profile 运行 GUI 浏览器
- 对内开启 CDP

#### `fcitx`

职责：

- 提供中文输入法能力
- 连接到与 Chromium 相同的 display

#### `cdp-proxy`

职责：

- 将容器内 `9222` relay 到 API 侧使用的暴露端口

## 4.2 Docker 镜像终态

文件：

- [docker/runtime-xpra.Dockerfile](docker/runtime-xpra.Dockerfile)

终态要求：

### 必须安装的包

- `chromium`
- `xpra`
- `openbox`
- `xdotool`
- `wmctrl`
- `x11-utils`
- `imagemagick`
- `socat`
- `supervisor`
- `fonts-noto-core`
- `fonts-noto-cjk`
- `fonts-noto-color-emoji`
- `fonts-liberation`
- `fontconfig`
- `fcitx`
- `fcitx-bin`
- `fcitx-table-all`
- `fcitx-googlepinyin`
- `fcitx-config-gtk`
- `fcitx-frontend-all`
- `fcitx-frontend-gtk2`
- `fcitx-frontend-gtk3`
- `fcitx-ui-classic`
- `dbus-x11`
- `locales`
- `curl`

### 必须删除的包

- `xvfb`
- `x11vnc`
- `novnc`
- `websockify`

### 终态环境变量

建议在镜像中定义如下环境变量：

```bash
DISPLAY=:100
XPRA_DISPLAY=:100
XPRA_BIND_HOST=0.0.0.0
XPRA_PORT=14500
XPRA_HTML5=on
BROWSER_REMOTE_DEBUGGING_PORT=9222
EXPOSED_CDP_PORT=9223
BROWSER_WINDOW_WIDTH=1280
BROWSER_WINDOW_HEIGHT=1024
BROWSER_DOWNLOAD_DIR=/workspace/downloads
BROWSER_USER_DATA_DIR=/workspace/browser-profile
DEFAULT_URL=about:blank
XMODIFIERS=@im=fcitx
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
LC_ALL=zh_CN.UTF-8
LANG=zh_CN.UTF-8
```

说明：

- `DISPLAY` 与 `XPRA_DISPLAY` 在终态中应保持一致。
- 不再定义 `VNC_SERVER_PORT`。
- 不再定义 `WEBSOCKET_PROXY_PORT`。
- 不再定义 `EXPOSED_CDP_PORT=9223` 以外的远程接管中间层端口。

### 终态暴露端口

镜像只需要暴露：

- `9223`，供 CDP relay 使用
- `14500`，供 Xpra HTML5 和 WebSocket 使用

## 4.3 Supervisor 终态

文件：

- [apps/runtime-xpra/supervisor/supervisord.conf](apps/runtime-xpra/supervisor/supervisord.conf)

终态 Supervisor 配置要求如下：

### 必须保留的 program

- `[program:xpra]`
- `[program:fcitx]`
- `[program:chromium]`
- `[program:cdp-proxy]`

### 必须删除的 program

- `[program:xvfb]`
- `[program:x11vnc]`
- `[program:websockify]`

### 启动顺序

推荐优先级：

1. `xpra`
2. `fcitx`
3. `chromium`
4. `cdp-proxy`

约束：

- `chromium` 启动前，`xpra` display 必须已经建立。
- `fcitx` 必须使用同一个 display。
- `cdp-proxy` 可在 Chromium 启动后立即提供 relay。

### 日志要求

终态必须有以下日志文件：

- `/var/log/sandbox/xpra.log`
- `/var/log/sandbox/xpra.err.log`
- `/var/log/sandbox/chromium.log`
- `/var/log/sandbox/chromium.err.log`
- `/var/log/sandbox/cdp-proxy.log`
- `/var/log/sandbox/cdp-proxy.err.log`
- `/var/log/sandbox/fcitx.log`
- `/var/log/sandbox/fcitx.err.log`

## 4.4 启动脚本终态

### 必须保留的脚本

- `start_all.sh`
- `start_browser.sh`
- `start_fcitx.sh`
- `start_cdp_proxy.sh`
- `healthcheck.sh`

### 必须新增的脚本

- `start_xpra.sh`

### 必须删除的脚本

- `start_x.sh`
- `start_x11vnc.sh`
- `start_websockify.sh`

## 4.5 `start_xpra.sh` 设计

文件：

- `apps/runtime-xpra/scripts/start_xpra.sh`

职责：

1. 清理旧的 Xpra runtime/socket 状态
2. 启动 Xpra server
3. 创建固定 display
4. 启用 HTML5 client
5. 绑定固定监听地址和端口
6. 以前台模式运行，交给 supervisor 托管

脚本必须满足：

- display 固定为 `:100`
- 必须开启 HTML5
- 监听 `0.0.0.0:${XPRA_PORT}`
- 不启用额外认证，鉴权统一由 FastAPI 负责
- 日志写入 stdout/stderr，由 supervisor 收集

脚本需要处理的异常：

- 旧 socket 未清理
- 上一次异常退出后 display 占用
- runtime 目录丢失
- HTML5 client 目录未找到

## 4.6 `start_browser.sh` 终态改造

文件：

- [apps/runtime-xpra/scripts/start_browser.sh](apps/runtime-xpra/scripts/start_browser.sh)

终态要求：

1. 不再依赖 `Xvfb`
2. 默认 display 来自 `DISPLAY` 环境变量，值为 `:100`
3. 启动 Chromium 前必须等待 Xpra display 就绪
4. 保留 profile lock 清理逻辑
5. 保留现有 CDP 暴露逻辑
6. 保留窗口尺寸和默认 URL 配置逻辑

建议保留的 Chromium 参数：

- `--display`
- `--no-first-run`
- `--no-default-browser-check`
- `--disable-background-networking`
- `--disable-dev-shm-usage`
- `--disable-popup-blocking`
- `--disable-features=TranslateUI`
- `--window-position=0,0`
- `--window-size=...`
- `--start-maximized`
- `--user-data-dir=...`
- `--remote-debugging-address=0.0.0.0`
- `--remote-debugging-port=9222`
- `--disk-cache-dir=/tmp/chrome-cache`
- `--force-color-profile=srgb`

建议重新评估但不属于本次方案强制项的参数：

- `--no-sandbox`
- `--disable-gpu`

本方案只要求 Xpra 替换，不强制同步处理浏览器指纹相关参数。

## 4.7 `start_fcitx.sh` 终态改造

文件：

- [apps/runtime-xpra/scripts/start_fcitx.sh](apps/runtime-xpra/scripts/start_fcitx.sh)

终态要求：

1. 使用 `DISPLAY=:100`
2. 与 Chromium 在同一个 Xpra 会话内运行
3. 保持中文输入法可用

## 4.8 `healthcheck.sh` 终态改造

文件：

- [apps/runtime-xpra/scripts/healthcheck.sh](apps/runtime-xpra/scripts/healthcheck.sh)

当前仅检查：

- `http://127.0.0.1:9222/json/version`

终态必须同时检查：

1. Chromium CDP 可访问
2. Xpra 服务端口可访问
3. Xpra display 已存在

即 healthcheck 需要覆盖：

- `curl http://127.0.0.1:9222/json/version`
- `xpra info --display=:100` 或等价检查
- `curl http://127.0.0.1:${XPRA_PORT}/` 或等价本地探测

## 5. API 终态设计

## 5.1 终态路由命名

终态不再保留 `/vnc` 路由。

统一使用如下路由：

```text
POST /sandbox/{sandbox_id}/session/apply
GET  /sandbox/{sandbox_id}/session/
GET  /sandbox/{sandbox_id}/session/{asset_path:path}
WS   /sandbox/{sandbox_id}/session/ws
```

终态必须删除：

```text
POST /sandbox/{sandbox_id}/vnc/apply
GET  /sandbox/{sandbox_id}/vnc/
GET  /sandbox/{sandbox_id}/vnc/{asset_path:path}
WS   /sandbox/{sandbox_id}/vnc/websockify
```

### 语义说明

- `session` 表示浏览器人工接管会话
- 具体后端唯一实现为 `xpra`
- API、SDK、CLI、前端不再暴露 `vnc` 文案

## 5.2 票据模型终态

终态不再签发 `vnc` 类型票据。

统一票据类型：

- `ticket_type="session"`
- `scope="connect"`

票据流程：

1. `POST /session/apply` 签发 ticket
2. `GET /session/?ticket=...` 校验 ticket
3. 服务端创建短时 `session` cookie
4. HTML5 页面、资源和 WebSocket 都依赖该 cookie

推荐 cookie 名称：

- `sandbox_session`

终态必须删除：

- `vnc_session`

## 5.3 Session 路由实现要求

新增文件：

- `apps/api-server/app/routes/session.py`

终态中 [apps/api-server/app/routes/vnc.py](apps/api-server/app/routes/vnc.py) 必须删除。

`session.py` 必须实现：

### `POST /session/apply`

职责：

- 校验 sandbox 存在且运行中
- 生成 `session` ticket
- 返回 session entry URL

返回结构建议：

```json
{
  "ticket": "...",
  "session_url": "https://api.example.com/sandbox/sb_xxx/session/?ticket=...",
  "mode": "one_time",
  "ttl_sec": 60,
  "expires_at": "2026-03-12T12:00:00Z"
}
```

### `GET /session/`

职责：

- 校验 ticket
- 创建短时 cookie
- 返回或重定向到 Xpra HTML5 入口页面

终态要求：

- 返回的前端入口必须是基于 Xpra 的 HTML5 client
- 不再拼接 `vnc.html`
- 不再拼接 `/websockify`

### `GET /session/{asset_path:path}`

职责：

- 代理 Xpra HTML5 静态资源
- 校验 cookie
- 透传正确的 content-type

### `WS /session/ws`

职责：

- 代理浏览器与 Xpra 的 WebSocket 通道
- 校验 cookie
- 转发文本和二进制消息

终态要求：

- WebSocket 上游目标必须是容器内 Xpra 的 WebSocket endpoint
- 不得再以 `websockify` 命名

## 5.4 RuntimeEndpoint 终态结构

文件：

- [apps/api-server/app/models/sandbox.py](apps/api-server/app/models/sandbox.py)

当前 `RuntimeEndpoint` 为：

- `host`
- `cdp_port`
- `vnc_port`
- `display`
- `browser_port`

终态必须改为表达 Xpra 会话信息。

推荐结构：

```python
class RuntimeEndpoint(BaseModel):
    host: str = "127.0.0.1"
    cdp_port: int = 9223
    session_port: int = 14500
    display: str = ":100"
    browser_debug_port: int = 9222
```

终态必须删除字段：

- `vnc_port`
- `browser_port`

终态新增字段：

- `session_port`
- `browser_debug_port`

## 5.5 Lifecycle 终态改造

文件：

- [apps/api-server/app/services/lifecycle.py](apps/api-server/app/services/lifecycle.py)

终态要求：

### sandbox 创建时

创建容器后，必须等待以下条件全部满足：

1. Chromium CDP 可访问
2. Xpra display 可访问
3. Xpra HTML5 服务可访问
4. 浏览器窗口发现成功

### readiness 逻辑

当前 `_wait_until_ready()` 只检查：

- CDP
- 窗口宽度

终态必须升级为：

- `browser_version()` 成功
- `get_viewport()` 成功
- `xpra` 服务探测成功

### 失败状态诊断

当 sandbox 启动失败时，metadata 中应记录：

- `runtime_error`
- `xpra_error`
- `chromium_error`
- `display`

## 5.6 新增 Remote Session Service

新增文件：

- `apps/api-server/app/services/session.py`

职责：

1. 拼接 session entry URL
2. 代理 Xpra HTML5 静态资源
3. 代理 Xpra WebSocket
4. 检查 session upstream readiness
5. 统一处理 content-type、query string、cookie 校验

该 service 是终态远程接管的唯一实现，不需要 backend 分发逻辑。

## 6. Browser Service 终态设计

文件：

- [apps/api-server/app/services/browser.py](apps/api-server/app/services/browser.py)

终态中 BrowserService 仍然是 GUI 自动化核心，但要适配 Xpra display。

## 6.1 可以保留的部分

以下能力在终态中可继续使用：

- `CdpClient`
- 页面级截图
- `xdotool` 动作注入
- `wmctrl`/`xdotool` 窗口发现
- `import -window` 的窗口截图

## 6.2 必须修改的部分

### display 使用

容器内所有依赖 X11 的命令必须显式运行在 `DISPLAY=:100` 或 sandbox 记录中的 `runtime.display` 上。

### 窗口发现逻辑

窗口发现脚本必须适配 Xpra 会话，确保：

- Chromium 启动后可稳定枚举到窗口
- 在 Xpra 初始阶段不把“短时未出现窗口”误判为硬失败

### 截图稳定性

终态保留两条截图能力：

1. 页面级截图：CDP
2. 窗口级截图：X11 `import`

窗口截图必须验证在 Xpra 下仍可稳定抓取 Chromium 窗口。

### 诊断日志

BrowserService 在失败时应输出：

- 当前 display
- 窗口发现脚本 stdout/stderr
- Chromium stderr

## 7. Docker Adapter 终态要求

文件：

- [apps/api-server/app/services/docker_adapter.py](apps/api-server/app/services/docker_adapter.py)

终态要求：

1. 运行容器时注入 `DISPLAY=:100`
2. 注入 `XPRA_DISPLAY=:100`
3. 注入 `XPRA_PORT=14500`
4. 注入浏览器窗口尺寸
5. 保持 workspace volume 挂载

容器创建参数需要移除：

- 与 VNC 相关的环境变量
- 与独立 `Xvfb` 相关的环境变量，例如 `XVFB_WHD`

## 8. 配置模型终态

文件：

- [apps/api-server/app/config.py](apps/api-server/app/config.py)

终态建议新增配置：

- `sandbox_session_port: int = 14500`
- `sandbox_display: str = ":100"`
- `sandbox_default_session_path: str = "/"`

终态建议删除配置概念：

- 与 VNC/noVNC 对外暴露相关的命名

## 9. 管理端终态设计

管理端需要全面去除 VNC 语义。

受影响位置包括：

- `apps/admin-web`
- 已构建产物 `apps/api-server/app/static/admin`

## 9.1 功能命名调整

终态 UI 文案：

- `Open Session`
- `Session URL`
- `Connect CDP`

必须删除：

- `Open VNC`
- `VNC URL`

## 9.2 API 调用调整

当前前端调用：

- `POST /sandbox/{id}/vnc/apply`

终态必须改为：

- `POST /sandbox/{id}/session/apply`

返回字段从：

- `vnc_url`

改为：

- `session_url`

## 9.3 前端入口假设

终态前端不得写死：

- `vnc.html`
- `/websockify`

前端只应消费后端返回的 entry URL。

## 10. SDK / CLI / 脚本终态设计

当前仓库中大量示例和脚本都使用 `vnc` 命名。

终态必须全面替换。

受影响位置至少包括：

- `docs/cli-sdk.md`
- `tests/scripts/get-vnc-url.sh`
- `tests/scripts/full-manual-tour.sh`
- `tests/scripts/create-sandbox.sh`

### 终态命令命名建议

CLI：

- `verge-browser sandbox session <id-or-alias>`

SDK：

- `get_session_url()`

Shell 脚本：

- `get-session-url.sh`

必须删除：

- `sandbox vnc`
- `get_vnc_url()`
- `get-vnc-url.sh`

## 11. 测试终态设计

终态切换为 Xpra 后，所有单元测试、集成测试、手工脚本都要同步重写。

## 11.1 单元测试

重点受影响文件包括：

- `tests/unit/test_api.py`
- `tests/unit/test_registry_persistence.py`

必须修改的断言：

1. `vnc_url` 改为 `session_url`
2. `/vnc/apply` 改为 `/session/apply`
3. 重定向目标不再是 `vnc.html?.../websockify`
4. cookie 名称从 `vnc_session` 改为 `sandbox_session`
5. runtime 序列化中的 `vnc_port` 改为 `session_port`

## 11.2 集成测试

重点受影响文件：

- `tests/integration/test_runtime_api.py`

必须覆盖：

1. sandbox 创建后 session apply 成功
2. session entry 返回正确入口
3. session cookie 正常建立
4. session 资源代理可用
5. session WebSocket 代理可建立
6. CDP、截图、动作注入不回归

## 11.3 手工验证脚本

必须重写或重命名：

- `tests/scripts/get-vnc-url.sh` -> `tests/scripts/get-session-url.sh`
- `tests/scripts/full-manual-tour.sh`
- `tests/scripts/create-sandbox.sh`

## 12. 文档终态改造范围

终态切换不是只改一个实现文件，而是全仓库语义替换。

必须同步更新的文档包括：

- [docs/tech.md](docs/tech.md)
- `docs/api.md`
- `docs/cli-sdk.md`
- `docs/todo.md`
- `docs/tech-0311.md`
- `docs/idea/tech1.md`
- `docs/idea/tech2.md`
- `docs/idea/t1.md`
- `docs/idea/req.md`

### 文档替换要求

必须统一替换以下概念：

- `VNC / noVNC` -> `Xpra Session`
- `vnc_url` -> `session_url`
- `Open VNC` -> `Open Session`
- `/vnc/...` -> `/session/...`
- `websockify` -> `session ws`

文档中涉及运行时架构图、端口说明、流程图、接口说明、示例代码、CLI 示例，均应按终态重写。

## 13. 终态文件改动清单

以下是终态方案下需要修改、删除或新增的主要文件。

### 13.1 必须修改

- [docker/runtime-xpra.Dockerfile](docker/runtime-xpra.Dockerfile)
- [apps/runtime-xpra/supervisor/supervisord.conf](apps/runtime-xpra/supervisor/supervisord.conf)
- [apps/runtime-xpra/scripts/start_browser.sh](apps/runtime-xpra/scripts/start_browser.sh)
- [apps/runtime-xpra/scripts/start_fcitx.sh](apps/runtime-xpra/scripts/start_fcitx.sh)
- [apps/runtime-xpra/scripts/start_cdp_proxy.sh](apps/runtime-xpra/scripts/start_cdp_proxy.sh)
- [apps/runtime-xpra/scripts/healthcheck.sh](apps/runtime-xpra/scripts/healthcheck.sh)
- [apps/api-server/app/models/sandbox.py](apps/api-server/app/models/sandbox.py)
- [apps/api-server/app/services/lifecycle.py](apps/api-server/app/services/lifecycle.py)
- [apps/api-server/app/services/browser.py](apps/api-server/app/services/browser.py)
- [apps/api-server/app/services/docker_adapter.py](apps/api-server/app/services/docker_adapter.py)
- [apps/api-server/app/config.py](apps/api-server/app/config.py)
- `apps/api-server/app/schemas/sandbox.py`
- `apps/api-server/app/main.py`
- `apps/admin-web/src/App.tsx`
- `apps/api-server/app/static/admin/*`
- `tests/unit/test_api.py`
- `tests/unit/test_registry_persistence.py`
- `tests/integration/test_runtime_api.py`
- `docs/tech.md`
- `docs/api.md`
- `docs/cli-sdk.md`

### 13.2 必须新增

- `apps/runtime-xpra/scripts/start_xpra.sh`
- `apps/api-server/app/routes/session.py`
- `apps/api-server/app/services/session.py`
- `tests/scripts/get-session-url.sh`

### 13.3 必须删除

- [apps/runtime-xvfb/scripts/start_x.sh](apps/runtime-xvfb/scripts/start_x.sh)
- [apps/runtime-xvfb/scripts/start_x11vnc.sh](apps/runtime-xvfb/scripts/start_x11vnc.sh)
- [apps/runtime-xvfb/scripts/start_websockify.sh](apps/runtime-xvfb/scripts/start_websockify.sh)
- [apps/api-server/app/routes/vnc.py](apps/api-server/app/routes/vnc.py)
- `tests/scripts/get-vnc-url.sh`

## 14. 终态运行时端口与协议

### 容器内端口

- `9222`：Chromium 原生 CDP
- `9223`：对 API server 暴露的 CDP relay
- `14500`：Xpra server，包含 HTML5 和 WebSocket

### 对外暴露方式

外部客户端不直接访问容器端口。

统一通过 FastAPI Gateway 访问：

- `/sandbox/{id}/cdp/browser?...`
- `/sandbox/{id}/session/...`

终态安全要求：

- 不允许直接暴露 `9222`
- 不允许直接暴露 `14500`
- 票据和 cookie 必须绑定 sandbox_id

## 15. 终态 readiness 规范

sandbox 仅在满足以下条件后才能标记为 `RUNNING`：

1. 容器已启动
2. `xpra` 进程已启动
3. `DISPLAY=:100` 可用
4. Chromium 已成功连接该 display
5. Chromium 的 `/json/version` 可访问
6. BrowserService 成功发现窗口
7. Xpra HTML5 入口可访问

只要其中任一条件不满足，就不能对外报告为可用。

## 16. 终态风险点

本方案描述的是终点，不代表实现上没有风险。终态必须重点验证以下问题：

1. Ubuntu 发行版里的 `xpra` HTML5 资源路径是否稳定。
2. Xpra 的 WebSocket 路径和 query 参数是否需要特殊适配。
3. `import -window` 在 Xpra 管理的 X11 session 下是否稳定。
4. Chromium 启动早于 Xpra display 就绪时是否会进入崩溃重启。
5. fcitx 在 Xpra session 中是否稳定工作。

这些是实现风险，但不改变终态方案本身。

## 17. 终态验证标准

只有满足以下标准，才能认为“已彻底切换为 Xpra”：

1. 镜像中不再安装 `x11vnc`、`websockify`、`novnc`、`xvfb`
2. 运行时不再启动任何 VNC 相关进程
3. 仓库 API 中不存在 `/vnc` 路由
4. 前端不存在 `Open VNC` 文案
5. 测试中不存在 `vnc_url`、`vnc_session`、`/websockify`
6. 文档中主设计不再描述 noVNC/VNC 接管
7. 新建 sandbox 可以成功：
   - 创建
   - 打开 session
   - 手工接管
   - 继续 CDP 自动化
   - 执行 GUI action
   - 截图

## 18. 结论

本仓库切换到 Xpra 的终态不是“把 noVNC 换成另一个前端页面”，而是完整替换以下三层：

1. 运行时图形承载层
2. API 接入语义层
3. 产品文案与测试契约层

终态下，系统的标准描述应变为：

- 每个 sandbox 在容器内运行一个由 `xpra` 承载的 Chromium GUI 会话
- 人工接管通过 `session` 接口进入 Xpra HTML5 client
- 自动化继续通过 CDP 和 X11 GUI action 完成

这就是本项目“彻底切换为 Xpra”的完整目标状态。
