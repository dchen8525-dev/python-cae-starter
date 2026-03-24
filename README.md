# Local CAE Job Service

一个可直接运行的最小原型项目，面向 Windows 本地环境，监听 `127.0.0.1:8765`，接收浏览器请求并按 `tool` 类型启动对应的 CAE 仿真工具。当前内置 `dummy_solver` 与 `ansa`，用于验证提交流程、SQLite 持久化、任务取消与 WebSocket 日志推送。

## 项目简介

- HTTP API 与 WebSocket 基于 FastAPI
- 外部程序启动基于 `subprocess`
- 任务状态持久化基于 SQLite
- 参数校验基于 Pydantic
- 不同求解器通过适配器模式封装
- 使用 `uvicorn` 启动服务
- 当前支持 `dummy_solver` 和 `ansa`

服务默认只监听本机：

- Host: `127.0.0.1`
- Port: `8765`

## 目录结构

```text
python-starter/
├─ app/
│  ├─ adapters/
│  │  ├─ base.py
│  │  ├─ dummy_solver.py
│  │  └─ registry.py
│  ├─ api/
│  │  └─ jobs.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ models.py
│  │  └─ security.py
│  ├─ services/
│  │  ├─ job_manager.py
│  │  ├─ log_stream.py
│  │  └─ process_runner.py
│  └─ main.py
├─ frontend/
│  └─ index.html
├─ scripts/
│  └─ dummy_solver.py
├─ data/
├─ workspaces/
├─ .env.example
├─ README.md
└─ requirements.txt
```

## 安装步骤

1. 使用 Python 3.11+ 创建虚拟环境。
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 复制环境变量文件：

```bash
cp .env.example .env
```

Windows PowerShell 可改为：

```powershell
Copy-Item .env.example .env
```

## 启动方式

使用 uvicorn 启动：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

启动后可访问：

- API 根路径: `http://127.0.0.1:8765/`
- 前端测试页: `http://127.0.0.1:8765/frontend/index.html`

## .env 配置说明

- `HOST`: 服务监听地址，默认 `127.0.0.1`
- `PORT`: 服务端口，默认 `8765`
- `ANSA_EXECUTABLE`: ANSA 启动器路径，建议指向 `ansa64.bat` 或 `ansa64.exe`
- `ANSA_SCRIPT_FILE`: ANSA 批处理脚本路径，例如 `C:\scripts\run_ansa.py`
- `ANSA_EXECPY_PREFIX`: 传给 `-execpy` 的脚本前缀，默认 `load_script:`
- `ANSA_BATCH_FLAGS`: ANSA 批处理标志，默认 `-b`
- `DATABASE_PATH`: SQLite 数据库文件路径，默认 `data/jobs.db`
- `WORKSPACE_ROOT`: 任务工作目录根路径，默认 `workspaces`
- `ALLOWED_ORIGINS`: CORS 白名单，逗号分隔
- `LOG_POLL_INTERVAL_SECONDS`: WebSocket 日志轮询间隔

## API 说明

### 提交任务

```bash
curl -X POST "http://127.0.0.1:8765/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "demo-job",
    "tool": "dummy_solver",
    "params": {
      "duration": 10,
      "fail": false
    }
  }'
```

### 提交 ANSA 任务

```bash
curl -X POST "http://127.0.0.1:8765/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "ansa-batch-demo",
    "tool": "ansa",
    "params": {
      "input_file": "C:\\models\\demo.ansa",
      "script_args": ["--deck", "NASTRAN"],
      "extra_args": ["-mesa"],
      "no_gui": true
    }
  }'
```

### 查询状态

```bash
curl "http://127.0.0.1:8765/jobs/<job_id>"
```

### 查询任务列表

```bash
curl "http://127.0.0.1:8765/jobs?status=running"
```

### 取消任务

```bash
curl -X POST "http://127.0.0.1:8765/jobs/<job_id>/cancel"
```

## WebSocket 测试方式

WebSocket 地址：

```text
ws://127.0.0.1:8765/ws/jobs/<job_id>
```

可以直接打开项目自带页面：

- `http://127.0.0.1:8765/frontend/index.html`

页面支持：

- 提交 `dummy_solver` 任务
- 提交 `ansa` 任务
- 查询状态
- 连接 WebSocket 查看日志增量输出

