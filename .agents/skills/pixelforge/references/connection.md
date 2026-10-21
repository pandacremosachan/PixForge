# 连接与 harness 接入

本文件描述与宿主无关的契约。必需能力只有“读取本 skill 文件”以及“执行进程或连接 MCP”中的至少一项。对话、文件写入、图像查看和批准由当前 harness 提供，不要求固定工具名或厂商 API。宿主不自动发现 SKILL.md 时，显式加载它和任务对应的参考即可；不必更改其全局提示或目录结构。

## 选择传输

| 当前 harness 能力 | 连接 |
|---|---|
| 能运行进程 | 软件 EXE 的 `--cli`；可用标准库客户端统一发现、错误和参数 |
| 能连接 MCP stdio | 直接配置软件 EXE 的 `--mcp`；客户端与 Python 均为可选 |
| 能运行 Python 3.10+ | 可使用客户端的 `Client` 类执行流程示例，只有标准库依赖 |
| 代理与软件不在同一系统 | 使用用户已有的进程转发器或 MCP 桥；路径与文件传输按下节处理 |
| 只有文本对话 | 交付可执行脚本/配置和具体命令，由用户执行；不能声称已操作工作台 |

PixForge 拥有自己的运行环境。skill 不安装 Pillow、MCP SDK、GUI 库或软件包，不调用 `backend/python.exe`，不读取/修改内部 `state.json`、恢复稿或令牌账本。客户端仅通过公开 EXE 入口调用。

## CLI 与外部配置

下列命令中的 `<skill-dir>` 取本 SKILL.md 所在目录的真实位置，不固定为 `.agents`、`.codex` 或用户主目录。`python` 表示当前 harness 已有的 Python 3.10+ 命令，也可换成其绝对路径。

```text
python <skill-dir>/scripts/pixforge_client.py --app <软件目录或EXE> doctor
python <skill-dir>/scripts/pixforge_client.py --app <软件目录或EXE> session --workspace <W> --runtime <R> status
```

连接优先级为 `--app`、`--config`、`PIXFORGE_APP`、`PIXFORGE_CONNECTION`、PATH 中的原生启动器，最后才是同级便携目录和本机安装目录。显式连接错误立即失败，不悄悄改连别的工作台。连接配置保存在 skill 目录之外；相对 application 路径以配置文件为基准。

```json
{"application":"../PixForge-Cpp/PixForgeNative.exe"}
```

已有兼容启动器或进程转发器可使用参数数组，客户端将 `--describe` / `--cli` / `--mcp` 追加到末尾，不经 shell 解释：

```json
{"command":["/absolute/path/to/pixforge-launcher"]}
```

`command` 和 `application` 二选一。command 首项含相对路径分隔符时相对配置文件解析；其余参数原样转发，路径参数使用绝对路径。启动器必须保留退出码及 stdin/stdout/stderr，`--describe` 只输出描述 JSON，MCP stdout 只输出协议。不要把 shell 管道、`&&` 或凭据拼进单一字符串。

本文其余参考中的 `pixelforge …` 是 `python <skill-dir>/scripts/pixforge_client.py [--app … 或 --config …] …` 的简写，并非要求 PATH 存在同名命令。客户端连接选项放在软件命令前；`session minecraft-configure --config target.json` 的 config 属于目标配置。

## MCP

以下对象是跨宿主通用的进程描述，将 command/args 字段填入宿主自己的 MCP 配置位置；不假定宿主配置顶层叫 `mcpServers`：

```json
{
  "command":"C:/Tools/PixForge/PixForgeNative.exe",
  "args":["--mcp","--workspace","C:/Project","--runtime","C:/Project/.runtime/pixforge"]
}
```

也可用已有 Python 启动 skill 客户端，args 为 `["<skill-dir>/scripts/pixforge_client.py","--app","<EXE>","mcp","--workspace","<W>","--runtime","<R>"]`。直接 EXE 模式不依赖 Python 或 skill 的安装路径。

按 MCP 标准初始化、取得工具列表、调用 `info`。这里的工具名指服务端名称；宿主加的命名空间前缀以实际连接为准，不能写死 `mcp__某宿主__`。返回值的 text content 是 JSON，image content 是 PNG；`isError=true` 时先处理错误，不把外层 HTTP/MCP 成功当作操作成功。详细映射见 [操作约定](operations.md)。

## 操作系统和远端

skill 的 Markdown、JSON 模板和标准库客户端可移动；当前桌面发行包为 Windows x64，不能将其直接当成 Linux/macOS 原生软件。Linux、macOS、WSL 或容器中的 harness 可连接已部署的兼容软件启动器/stdio 桥。此处不自动安装跨系统运行时或建立远程服务。

远端 EXE 后的 `workspace`、`runtime`、PNG/模型、脚本输入和预览路径都是**软件端路径**。代理本机不能读到这些文件时，使用用户已有的文件通道；纯绘图文字可经 stdin / MCP `draw.commands` 发送。Python `Client` 的 workspace/runtime 解析面向同机调用，远端优先用原始 CLI 或 MCP，并显式提供软件端绝对路径。不要把本机路径送给远端后将文件不存在误判为功能缺失。

公开 loopback JSON 仅供软件所在主机使用，需软件发布的会话认证；不要开放为未认证的远程端口，不记录令牌。多数 harness 直接使用 CLI/MCP 即可。

## 兼容性和更新

`doctor` 实际调用 `--describe`，核对 `pixforge.application/v1`、API 主版本和接口。若使用本地 EXE，同时核对相邻 `application.json`。API 主版本不兼容时停止；可选能力缺少时只影响对应流程，不导入内部模块补齐。

本版完整流程以软件 2.9.0 为基线，沿用 API 主版本 1。MCP 工具集和 CLI 可用选项仍以该安装为准；文档已给出基线命令，只有版本不符、缺项或报错时才查看 help。普通 Minecraft 资源适配需 `minecraft-assets/v1`；数据、预览与运行时代码分别需要对应能力。

软件与 skill 分开更新。替换 skill 不停止软件、不修改工程。Windows 替换软件前保存当前作品、关闭窗口和连接，用当前令牌调用公开 `session shutdown`，再替换程序文件；保留用户 workspace/runtime 和外部工程。完整保留软件目录的 backend 与 application.json。软件自身不读取 skill；`agents/openai.yaml` 只是可选宿主 UI 元数据。
