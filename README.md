# 💀 Incident Skeleton

> Kiroween 2026 · **Skeleton Crew** · v4.1 · English / 中文 · MIT

**One shared six-step runtime. Two very different apps. Three plug-in slots. An AI that learns from vendors first.**

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
3. Read **`skill/skeleton_v4/skeleton.py`**: the whole skeleton fits on one screen.

No install. Double-click the HTML files.

## The Teams story

Many staff cannot sign in to Teams, and a meeting room's Teams Rooms cannot join. The `triage_gate` slot checks vendor health before any local fix. Microsoft has an incident, so **both apps link to one Microsoft parent ticket**, and password resets and Office reinstalls are held. A one-floor Wi-Fi fault with Cisco healthy stays local.

## The AI learns first

| Order | Source | Rule |
|---|---|---|
| A | vendor MCP (Microsoft, Cisco) and official status | read first, weighs most |
| B | company KB, tickets, chat, email | read second |
| C | trusted web | needs backing from A or B |
| D | public reports | needs backing; never promotes or demotes |

Text that gives orders is blocked. A vendor advisory that calls a fix harmful pauses it. **Learning can only narrow permission, never widen it.** `policy.json` is the only permission source.

## Built with Kiro

| Kiro feature | Where |
|---|---|
| Spec | `.kiro/specs/incident-skeleton-v4/` (requirements, design, tasks) |
| Steering | `.kiro/steering/incident-skeleton.md` |
| Hooks | `.kiro/hooks/` (tests on save, postmortem audit, permission guard) |
| Agents (Kiro Crew) | `.kiro/agents/`: a crew lead and five crews; a real run is in `docs/agent-run-v4.md` |
| MCP | `skill/mcp/incident_kb_server.py` |
| Power | `power-incident-skeleton/` |

## How the code fits

| Part | Path | Job |
|---|---|---|
| Runtime | `skill/skeleton_v4/skeleton.py` | the six steps and three slots, nothing else |
| Adapters | `skill/skeleton_v4/app_*.py` | intake, crew choice, INVESTIGATE, MITIGATE |
| Plug-ins | `skill/skeleton_v4/plugins.py`, `learning.py` | outage gate, ranking, learning |
| Shared repair library | `skill/remediation/` | repair loop, tickets, case library, notify (from v1, called by both adapters) |

## Run it

```bash
python3 skill/skeleton_v4/run.py --lang en          # one dry-run cycle of both apps
python3 skill/skeleton_v4/simulate.py               # regenerate demo/data/skeleton-v4.js
for f in skill/tests/test_*.py; do python3 "$f"; done
```

On Windows use `python`.

## Honest status

Everything is a **dry run on simulated data**. No Microsoft tenant, Cisco account or live internet connector is signed in. ServiceNow, Teams and mail connectors are written but not run against real systems. No dry-run result is a real repair.

## Versions

v4.1 is the only version kept. [VERSIONS.md](VERSIONS.md) lists every file and the libraries v4 calls. Older docs and pages are in the Git history.
