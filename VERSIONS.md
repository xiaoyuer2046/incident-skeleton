# Versions / 版本清单

v4.1 is the current and final version. Older versions stay unchanged as history.
v4.1 是当前最终版本。旧版本原样保留，作为历史。

## Current: v4.1 / 当前版本

| Purpose / 用途 | File / 文件 |
|---|---|
| Judge entry / 评委入口 | `demo/guide-v4.html` |
| Demo / 演示 | `demo/skeleton-v4.html` |
| Shared runtime / 共用骨架 | `skill/skeleton_v4/skeleton.py` |
| Code / 代码 | `skill/skeleton_v4/` |
| Spec / 规格 | `.kiro/specs/incident-skeleton-v4/` |
| Steering / 规则 | `.kiro/steering/incident-skeleton.md` |
| Hooks / 钩子 | `.kiro/hooks/` |
| Agents / 代理 | `.kiro/agents/`, run record `docs/agent-run-v4.md` |
| Kiro power | `power-incident-skeleton/` |
| Submission / 提交 | `DEVPOST-v4.md` |
| Wrap-up note / 收尾说明 | `docs/v4-收尾说明.md` |
| Skill / 技能说明 | `skill/SKILL-v4.md` |
| Live demos still used by v4 / v4 仍在用的演示 | `demo/console.html`, `demo/servicenow.html` |

## History / 历史版本

| Version / 版本 | Files / 文件 |
|---|---|
| v1 | `SPEC.md` (invariants still hold), `archive/ROADMAP.md`, `archive/DEVPOST.md`, `archive/README-v1-v3.1.md`, `demo/guide.html`, `demo/index.html`, `skill/SKILL.md`, `docs/系统说明.md`, `docs/技术说明.md` |
| v2 | `archive/SPEC-v2-intelligence-evolution.md`, `archive/ROADMAP-v2.md`, `archive/DEVPOST-v2.md`, `demo/evolution-v2.html`, `skill/evolution_v2/`, `skill/SKILL-v2.md`, `docs/智能进化-v2.md` |
| v3 | `archive/SPEC-v3-global-intelligence.md`, `archive/ROADMAP-v3.md`, `archive/DEVPOST-v3.md`, `demo/global-intelligence-v3.html`, `skill/external_intelligence_v3/`, `skill/SKILL-v3.md`, `docs/全局故障情报-v3.md` |
| v3.1 | `archive/SPEC-v3.1-integrated-skeleton.md`, `archive/DEVPOST-v3.1.md`, `demo/guide-v3.1.html`, `demo/integrated-v31.html`, `skill/integration_v31/`, `skill/SKILL-v3.1.md`, `docs/骨架整合-v3.1.md` |

v4 still imports code from v1 (`skill/remediation/`, `skill/apps/servicedesk/`), v2 (`skill/evolution_v2/`), v3 (`skill/external_intelligence_v3/`) and v3.1 (`skill/integration_v31/`). Those folders are libraries, not separate skeletons.
v4 仍会导入 v1、v2、v3、v3.1 的代码目录。它们是共用库，不是另外的骨架。
