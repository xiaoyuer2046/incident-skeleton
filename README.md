# 💀 Incident Skeleton

> Kiroween 2026 · **Skeleton Crew** · v5 · English / 中文 · MIT

**One shared six-step runtime. Two very different apps. Three plug-in slots. An AI that learns from vendors first.**

> **v5** keeps `skeleton.py` unchanged and adds an access layer for five managed systems, a news check that warns of a *likely* vendor outage before the vendor says so, and permission growth that a person approves. See [v5 below](#v5-connect-warn-early-grow-with-approval).

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG      skill/skeleton_v4/skeleton.py (102 lines)
            ▲          crew          crew       ▲           ▲
       triage_gate                        mitigate_rank   log_learn
```

| | App 1 · office devices | App 2 · service desk L1 |
|---|---|---|
| Who reports | machines (a patrol probes them) | people (Teams, email, portal) |
| Crews | printer · signage · meeting-room AV · Wi-Fi AP | account · VPN · email · software |
| App code | `skill/skeleton_v4/app_devices.py` | `skill/skeleton_v4/app_servicedesk.py` |

Both adapters call the same `skeleton.run()`. A third app is one more adapter; `test_skeleton_v4.py` proves it with a tiny third app that leaves `skeleton.py` unchanged.

## Start here (5 minutes)

1. Open **`demo/guide-v4.html`**: the product guide (EN / 中文, Day / Night / Auto).
2. Open **`demo/skeleton-v4.html`**: both apps running through the one runtime, step by step.
3. Read the four files below. You can ignore the rest of `skill/` on a first look.

| Read | File | Lines | What you will see |
|---|---|---|---|
| 1 | `skill/skeleton_v4/skeleton.py` | 102 | the whole skeleton: six fixed steps, three slots, nothing app-specific |
| 2 | `skill/skeleton_v4/app_devices.py` | 100 | App 1 as an adapter |
| 3 | `skill/skeleton_v4/app_servicedesk.py` | 181 | App 2 as an adapter |
| 4 | `skill/skeleton_v4/plugins.py` | 128 | the three plug-ins that fill the slots |

No install. Double-click the HTML files.

**What is independent, and what is shared.** `skeleton.py` imports nothing from either app or from the older code. The two adapters do call a shared repair library (`skill/remediation/`: repair loop, tickets, case library, notifications) that came from v1. That library is a set of parts both apps reuse; it does not contain the six steps.

## The Teams story

Many staff cannot sign in to Teams, and a meeting room's Teams Rooms cannot join. The `triage_gate` slot checks vendor health before any local fix. Microsoft has an incident, so **both apps link to one Microsoft parent ticket**, and password resets and Office reinstalls are held. A one-floor Wi-Fi fault with Cisco healthy stays local.

## The AI learns first

| Order | Source | Rule |
|---|---|---|
| A | vendor MCP (Microsoft, Cisco) and official status | read first, weighs most |
| B | company KB, tickets, chat, email | read second |
| C | trusted web | needs backing from A or B |
| D | public reports | needs backing; never promotes or demotes |

Text that gives orders is blocked. A vendor advisory that calls a fix harmful pauses it. **In v4, learning can only narrow permission.** `policy.json` is the only permission source. v5 adds one way up, and only a person can take it (below).

## v5: connect, warn early, grow with approval

`python skill/skeleton_v5/run.py --lang en` (or `--lang zh`) runs one simulated morning. Nothing is sent.

| Part | What it does | File |
|---|---|---|
| Access layer | ServiceNow, AP controller, meeting-room manager, signage CMS, print manager as connectors with scopes. A new system is one JSON entry. Secrets are named, never read. A system that does not answer is skipped and the admin is told. | `skill/skeleton_v5/connectors.py`, `connectors_v5.json` |
| Merge | Items about the same service in two or more systems, or the same device, become one parent. | `connectors.py` |
| News check | 3+ independent sites reporting the same outage = **likely vendor outage**, even with no official word. One vote per site, reposts once, old reports ignored, text that gives orders dropped. Official status = confirmed. | `skill/skeleton_v5/news.py` |
| Tell people | On "likely", affected people get the sources at once. Local work continues. | `run.py` |
| Permission growth | After enough confirmed successes, learning **proposes** a standing approval for one action, crew and symptom. Only a listed approver grants it; it expires in 30 days and can be revoked. Identity and on-site actions are refused by rule. No permission file is written. | `skill/skeleton_v5/permissions.py` |
| Meeting window | A room in a meeting that still works: risky steps wait until it ends. | `plugins_v5.py`, `adapters_v5.py` |
| Numbers | Merged items, minutes warned before the official notice, work done by AI, useless fixes held, an estimate of minutes saved. | `run.py` |

In the simulated morning: four independent sites report Teams sign-in failing at 09:05, five minutes before Microsoft's status page. Three items from two systems merge into one parent. A full mailbox waits for approval; after a person approves the standing grant, the next one is fixed alone. Rules live in `skill/skeleton_v5/rules_v5.json`; the spec is `.kiro/specs/incident-skeleton-v5/`.

## Built with Kiro

| Kiro feature | Where | Evidence |
|---|---|---|
| Spec | `.kiro/specs/incident-skeleton-v4/` (requirements, design, tasks) | the v4 code and tests follow it |
| Steering | `.kiro/steering/incident-skeleton.md` | loaded by every agent in `.kiro/agents/` |
| Agents (Kiro Crew) | `.kiro/agents/`: a crew lead and five crews | **ran**: `docs/agent-run-v4.md` records the crew lead handing a fault to `wifiap-crew` |
| MCP | `skill/mcp/incident_kb_server.py` | **ran**: both agents in that record called it |
| Scheduled job | Kiro Crew cron, every 10 minutes | **ran** on the build machine (dry-run patrol) |
| Hooks | `.kiro/hooks/` (tests on save, postmortem audit, permission guard) | **ran** in Kiro IDE 1.5.11: tests on save and postmortem audit fired on an agent file save (`docs/evidence/kiro-ide-hooks-triggered.png`); permission guard not yet shown firing |
| Power | `power-incident-skeleton/` | **ran** in Kiro IDE 1.5.11: imported from a folder, `incident-kb` connected with 5 tools, and a dry-run chat called `recall_fix` (`docs/evidence/kiro-ide-mcp-connected.png`, `docs/evidence/kiro-ide-power-dryrun-chat.png`) |

## How the code fits

| Part | Path | Job |
|---|---|---|
| Runtime | `skill/skeleton_v4/skeleton.py` | the six steps and three slots, nothing else |
| Adapters | `skill/skeleton_v4/app_*.py` | intake, crew choice, INVESTIGATE, MITIGATE |
| Plug-ins | `skill/skeleton_v4/plugins.py`, `learning.py` | outage gate, ranking, learning |
| Shared repair library | `skill/remediation/`, `skill/apps/servicedesk/`, `skill/scripts/` | repair loop, tickets, case library, notify, read-only probes (from v1, called by both adapters) |
| Engines the plug-ins reuse | `skill/evolution_v2/`, `skill/external_intelligence_v3/`, `skill/integration_v31/` | method versions, vendor outage correlation, held-action map |
| MCP server | `skill/mcp/` | the incident KB the agents query |

Only `skeleton.py` holds the six steps. Every other folder is a library it reaches through an adapter or a plug-in.

## Run it

macOS / Linux:

```bash
python3 skill/skeleton_v4/run.py --lang en          # one dry-run cycle of both apps
python3 skill/skeleton_v5/run.py --lang en          # v5: access layer, news check, permission growth
python3 skill/skeleton_v4/simulate.py               # regenerate demo/data/skeleton-v4.js
for f in skill/tests/test_*.py; do python3 "$f"; done
```

Windows (PowerShell):

```powershell
$env:PYTHONIOENCODING = "utf-8"
python skill\skeleton_v4\run.py --lang en
python skill\skeleton_v5\run.py --lang en
python skill\skeleton_v4\simulate.py
Get-ChildItem skill\tests\test_*.py | ForEach-Object { python $_.FullName }
```

| On Windows | Change |
|---|---|
| Agents (`.kiro/agents/`) | run `python skill\agents\build_agents.py --install`; it writes your own Python path into the installed agents |
| Hooks (`.kiro/hooks/*.json`) | nothing: each command tries `python3`, then `python` |
| Power (`power-incident-skeleton/mcp.json`) | in a copy of the folder, set `command` to your `python.exe` and replace `${INCIDENT_SKELETON_HOME}` with the repo's absolute path, then import that copy |

## Honest status

Everything is a **dry run on simulated data**. No Microsoft tenant, Cisco account or live internet connector is signed in. ServiceNow, Teams and mail connectors are written but not run against real systems. No dry-run result is a real repair.

## Versions

v4.1 is the only version kept. [VERSIONS.md](VERSIONS.md) lists every file and the libraries v4 calls. Older docs and pages are in the Git history.
