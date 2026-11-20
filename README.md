# 💀 Incident Skeleton: one skeleton, four crews

> Kiroween 2026 · **Skeleton Crew** · built with Kiro (spec, skill, MCP, hook) · English / 中文

One incident-response **skeleton** (a six-state state machine) powers four device
**crews**: 🖨️ printer, 📺 digital signage, 🎥 meeting-room AV, 📶 wireless AP.
A *skeleton crew* is the minimum staff that keeps things running: the skeleton is the
shared state machine, the crews are the device-specific logic that plugs into it.

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
 shared    shared    crew          crew      shared    shared
```

Full documentation (Chinese): [系统说明](docs/系统说明.md) · [技术说明](docs/技术说明.md)

## What it does

1. **Patrol** four device types in parallel. One failed probe is a blip; only a fault
   that fails at least 2 of 3 probes is confirmed.
2. **Repair within permissions.** Candidate fixes come from built-in runbooks, ServiceNow KB
   articles, an optional AI advisor and the history of what worked here. Soft fixes first.
   What it may do alone is set in `skill/remediation/policy.json`.
3. **Learn.** Every attempt is recorded and verified. Success rates reorder the next attempt,
   a fix that keeps failing is demoted, a fix learned from KB/AI is only a candidate until it proves itself.
4. **Escalate.** If it cannot fix the fault, the alert says what was tried, what is left for a
   person and the likely cause, and a ServiceNow incident is opened for the right support group.

## What is real and what is simulated (read this first)

| Part | Status |
|---|---|
| Six-state skeleton, four crews, postmortems | real, runs today (ping / curl / SNMP, read-only) |
| Parallel patrol with a failure threshold | real |
| Permission policy, risk tiers, cooldown, audit log | real |
| Success-rate ranking, promotion and demotion | real, but statistics, not model training |
| Case-library harvest (KB, incidents, chat, email) | real logic on **sample source files**; live ServiceNow KB fetch is written but untested; Teams/Slack/WeChat/email connectors are not wired |
| Fix executors (controller API, CMS, MDM, PoE switch) | **not wired**: only `clear-queue` has a command. Live mode reports "no executor" and hands the step to a person |
| ServiceNow ticket + KB | payload, de-duplication and REST code are written; **not run against a real instance**. Default is dry run with a sample KB file |
| AI brain | interface, guardrails and tests are real; the demo uses a **mock stand-in**; real-model backends are written but untested |
| Demo page | simulated data, for the story |

## Safety and staying in touch

| Part | What it does | How to use it |
|---|---|---|
| Kill switch | pauses every automatic repair; tickets are still opened for people | `python3 skill/remediation/remediate.py --stop --by <name>`, undo with `--resume`, or `"kill_switch": true` in `policy.json` |
| Daily limit | at most `max_repairs_per_device_per_day` (6) repairs per device | `policy.json` |
| Delayed re-check | a fix counts only if the device is still healthy `recheck_minutes` (10) later; if the fault is back the fix is counted as a failure | automatic |
| Self-heal rule | a device that fails twice and then answers is not repaired and gives no credit to any fix | automatic |
| Notifications (`notify.py`) | outage, board news, failed repair, approval needed, fixed, fix did not hold, kill switch → Teams / Slack, each sent once | channels in `policy.json`; webhook URLs in `TEAMS_WEBHOOK_URL` / `SLACK_WEBHOOK_URL`; dry run writes `outbox.jsonl` |
| Scheduled patrol | runs every 10 minutes as a Kiro Crew command job (no AI cost), prints only new notifications | `python3 skill/scripts/patrol.py --remediate --quiet --lang zh` |

`skill/tests/test_safety.py` checks the kill switch, the daily limit, both re-check outcomes, the self-heal rule and that notifications are routed and not repeated.

## The AI brain (`skill/remediation/brain.py`)

One interface where an AI plugs in. The engine asks; the AI advises; the rules decide.

| Task | Used by | What the AI does |
|---|---|---|
| `suggest_actions` | repair loop | names known actions that fit the evidence (shown as 🧠 on the trace) |
| `map_fix_text` | case-library harvest | maps a free-text reply to a known action when keywords miss |
| `diagnose` | escalation | likely cause and next step, written on the ticket for the engineer |
| `summarize_outage_board` | outage board | one plain status line for everyone |

Guardrails enforced in code, whatever the AI says: only action ids from `actions.json` for that device; never changes the
policy (an AI pick still goes through allow-list, risk tier, approval and the physical-step rule); KB, chat, email and ticket text
is passed as data; JSON only, text capped; errors, timeouts or the call budget fall back to the rules; every call is audited
(no payload text); answers are cached. `skill/tests/test_brain_guardrails.py` checks these with a deliberately bad "AI".

Backends: `BRAIN=off` (default), `mock` (deterministic stand-in used by the demo, **not a model**), `claude` (local Claude Code CLI,
uses your Claude credits), `http` (OpenAI-compatible endpoint: `BRAIN_URL`, `BRAIN_MODEL`, key in `BRAIN_API_KEY`), `cmd`
(any command in `INCIDENT_AI_CMD`). The `claude` and `http` backends are written but **not tested** here.

## Mass outages: one shared status board

When many devices behind one switch fail together, the system opens ONE upstream ticket and then, every patrol,
**actively** checks ServiceNow for a master (major) incident and the mailbox for outage emails (`skill/remediation/watch.py`).
It links our ticket as a child of the master, keeps one timeline for everyone (patrol, ServiceNow notes, emails,
automation), tries any fix the master names within its permissions (physical steps go to engineers), posts our progress
back to the master, and closes the board only when the master is resolved **and** the patrol confirms the devices are
healthy. The board is the red card at the top of `demo/console.html` during the floor-4 outage (09:40-10:10).
Sources are sample files; the live ServiceNow and mailbox connectors are not wired.

## The autoplay demo (no clicks needed)

Open `demo/console.html`. It plays one simulated morning, 14 patrols from 09:00 to 11:10, by itself and loops.
Each patrol shows the fleet, **the faults of that patrol listed separately**, the repair trace, the case-library
harvest, learning, ServiceNow tickets, and a checklist of the 29 scenarios as they happen. EN / 中文 switch top right;
`?at=5` jumps to a patrol, `?speed=2` speeds it up.

`demo/servicenow.html` is a **simulated ServiceNow**: incident list, the incident form with its work notes,
"what automation did", related knowledge from the case library, the case library itself, and rejected sources.
Its time slider and **Replay** show the tickets as they were at any patrol.

How it is made: `python3 skill/remediation/simulate.py` scripts the *world* (which device fails, which fix would work,
when an engineer acts, who approves) and runs the *real engine* on it. The threshold, maintenance silence, blast-radius
grouping, harvest verdicts, ranking, permissions, cooldown, learning and ticket lifecycle are all real decisions. The
scenario tags are detected from what the engine did, then written to `demo/data/sim.js` for the pages to replay.

## Files

| Path | What it is |
|---|---|
| `SPEC.md` | the skeleton (source of truth, edited in Kiro) |
| `skill/SKILL.md` | the Kiro Crew skill an agent follows |
| `skill/scripts/run_incident.py` | walks one alert through the six states, writes a postmortem |
| `skill/scripts/patrol.py` | four crews patrol in parallel; `--remediate` repairs and escalates |
| `skill/remediation/remediate.py` | the repair loop, learning and escalation |
| `skill/remediation/policy.json` | **the permissions**: risk tiers, allow-list per device, caps, escalation groups |
| `skill/remediation/actions.json`, `runbooks.json` | the action catalogue and the built-in runbooks (zh/en) |
| `skill/remediation/harvest.py` | the case library collects fixes itself: ServiceNow KB, closed incidents, our resolved tickets, Teams / Slack / WeChat Work, email; verdicts verified / failed / unverified / rejected |
| `skill/remediation/sources/` | sample sources used when no live ServiceNow is configured |
| `skill/remediation/brain.py` | the AI interface: four tasks, guardrails, backends off / mock / claude / http / cmd |
| `skill/tests/test_brain_guardrails.py` | a badly behaved AI must not change what the engine does |
| `skill/remediation/notify.py` | pushes the right news to Teams / Slack once (dry run by default) |
| `skill/tests/test_safety.py` | kill switch, daily limit, re-check, self-heal, notifications |
| `skill/remediation/watch.py` | the active outage watch: master incident, outage email, shared board, progress posted back |
| `skill/remediation/orchestrator.py` | one patrol: threshold, maintenance, blast radius, repair, ticket upkeep |
| `skill/remediation/simulate.py` | the scripted morning that drives the real engine and writes `demo/data/sim.js` |
| `skill/mcp/incident_kb_server.py` | a real stdio MCP server: route, recall a fix, record a case |
| `skill/hooks/audit_incident.sh` | PostToolUse hook that audits postmortems |
| `demo/console.html` | autoplay ops console: 12 patrols, faults listed separately, outage board, notifications, 29 scenarios |
| `demo/servicenow.html` | simulated ServiceNow: incidents, work notes, case library, rejected sources |
| `demo/index.html` | the skeleton drawn as a spine, EN/中文 switch |
| `ROADMAP.md`, `DEVPOST.md` | what is built and what is next; the Devpost text |

## Run it

```bash
# the scripted morning (real engine) → demo/data/sim.js, then open demo/console.html
python3 skill/remediation/simulate.py

