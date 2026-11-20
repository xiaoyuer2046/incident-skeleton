# 💀 Incident Skeleton — 骨架驱动四套班底

> Kiroween 2026 · **Skeleton Crew** category · built with Kiro (specs, skill, MCP, hooks)

One incident-response **skeleton** (a 6-state state machine) powers four
device **handlers** — 🖨️ printer, 📺 digital signage, 🎥 meeting-room AV, 📶
wireless AP. The same spine walks every alert; each device type plugs its own
read-only checks into INVESTIGATE and its own prescribed fixes into MITIGATE.

> **Skeleton Crew** (原意) = 维持运转的最少班底. The skeleton is the state
> machine; the four handlers are the crew that keeps the lights on.

## What's in the box

| File | What it is |
|------|-----------|
| `SPEC.md` | The spec — defines the skeleton (source of truth, edited in Kiro) |
| `skill/SKILL.md` | A Kiro Crew skill: the procedure an agent follows |
| `skill/scripts/run_incident.py` | The runnable engine: walks one alert through the 6 states, does real read-only checks, writes a postmortem |
| `skill/scripts/patrol.py` | Four crews patrol four devices in parallel; only a device failing ≥ 2 of 3 probes is confirmed and handed to the skeleton |
| `skill/logs/` | Auto-generated incident postmortems |
| `skill/mcp/incident_kb_server.py` | A real MCP server (stdio JSON-RPC): lookup_support_group / recall_fix / record_case tools |
| `skill/mcp/kb.json` | The local knowledge base the MCP `recall_fix` tool reads |
| `skill/mcp/case_history.jsonl` | The 病例库 (case-history KB) the MCP `record_case` tool appends to |
| `skill/hooks/audit_incident.sh` | A PostToolUse hook that audits postmortems |
| `demo/index.html` | A self-contained visual demo — animate an alert through the same skeleton |
| `ROADMAP.md` | Where this goes next: reactive skeleton → autonomous AIOps |
| `DEVPOST.md` | The Devpost project-page text (paste into the submission) |

## The skeleton (shared core)

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
 shared    shared    crew          crew      shared    shared
```

Four states are shared; **INVESTIGATE** and **MITIGATE** are plugged per device
type. Add a fifth device type by writing one `investigate_<type>()` and one
`MITIGATE` list — the core never changes. That is the skeleton proving its
versatility.

## Run it

```bash
# see it work end to end against safe public targets (real ping/curl/snmp)
python3 skill/scripts/run_incident.py --sample

# run a real alert (point --target at a real device on a network that can reach it)
python3 skill/scripts/run_incident.py --type printer \
  --target 10.0.4.21 --message "PAPER JAM (13.20)"

# a signage CMS endpoint
python3 skill/scripts/run_incident.py --type signage \
  --target https://cms.example/health --message "player offline 14m"

# a wireless AP behind a controller
python3 skill/scripts/run_incident.py --type wifiap \
  --target 10.0.8.5 --message "AP offline, clients dropping"

# a meeting room
python3 skill/scripts/run_incident.py --type av \
  --target 10.0.8.30 --message "can't join meeting, panel hung"
```

Read-only by default. `--apply` runs only the steps each handler marks safe
(none by default — every fix needs a human). Each run writes a postmortem to
`skill/logs/`.

## See the demo

```bash
cd demo && python3 -m http.server 8777 --bind 127.0.0.1
# open http://127.0.0.1:8777  — or just double-click demo/index.html
```

Pick a crew, hit **触发告警**, watch the alert walk the same six states. Hit
**连跑四套班底** to see one core drive all four. Hit **🔭 同时巡检四台** to see
four crews probe at once: a one-off blip is ignored, only a confirmed failure
is handed to the skeleton.

## Record the demo (for Devpost)

The recording is a manual step (this repo can't film itself):
1. Open `demo/index.html` in Chrome.
2. Click **连跑四套班底**.
3. macOS: `Cmd+Shift+5` → record the window for ~60s.
4. Trim and upload to the Devpost project page.

## Why Skeleton Crew

The Skeleton Crew brief asks for *a clean, flexible skeleton that proves its
versatility by powering distinct applications.* The skeleton is the state
machine; the distinct applications are the four device handlers. One spine,
four crews — and a fifth crew is one function away.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) — from this reactive skeleton to an autonomous
AIOps crew: threshold-gated detect & alert (auto ServiceNow ticketing), tiered
auto-remediation, symptom→solution matching, auto-gathering fixes from
ServiceNow KB / shared drives / chat history, a verified-only **病例库**
(case-history knowledge base), and open-incident status tracking.
