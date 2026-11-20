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
| Fix executors (controller API, CMS, MDM, PoE switch) | **not wired**: only `clear-queue` has a command. Live mode reports "no executor" and hands the step to a person |
| ServiceNow ticket + KB | payload, de-duplication and REST code are written; **not run against a real instance**. Default is dry run with a sample KB file |
| AI advisor | a hook only (`INCIDENT_AI_CMD`); suggestions can only pick known actions and stay under the policy |
| Demo page | simulated data, for the story |

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
| `skill/remediation/kb_servicenow_sample.json` | sample KB used when no ServiceNow is configured |
| `skill/mcp/incident_kb_server.py` | a real stdio MCP server: route, recall a fix, record a case |
| `skill/hooks/audit_incident.sh` | PostToolUse hook that audits postmortems |
| `demo/index.html` | the visual demo: the skeleton drawn as a spine, EN/中文 switch |
| `ROADMAP.md`, `DEVPOST.md` | what is built and what is next; the Devpost text |

## Run it

```bash
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
