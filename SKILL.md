---
name: donald-agent-hygiene
description: 体检并清理 Claude Code 与 Codex 的本机配置健康度——盘点已安装的 MCP / skills / hooks / memory，按真实使用频次找出"装了从不用"的僵尸项与吃上下文的大户，分 🟢可直接禁用 / 🟡需人工判断 / 🔴谨慎 三级给出可执行处置（禁用/卸载/归档，自动备份）。当用户说"体检/清理/优化我的 claude code（或 codex）配置""哪些 mcp/skill 装了没用""我的 agent 是不是太臃肿了""上下文被 mcp 吃光了""保持系统健康/精简"时触发。全程默认只读扫描，处置需显式确认。
---

# donald-agent-hygiene · Agent 配置健康体检与瘦身

> ✅ **状态：M1 已实现**（只读体检 → 交互式 HTML 报告，覆盖 CC+Codex 的 skills/MCP，含 plugin 自带项；安全处置器 dry-run 默认 + 备份）。45 个测试全绿，已对真机做过只读冒烟（配置零改动）。

## 使用

```bash
# 只读体检 → 交互式 HTML 报告（绝不改任何配置）
scripts/run_hygiene.sh /tmp/agent-hygiene-report.html
# 或直接：
cd scripts && python -m hygiene.cli scan \
  --home "$HOME" --codex-home "$HOME/.codex" \
  --projects "$HOME/.claude/projects" --sessions "$HOME/.codex/sessions" \
  --cwd "$PWD" --out /tmp/agent-hygiene-report.html

# 跑测试（必须在 scripts/ 目录下）
cd scripts && python -m pytest -q
```

报告按 🟢可直接清理 / 🟡需人工判断 / 🔴谨慎 / ✅保留 分级，每行附可一键复制的处置命令。
真正执行清理（禁用/归档/卸载）由 `hygiene.actions` 提供，**默认 dry-run，改写前自动备份**到 `~/.agent-hygiene-backups/`。

## 一句话

把 Claude Code / Codex 当作需要定期体检的系统：**盘点 → 按用量打分 → 分级 → 处置**，清掉"装了不用"的 MCP / skills / hooks / memory，让宿主时刻处于最健康（低上下文占用、启动快、工具选择准）的状态。

## 为什么需要它

我们会在不知不觉中装一堆 MCP 和 skills，其中很多**装了又不用**：
- MCP 启动即把全部工具 schema 注入上下文 → 装得越多，开局越慢、可用 token 越少、工具选错率越高（实测：全开可吃掉 41% 上下文，~20 个 MCP 进程 5 个 prompt 就打满）。
- skills 虽便宜（元数据 ~50–100 token/个），但描述预算溢出时会丢关键词、降低触发准确率。
- hooks / memory 日积月累也会变脏（枯死引用、超长 CLAUDE.md）。

市面工具都只切一刀（见 `docs/RESEARCH.md`）。本 skill 的差异化 = **跨 CC+Codex + 四维一体 + 用量驱动剪枝 + 分级可执行处置**。

## 工作流（拟）

1. **Inventory 盘点**：枚举 MCP（`.claude.json` / `~/.codex/config.toml`）、skills（`~/.claude/skills`、`.claude/skills`、`~/.codex/skills`）、hooks（settings.json）、memory（CLAUDE.md / AGENTS.md / memory store）。
2. **Usage 用量扫描**：解析会话记录 `~/.claude/projects/**/*.jsonl`，统计每个 skill / MCP 工具最近 N 天真实调用次数。
3. **Cost 成本估算**：估每项的上下文 token 占用（调内置 `/context`、`claude mcp list`、`/doctor` 做交叉验证）。
4. **Score 打分**：成本 ÷ 使用频次 → 性价比 → 标记僵尸项。
5. **三级分类**：🟢可直接禁用 / 🟡需人工判断 / 🔴谨慎处理。
6. **处置**：给可一键执行的禁用/卸载/归档命令；**改写前自动备份**（借鉴 McPick 的 `.claude.json` 安全改写）。

## 设计红线（拟）

- **默认只读**：扫描阶段绝不改任何配置。
- **处置需显式确认**，且每次改写前备份原文件。
- **复用而非重造**：能调 `/context`、`/doctor`、`claude mcp list`、`claude-code-templates --health-check`、`ClaudeForge` 的就调，自己只补"用量统计 + 跨工具统一视图 + 分级处置"这块缺口。

## 目录

- `docs/RESEARCH.md` — 现有开源工具全景 + 缺口分析（本次调研结论）
- `docs/DESIGN.md` — 架构、阶段拆解、**三个待拍板的开放决策**、路线图
- `scripts/hygiene/` — 已实现：`collect_cc`/`collect_codex`(inventory)、`usage_cc`/`usage_codex`(用量解析)、`cost`(成本)、`classify`(分级)、`report`(HTML)、`actions`(安全处置)、`cli`(编排)
- `scripts/run_hygiene.sh` — 一键只读体检
- `scripts/tests/` — pytest 用例（45 个）
