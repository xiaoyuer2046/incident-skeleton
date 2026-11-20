# Incident Skeleton — one skeleton, four crews

**Kiroween 2026 · Skeleton Crew**

A single incident-response state machine powers four device handlers —
printer, digital signage, meeting-room AV, and wireless AP. The same six-state
spine walks every alert; each device type plugs its own read-only checks into
INVESTIGATE and its own prescribed fixes into MITIGATE. One core, four
applications — and a fifth is one function away.

> *Skeleton crew* literally means the minimum staff that keeps an operation
> running. The skeleton is the state machine; the four handlers are the crew.

## What it does

An IT/ops team answers the same four kinds of tickets: a printer threw an
error, a signage screen went black, a meeting room won't join the call, a
wireless AP dropped its clients. The steps are always the same — *receive,
triage, investigate, mitigate, resolve, log* — only the middle two change per
device. Incident Skeleton makes that shared spine one reusable state machine,
and lets each device type plug in its own investigate/mitigate logic.

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
 shared    shared    crew          crew      shared    shared
```

- 🖨️ **Printer** — INVESTIGATE: ping, SNMP `hrDeviceStatus`, error-code lookup
  (HP LJ codes). MITIGATE: clear jam / swap toner → restart spooler → re-add
  queue → power-cycle.
- 📺 **Digital Signage** — INVESTIGATE: curl the CMS endpoint + ping the player.
  MITIGATE: reboot player → re-push content → reseat HDMI → swap player.
- 🎥 **Meeting-room AV** — INVESTIGATE: curl the controller/room API + ping the
  controller. MITIGATE: reboot controller → reboot codec → restart room app →
  reseat USB → dispatch AV tech.
- 📶 **Wireless AP** — INVESTIGATE: ping the AP, SNMP `ifOperStatus`, query the
  controller API for AP status / client count. MITIGATE: controller-API reboot
  AP → PoE port power-cycle → RF tune (channel/power) → add/replace AP.

It runs **real, read-only checks** (ping, curl, SNMP) — not faked. It never
restarts or reconfigures a device unless you pass `--apply`, and even then only
the steps each handler marks safe (none by default). Every run writes a
postmortem to `skill/logs/`.

## Why we built it

The Skeleton Crew brief asks for *a clean, flexible skeleton that proves its
versatility by powering distinct applications.* Ops device alerts fit
perfectly: the response flow is one skeleton, and the four device types are
the distinct applications it powers. Building it spec-first meant the skeleton
was fixed before any handler existed — then each handler was a small,
independent addition. The wireless AP handler was added last, as a fourth, to
prove the skeleton really does take a new device with one function.

## How we built it (with Kiro)

- **Spec-driven development.** `SPEC.md` is the skeleton's source of truth,
  written before any code. The six states and the shared/crew split are defined
  there, and every handler is checked against it.
- **Vibe-coded in chat.** The visual demo (`demo/index.html`) and the runner
  were written by conversing with Kiro, not by hand-typing.
- **A Kiro Crew skill.** `skill/SKILL.md` is a real skill procedure an agent
  follows; the runner is the engine it drives. This is the Kiro-native form —
  the skeleton lives where agents can actually use it.
- **Readable, extensible skeleton.** Adding a fifth device type is one
  `investigate_<type>()` function and one MITIGATE list — the six-state core
  never changes. That's the skeleton proving its versatility.
- **An MCP server (`skill/mcp/incident_kb_server.py`).** A real stdio MCP server
  exposes three tools an agent calls mid-flow — `lookup_support_group` (route
  an incident to the right IT group), `recall_fix` (pull a known fix from the
  local KB), and `record_case` (write a verified case to the 病例库). That is
  "bring in new capabilities with MCP," wired to the roadmap.
- **A chat-lifecycle hook (`skill/hooks/audit_incident.sh`).** A PostToolUse
  hook appends an audit line whenever a postmortem is written — "customize
  workflows with hooks," non-blocking (always exits 0).

## Run it

```bash
# end to end against safe public targets (real ping/curl/snmp fire)
python3 skill/scripts/run_incident.py --sample

# a real alert
python3 skill/scripts/run_incident.py --type printer \
  --target 10.0.4.21 --message "PAPER JAM (13.20)"

# a wireless AP behind a controller
python3 skill/scripts/run_incident.py --type wifiap \
  --target 10.0.8.5 --message "AP offline, clients dropping"

# the four crews patrol at once; only a confirmed failure reaches the skeleton
python3 skill/scripts/patrol.py

# the visual demo
cd demo && python3 -m http.server 8777 --bind 127.0.0.1   # open http://127.0.0.1:8777
```

## What's next

Today it's **reactive**: an alert lands, the skeleton walks it. The same
skeleton is the foundation for an **autonomous** AIOps crew (see `ROADMAP.md`):

1. **Detect & alert (threshold-gated)** — proactive polling (ping/SNMP/CMS/
   controller heartbeat) raises alerts itself; only *confirmed* errors (sustained
   or recurring past a threshold) open a ticket, not every blip. On confirm it
   auto-creates and routes a **ServiceNow** incident to the right IT group.
2. **Auto-remediate (tiered approval)** — low-risk fixes auto-run; medium-risk
   notify-then-act; high-risk wait for a human. Risky/physical ones escalate.
3. **Symptom → solution matching** — map symptoms (error code, unreachable,
   black screen, can't join, mass client drop) to known fixes, not just by
   device type.
4. **Auto-gather solutions** — when no fix matches, search **ServiceNow KB**,
   the **company shared drive**, and **chat history** for how it was solved
   before.
5. **病例库 (case-history KB)** — every incident, its root cause, and the fix
   that worked is recorded into a growing case-history knowledge base (only
   verified fixes enter; low success-rate ones are down-ranked). Next time
   similar symptoms appear, the system recalls the prior case.
6. **Open-incident tracking** — for each unclosed incident, gather ServiceNow
   work notes + chat + email by keyword and summarize the current status, so
   no one has to dig across three systems to see where things stand.

Each step adds a layer *around* the six-state core — the skeleton doesn't
change, which is exactly the point of building on a skeleton.

## Built with

Kiro (spec-driven development, vibe-coded in chat), Kiro Crew skills, an MCP
server (incident-kb), a PostToolUse hook, Python (stdlib + `ping`/`curl`/`snmpget`),
vanilla HTML/CSS/JS for the demo.
