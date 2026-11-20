# Incident Skeleton — Kiroween 2026 (Skeleton Crew)

> One incident-response **skeleton** (a state machine), crewed by four device
> **handlers**. Same core, four haunting applications. Built spec-first with Kiro.

## The pitch

Every IT/ops team answers the same four kinds of 3 AM tickets: a printer threw
an error, a signage screen went black, a meeting room won't join the call, a
wireless AP dropped its clients. The steps are always the same — *receive,
triage, investigate, mitigate, resolve, log* — only the middle two change per
device. **Incident Skeleton** makes that shared spine one reusable state
machine, and lets each device type plug in its own investigate/mitigate logic.
One skeleton, a crew of four.

That is the Skeleton Crew brief: *a clean, flexible skeleton that proves its
versatility by powering distinct applications.* The skeleton is the state
machine; the distinct applications are the four device handlers.

## The skeleton (shared core)

A single state machine every alert walks through:

| # | State | What happens | Shared or plugged? |
|---|-------|-------------|--------------------|
| 1 | RECEIVE | alert in: type, severity, source, message | shared |
| 2 | TRIAGE | classify type + score severity, decide act/no-act | shared |
| 3 | INVESTIGATE | gather context for *this* device type | **plugged** |
| 4 | MITIGATE | act to cut impact for *this* device type | **plugged** |
| 5 | RESOLVE | re-check health, confirm recovery | shared |
| 6 | LOG | write the postmortem record | shared |

Shared across all device types: the state machine itself, triage/severity
rules, health re-check, and the postmortem log. Plugged per type: only
INVESTIGATE and MITIGATE.

## The crew (four device handlers)

Each handler implements `investigate()` and `mitigate()` for its device type:

### 1. Printer 🖨️
- alerts: paper jam, toner/ink low, device offline, error code
- investigate: SNMP status query, check the print queue, check network
  reachability, look up the error code
- mitigate: clear jam / swap toner → restart spooler → re-add the device →
  power-cycle

### 2. Digital Signage 📺
- alerts: player offline, content not updating, display black
- investigate: ping the player, check the CMS schedule/push status, check
  display power + HDMI, check network
- mitigate: reboot player → re-push content/schedule → reseat HDMI → swap player

### 3. Meeting-room AV 🎥
- alerts: room offline, can't join meeting, mic/camera fault, control panel hung
- investigate: check room-controller status, check codec/bridge, check the
  Zoom/Teams room, test mic + camera
- mitigate: reboot controller/codec → restart the room app → reseat USB devices
  → dispatch AV tech

### 4. Wireless AP 📶
- alerts: AP offline, clients dropping, association fail, weak coverage
- investigate: ping the AP, SNMP ifOperStatus, query the controller API for AP
  status / client count
- mitigate: controller-API reboot AP → PoE port power-cycle → RF tune
  (channel/power) → add or replace AP

## The demo

A single self-contained HTML page (no build, no server — open in a browser).
You pick one of the four alert types and fire a *simulated* alert. The page
animates the alert walking the **same** six-state skeleton, highlighting which
two steps are the plugged-in handler and which four are shared. Fire all four
in a row to see one core drive four "apps." Halloween skin: orange/black/purple,
a tombstone per dead device, bats on alert, a skeleton that dances when the
state machine reaches RESOLVE.

## Build with Kiro (on-theme)

- **Spec-driven:** this SPEC.md is the skeleton's source of truth, edited in Kiro.
- **Vibe-coded demo:** the HTML page is written by chatting with Kiro, not by hand.
- **Kiro Crew skill:** `skill/SKILL.md` + `skill/scripts/run_incident.py` run a
  real alert through the skeleton; a live agent follows the skill to do it.
- **MCP:** `skill/mcp/incident_kb_server.py` is a real stdio MCP server exposing
  `lookup_support_group`, `recall_fix`, `record_case` — "bring in new
  capabilities with MCP," wired to the roadmap's routing / knowledge / 病例库.
- **Hook:** `skill/hooks/audit_incident.sh` is a PostToolUse hook that audits
  postmortems — "customize workflows with hooks," non-blocking.

## Submission checklist (Devpost)

- [x] `SPEC.md` (this file) — the skeleton
- [x] `demo/index.html` — the animated demo, single file
- [x] `README.md` — overview + how to run + record steps
- [x] `ROADMAP.md` — reactive skeleton → autonomous AIOps (病例库 vision)
- [x] `DEVPOST.md` — project-page text to paste into the submission
- [x] `skill/` — runnable Kiro Crew skill (SKILL.md + run_incident.py + logs/)
- [x] Enter category: Skeleton Crew
- [ ] Screen recording of the demo (manual: open `demo/index.html`, 连跑四套班底, `Cmd+Shift+5`, ~60s)
- [ ] Paste `DEVPOST.md` into the Devpost project page and submit
