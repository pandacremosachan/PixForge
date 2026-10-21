# PixForge 软件维护边界

- 软件唯一实现位于本目录，包含界面、核心、工程与历史、CLI/MCP 和私有运行环境组装。不得依赖配套 skill 的文件、Python 模块或安装位置。
- `.agents/skills/pixelforge` 只保存外部客户端与使用指导。公开入口是软件 EXE 的 `--describe`、`--cli`、`--mcp`，兼容性以 `public_api_version` 判断。
- GUI 与公开接口共用同一工程及撤销历史。保留既有文件格式、版本冲突检查、恢复稿、确认与导出校验。
- 开发构建用同目录 `pixforge-development.json` 指定应用自己的私有核心；发行包使用相邻 `backend`。不得搜索 skill 目录启动软件。
- 软件与 skill 分别版本管理和打包；软件包不得包含 skill，skill 包不得包含软件实现或运行环境。用实际隔离安装验证配合及独立更新。
