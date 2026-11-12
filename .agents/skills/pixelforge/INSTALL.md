# 安装 PixForge 技能（Windows）

解压发布包，将整个 `pixelforge` 文件夹放到下列位置之一。`SKILL.md` 和随包的 `runtime` 目录都留在这个文件夹内。

| 可用范围 | 放置后的技能目录 |
| --- | --- |
| 当前项目 | `<项目根目录>/.agents/skills/pixelforge/` |
| 当前用户的所有 Codex 项目 | `~/.codex/skills/pixelforge/`；自定义了 `CODEX_HOME` 时为 `<CODEX_HOME>/skills/pixelforge/` |

两个范围使用同一份文件。开发时也可以在对应位置放一个名为 `pixelforge` 的目录联接，指向维护中的技能文件夹。打开项目后，用 `$pixelforge` 调用。