## 任务执行与状态策略

- 提交任务后先写入 SQLite，状态为 `pending`
- 后台异步执行时转为 `running`
- 每个任务创建独立目录：`workspaces/<job_id>/`
- 日志文件固定为：`workspaces/<job_id>/run.log`
- 子进程 PID 会写入数据库
- 正常结束后状态为 `success` 或 `failed`
- 用户取消后状态为 `cancelled`

服务重启策略：

- 历史任务仍可从 SQLite 查询
- 服务启动时，会把上次未完成的 `pending/running` 任务标记为 `failed`
- 错误信息会写为 `Service restarted before job completion.`

这是一种简单可控的最小策略，适合本地原型。若后续需要更强恢复能力，可以扩展为：

- 启动时扫描系统进程并尝试恢复 PID
- 为每个任务记录更多恢复元数据
- 增加 `orphaned` 状态并实现人工接管流程

## 如何扩展真实 CAE 工具适配器

当前注册中心位于 `app/adapters/registry.py`。新增真实工具时建议：

1. 新建适配器类，例如 `AnsysAdapter`
2. 继承 `BaseCAEAdapter`
3. 实现以下方法：
   - `validate_params`
   - `prepare_workspace`
   - `build_command`
   - `parse_result`
4. 在 `registry.py` 中注册该工具名

安全约束建议保持不变：

- 前端只传 `tool` 和业务参数
- 可执行文件路径由服务端适配器内部决定
- 不允许前端直接传入任意 `exe` 路径

## Windows 兼容性说明

- 进程启动使用 `subprocess.Popen(..., shell=False)`
- 命令参数统一使用 `list[str]`
- 显式设置 `cwd`
- 取消任务时优先调用 `terminate()`，超时再 `kill()`
- `dummy_solver` 通过当前 Python 解释器调用，便于本地直接测试

## ANSA 说明

该版本增加了对 `BETA CAE Systems ANSA v24.1.3` 的最小适配，默认思路是：

- 服务端通过 `ANSA_EXECUTABLE` 定位本机安装的 ANSA
- 服务端通过 `ANSA_SCRIPT_FILE` 固定批处理脚本路径
- 前端只传 `tool=ansa` 与模型/脚本参数，不传 exe 路径和脚本路径
- 适配器通过 `-execpy` 构造批处理命令

由于不同现场环境中的 ANSA 启动参数可能存在差异，当前实现把变化点集中在：

- `app/adapters/ansa.py`
- `.env` 中的 `ANSA_EXECUTABLE`
- `.env` 中的 `ANSA_SCRIPT_FILE`
- `.env` 中的 `ANSA_EXECPY_PREFIX`
- `.env` 中的 `ANSA_BATCH_FLAGS`

如果你本机验证后发现 `-execpy` 或批处理参数与现场安装不一致，只需要改 `AnsaAdapter.build_command()` 这一处。

你机器上的 ANSA 实际启动命令示例：

假设 `.env` 中是下面这组配置：

```env
ANSA_EXECUTABLE=C:\Program Files\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.bat
ANSA_SCRIPT_FILE=C:\scripts\run_ansa.py
ANSA_EXECPY_PREFIX=load_script:
ANSA_BATCH_FLAGS=-b
```

并且你提交的任务参数是：

```json
{
  "input_file": "C:\\models\\demo.ansa",
  "script_args": ["--deck", "NASTRAN"],
  "extra_args": ["-mesa"],
  "no_gui": true
}
```

那么服务端最终构造出来的命令大致是：

```powershell
& "C:\Program Files\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.bat" `
  -b `
  -execpy "load_script:C:\scripts\run_ansa.py C:\models\demo.ansa --deck NASTRAN" `
  -mesa
```

如果你现场实际命令不是这样，优先检查这三项：

- `ANSA_EXECUTABLE` 是否指向了正确的 `ansa64.bat` 或 `ansa64.exe`
- `ANSA_SCRIPT_FILE` 是否指向了正确的 `run_ansa.py`
- `ANSA_EXECPY_PREFIX` 是否确实应该是 `load_script:`
- `ANSA_BATCH_FLAGS` 是否应该是 `-b`，还是你们现场还有别的批处理参数
