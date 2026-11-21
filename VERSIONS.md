# Versions / 版本清单

v5 is current. It adds `skill/skeleton_v5/` and reuses the v4 runtime and adapters unchanged. Older docs and demo pages were removed; they remain in the Git history.
当前是 v5。它新增 `skill/skeleton_v5/`，原样复用 v4 骨架和适配器。旧文档和旧网页已删除，在 Git 历史里仍可找回。

## v5 files / v5 文件

| Purpose / 用途 | File / 文件 |
|---|---|
| Owner's rules / 规则 | `skill/skeleton_v5/rules_v5.json` |
| Access layer / 接入层 | `skill/skeleton_v5/connectors.py`, `connectors_v5.json` |
| News check / 新闻核查 | `skill/skeleton_v5/news.py`, `news_v5.json` |
| Permission growth / 权限进化 | `skill/skeleton_v5/permissions.py` |
| Plug-ins and adapters / 插件与适配器 | `skill/skeleton_v5/plugins_v5.py`, `adapters_v5.py` |
| Dry-run morning / 演练 | `skill/skeleton_v5/run.py` |
| Demo / 演示 | `demo/skeleton-v5.html` (data: `skill/skeleton_v5/simulate.py` → `demo/data/skeleton-v5.js`) |
| Spec / 规格 | `.kiro/specs/incident-skeleton-v5/` |
| Tests / 测试 | `skill/tests/test_skeleton_v5.py` |

## v4 files / v4 文件

| Purpose / 用途 | File / 文件 |
|---|---|
| Judge entry / 评委入口 | `demo/guide-v4.html` |
| Demo / 演示 | `demo/skeleton-v4.html` |
| Live demos / 运维演示 | `demo/console.html`, `demo/servicenow.html` |
| Shared runtime / 共用骨架 | `skill/skeleton_v4/skeleton.py` |
| Code / 代码 | `skill/skeleton_v4/` |
| Spec / 规格 | `.kiro/specs/incident-skeleton-v4/` |
| Core invariants / 基础不变量 | `SPEC.md` |
| Steering / 规则 | `.kiro/steering/incident-skeleton.md` |
| Hooks / 钩子 | `.kiro/hooks/` |
| Agents / 代理 | `.kiro/agents/`, run record `docs/agent-run-v4.md` |
| Kiro power | `power-incident-skeleton/` |
| Skill / 技能说明 | `skill/SKILL.md` |
| Submission / 提交 | `DEVPOST-v4.md` |
| Wrap-up note / 收尾说明 | `docs/v4-收尾说明.md` |
| Recording script / 录屏脚本 | `docs/提交清单.md` |

## Libraries v4 calls / v4 调用的代码库

| Folder / 目录 | Job / 作用 |
|---|---|
| `skill/remediation/` | repair loop, tickets, case library, notify / 修复循环、工单、病例库、通知 |
| `skill/apps/servicedesk/` | service desk checks and catalogue / 服务台检查与动作目录 |
| `skill/scripts/` | read-only probes / 只读探测 |
| `skill/evolution_v2/` | method lifecycle and versions / 方法生命周期与版本 |
| `skill/external_intelligence_v3/` | vendor outage correlation / 厂商故障关联判断 |
| `skill/integration_v31/` | outage gate and held-action map / 故障闸门与暂停动作映射 |
| `skill/mcp/` | incident KB MCP server / 事件知识库 MCP 服务 |

These folders are libraries, not separate skeletons. The six steps live only in `skeleton.py`.
这些目录是共用库，不是另外的骨架。六步流程只在 `skeleton.py` 里。