# harvest the case library from the sources
python3 skill/remediation/harvest.py --data-dir /tmp/kb --lang en

# one alert through the skeleton (add --lang zh for Chinese)
python3 skill/scripts/run_incident.py --type printer --target 10.0.4.21 --message "PAPER JAM (13.20)" --lang en

# four crews patrol at once, then repair and escalate (dry run, simulated: nothing fixes it)
python3 skill/scripts/patrol.py --remediate --simulate-fix none --lang en

# the scripted repair demo: see the crew learn, then fail and open a ticket
python3 skill/remediation/remediate.py --demo --lang en

# what the crew has learned so far
python3 skill/remediation/remediate.py --report --lang en
```

Dry run is the default. Nothing touches a device unless `policy.json` says `live` or you pass `--live`,
and only actions that have a command wired up can run.

Run the patrol on a schedule with Kiro Crew's cron (a no-LLM script job), for example every 5 minutes:
`python3 skill/scripts/patrol.py --remediate --lang en`.

## See the demo

Open `demo/index.html` (double-click). Pick a crew and fire an alert, patrol all four, or press
**Demo: repair fails, ticket opens**. The language follows your browser; the EN / 中文 switch is top right.

## Why Skeleton Crew

The category asks for a clean, flexible skeleton that proves its versatility with distinct
applications. The skeleton is the state machine; the applications are four device crews. A fifth crew
is one `investigate_<type>()` function, one runbook and a few catalogue entries.
