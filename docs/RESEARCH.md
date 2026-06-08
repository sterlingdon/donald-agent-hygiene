# 调研：现有 MCP / skills / hooks / memory 管理工具全景

> 调研时间 2026-06。✅=已确认真实仓库/官方文档；⚠️=来自 AI 摘要、需再核实。

## 1. 背景数据（为什么要做）

- 全开 MCP：空对话就吃掉 **82k token（41%）**，仅剩 5% 可用（Scott Spence 实测）。
- ~20 个本地 MCP 进程：上下文 **5 个 prompt 内打满**，会话不可用（claude-code issue #3036）。
- 7+ 个 MCP server：开干前预占 **~67k token**（Anthropic Tool Search 说明）。
- MCP vs CLI token（Scalekit）：简单查询 1,365 vs 44,026（**32×**）；复杂 5,010 vs 33,712（**7×**）。
- GitHub 官方 MCP 工具定义单次就 **17,600 token**（StackOne）。
- Skills 渐进式：元数据 ~50–100 token/个，100 个 skill ≈ 5–10k token；描述预算=上下文 1%，溢出先丢最少用 skill 的描述（`/doctor` 可查）。

## 2. 现有工具（按维度）

### MCP 开关 / 管理 / 网关
| 工具 | 形态 | 做什么 | 局限 |
|---|---|---|---|
| **McPick**（`npx mcpick`）✅ | CLI | 会话前勾选启用哪些 MCP，自动备份改写 `.claude.json` | 纯手动，不分析用量 |
| **qdhenry/Claude-Code-MCP-Manager** ✅ | bash+jq | 增删列、批量开关、预设组合，配置在 `~/.config/claude/mcp_config.json` | 不审计、不看 token |
| **metatool-ai/MetaMCP** ✅ | Docker 网关 | 把 N 个 MCP 聚合成 1 个端点，命名空间挑工具 + 中间件 | 偏团队/重，要起服务 |
| Atlassian mcp-compressor / Speakeasy 动态 toolset ✅ | 技术方案 | 压 schema / 按需载入，降 90–96% | 非成品工具 |

### Skills 分发 / 市场
| 工具 | 做什么 | 局限 |
|---|---|---|
| 内置 `/plugins`、`/plugin marketplace add` ✅ | 官方市场安装/管理 | 不审计本机僵尸 skill |
| richfrem **Marketplace Manager** skill ✅ | 搭建/校验/分发 plugin 目录，可同步到 CC/Codex | 偏分发侧 |
| ⚠️ `npx skills` / agent-skills-cli | 跨工具批量装 skill | 待核实 |

### Hooks + CLAUDE.md / memory
| 工具 | 做什么 | 局限 |
|---|---|---|
| **alirezarezvani/ClaudeForge** ✅ | hooks（PreToolUse/PostToolUse/InstructionsLoaded/Stop）+ `audit-claude-md.py`：剪枯死引用、强制 150 行上限拆分、`/sync-claude-md --weekly` 并行跑漂移/断链/依赖三个审计子 agent（forked subagent，不污染主会话）；`claude-md-guardian` agent（haiku） | **只管 CLAUDE.md** |
| **zilliztech/memsearch** ✅ | markdown 记忆 + Milvus 索引，跨会话召回 | 是"记忆增强"非"清理" |

### 综合健康检查 / 上下文
| 工具 | 做什么 | 局限 |
|---|---|---|
| **davila7/claude-code-templates**（aitmpl.com）✅ | `--health-check` 校验配置查问题给建议；`--analytics` 读会话记录看 token/实时状态；`--plugins` 管 MCP/权限；`--skill <name>` 装 skill | **仅 CC**；不按使用率剪 skills；不碰 Codex |
| zilliztech/claude-context ✅ | 语义代码检索（省探索 token） | 单点 |
| mksglu/context-mode、rtk-ai/rtk、Mibayy/token-savior、JuliusBrussee/caveman、code-review-graph ✅ | 输出压缩/终端降噪/检索等各切一刀 | 单点 |

### 内置原语（直接复用，别重造）
- Claude Code：`/context`（占用分布）、`/doctor`（skill 预算溢出）、`claude mcp list`、`/mcp`、`settings.json`（`enabledMcpjsonServers` 等）。
- Codex：`codex mcp list / add / remove / show`、`~/.codex/config.toml`、`AGENTS.md`、`~/.codex/skills/<name>/SKILL.md`。⚠️ `codex skill list/remove` 待核实（先查 `codex --help`）。

## 3. 缺口（= 本 skill 的差异化）

**没有任何工具同时满足**：
1. **跨 CC + Codex**（现有几乎都只管 CC）；
2. **MCP + skills + hooks + memory 四维一体**（现有都只切一刀）；
3. **按真实使用率剪枝**——"装了 30 天没用过 → 建议卸载"这件事**没人系统做**。

> 关键 insight：用量数据一直存在，就在 `~/.claude/projects/**/*.jsonl` 会话记录里（每次工具调用 / skill 触发都有记录）。解析它即可统计真实使用频次。`claude-code-templates --analytics` 和 `ccusage` 都读这批文件，可参考其解析方式。

## 4. 数据源 / 内部路径备忘

| 对象 | Claude Code | Codex |
|---|---|---|
| MCP 配置 | `~/.claude.json`（mcpServers）、项目 `.mcp.json` | `~/.codex/config.toml`（`[mcp_servers.*]`） |
| skills | `~/.claude/skills/`、项目 `.claude/skills/`、plugin | `~/.codex/skills/<name>/SKILL.md` |
| hooks | `settings.json` / `settings.local.json` | `config.toml`（hooks）、`AGENTS.md` |
| memory/指令 | `CLAUDE.md`（各级）、memory store | `AGENTS.md` |
| 用量记录 | `~/.claude/projects/**/*.jsonl` | `~/.codex/`（待核实具体路径） |

## 5. 主要来源
- Anthropic《Advanced tool use》/ Tool Search；Claude Code 官方 Skills 文档
- Scott Spence《Optimising MCP Server Context Usage in Claude Code》+ McPick
- claude-code GitHub issue #3036
- Shareuhack《Best MCP Servers 2026》；Scalekit / StackOne token 基准
- Milvus《7 Best Open-Source Tools for Claude Code Context Management》
- GitHub：qdhenry/Claude-Code-MCP-Manager、metatool-ai/metamcp、alirezarezvani/claudeforge、davila7/claude-code-templates、zilliztech/memsearch、zilliztech/claude-context
- OpenAI 社区《Sync Codex and Claude Code configs: skills, agents, MCP, permissions》
