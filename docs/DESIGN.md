# 设计：donald-agent-hygiene

> 状态：设计阶段。下面的「开放决策」需用户拍板后才进入实现。

## 1. 目标

让 Claude Code / Codex 时刻处于最健康状态：低上下文占用、启动快、工具选择准。手段是定期体检 + 用量驱动地清掉"装了不用"的 MCP / skills / hooks / memory。

## 2. 架构（六阶段管线）

```
Inventory ─► Usage ─► Cost ─► Score ─► Classify ─► Treat
盘点已装    真实用量   token估算  性价比    🟢🟡🔴      处置(备份)
```

1. **Inventory**：枚举四类对象（路径见 RESEARCH.md §4），统一成内部清单 schema。
2. **Usage**：解析 `~/.claude/projects/**/*.jsonl`，按 skill 名 / MCP 工具名聚合最近 N 天调用次数、最后一次使用时间。
3. **Cost**：估每项上下文 token（MCP 调 `claude mcp list` / 估 schema；skill 取 description 字符数；交叉验证用 `/context`、`/doctor`）。
4. **Score**：`成本 / max(用量,ε)` → 排序；近 N 天 0 次 = 僵尸候选。
5. **Classify**：
   - 🟢 可直接禁用：0 调用 + 非关键 + 高 token。
   - 🟡 需人工判断：低频但可能重要 / 安全相关。
   - 🔴 谨慎：核心依赖、写权限、官方安全工具。
6. **Treat**：输出可执行处置（禁用 / 卸载 / 归档），**改写前自动备份**。

## 3. 复用 vs 自研

| 能力 | 复用现有 | 自研核心 |
|---|---|---|
| MCP 安全开关/备份 | 借鉴 McPick 改 `.claude.json` | — |
| CLAUDE.md/memory 审计 | 借鉴 ClaudeForge 的 hooks+audit 脚本 | — |
| 配置校验 + token 看板 | 调 `claude-code-templates --health-check/--analytics` | — |
| 上下文占用 | 调 `/context`、`/doctor`、`claude mcp list` | — |
| **用量统计（剪枝）** | 无人做 | ⭐ 解析 jsonl 算调用频次 |
| **跨 CC+Codex 统一** | 无人做 | ⭐ 统一 inventory + 处置层 |
| **分级 + 一键处置** | 参考自家 storage-analyzer 范式 | ⭐ |

## 4. 已定决策（2026-06 用户拍板）✓

1. **覆盖范围**：✅ **CC + Codex 都要**。Codex 的用量记录路径 / skill 机制较新，列入「待核实事项」先验证。
2. **输出形态**：✅ **交互式 HTML 报告**（对齐 storage-analyzer：可折叠分级、命令一键复制、可起本地服务执行）。
3. **处置权限**：✅ **直接可执行**，但硬性前置：每次改写前自动备份 + 改动需显式确认。

## 5. 路线图（按已定决策）

- **M1 只读体检（CC+Codex）**：Inventory + Usage + Cost + 打分分级 → 交互式 HTML 报告。**全程只读、不改任何配置**。先交付价值、验证用量数据可用性。
- **M2 处置层**：备份机制 + 显式确认 + 一键禁用/卸载/归档（HTML 报告内起本地服务执行，或导出命令）。
- **M3 周期巡检**：可选 SessionStart hook / 定时，定期产报告提醒。

> 即使最终要"可执行"，仍建议 M1 先把"只读体检 + HTML 报告"跑通——它本身就有完整价值，且能在零风险前提下验证「用量解析」「跨工具 inventory」这两块自研核心。

## 6. 可行性验证（2026-06 本机实测）✓

**Claude Code — 完全可行：**
- 用量记录：`~/.claude/projects/**/*.jsonl`（本机 144 个会话文件）。
- skill 调用：`tool_use.name == "Skill"` → `.input.skill` 即 skill 名，可直接聚合排名。
- MCP 调用：`tool_use.name` 形如 `mcp__<server>__<tool>`，可按 server/tool 聚合。
- 内置工具（Bash/Write/Read…）同样以 `.name` 出现。
- **样本结论**：本机装了 **49 个 skill**，历史上真正被调用过的仅 **~28 个** → 约 **21 个"从未使用"僵尸候选**；`~/.claude.json` 里配了 `Framelink Figma MCP` 但历史 **0 调用** → 僵尸 MCP。差异化逻辑当场成立。

**Codex — 可行，布局不同：**
- 用量记录：`~/.codex/history.jsonl`、`session_index.jsonl`、`sessions/`（字段待抽样确认）。
- MCP 配置：`~/.codex/config.toml` 的 `[mcp_servers.*]`（本机有 `node_repl`）。
- skills：`~/.codex/skills/`（本机为空）；另有 `superpowers/`、`plugins/`、`vendor_imports/skills-curated-cache.json` 可能也是来源，需进一步确认实际安装位置。
- memory：`~/.codex/memories/`、`memory-archives/`、`AGENTS.md`、`rules/`。

**仍待核实：**
- Codex `history.jsonl` / `sessions/` 中工具与 skill 调用的精确字段。
- Codex skills 的全部真实来源目录（`skills/` 空，实际装在哪）。
- `codex --help` 是否提供 skill 列表/删除子命令。

---

## 附录 A：已验证的 Claude Code 用量提取配方（可直接用）

```bash
# 历史上真正被调用过的 skill 排名
find ~/.claude/projects -name '*.jsonl' -print0 | xargs -0 cat \
 | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Skill") | .input.skill' \
 | sort | uniq -c | sort -rn

# 历史上真正被调用过的 MCP 工具排名
find ~/.claude/projects -name '*.jsonl' -print0 | xargs -0 cat \
 | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and (.name|type=="string") and (.name|startswith("mcp__"))) | .name' \
 | sort | uniq -c | sort -rn

# 已安装 skill 清单（与上面求差集 = 僵尸 skill）
ls -1 ~/.claude/skills
```

> 时间窗口：用文件 mtime 或记录内时间戳过滤"最近 N 天"，即可区分"近期没用"和"从未用过"。
