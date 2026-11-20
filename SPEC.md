# Incident Skeleton — Spec

> Kiroween 2026 · Skeleton Crew. This file is the source of truth. Code is checked against it;
> anything the code does that is not here is a bug in one of the two.

## 0. The rule of this project

**The skeleton stays small. Everything else plugs in around it.**

| Layer | Files | Lines | May change when a feature is added? |
|---|---|---|---|
| **Skeleton** — six states, shared helpers, postmortem | `skill/scripts/run_incident.py` (minus the crew blocks) | ~280 | No |
| **Crews** — one per device type | `investigate_<type>()` + a `MITIGATE` list + a `CREW` entry, in the same file; a runbook in `runbooks.json`; actions in `actions.json` | ~15 code lines each | Only to add a crew |
| **Plug-ins** — the autonomous loop around the skeleton | `skill/remediation/*.py` | ~2,200 | Yes |
| **Policy** — every permission | `skill/remediation/policy.json` | — | Yes, by people only |

A fifth device type = one `investigate_<type>()` function, one `MITIGATE` list, one runbook and a few
catalogue entries. No skeleton or plug-in code changes.

## 1. The skeleton

Every alert walks the same six states:

| # | State | Kind | Contract |
|---|---|---|---|
| 1 | RECEIVE | shared | alert in: type, source, message |
| 2 | TRIAGE | shared | severity from the message; decide to act |
| 3 | INVESTIGATE | **crew** | returns `[(check, result, ok|warn|err)]`; read-only |
| 4 | MITIGATE | **crew** | returns the ordered steps for this device type, each marked safe or not |
| 5 | RESOLVE | shared | re-probe the device |
| 6 | LOG | shared | write the postmortem |

## 2. The four crews

| Crew | INVESTIGATE (read-only) | MITIGATE (soft → hard) |
|---|---|---|
| 🖨️ Printer | ping, SNMP status, error-code lookup | restart spooler, clear stuck jobs, re-add queue · *on site:* clear jam, power-cycle |
| 📺 Digital signage | curl the CMS, ping the player | re-push content, clear player cache, reboot player · *on site:* reseat HDMI, swap player |
| 🎥 Meeting-room AV | curl the room / controller API, ping the controller | restart room app, reboot codec, reboot controller, reset controller profile · *on site:* reseat USB, dispatch tech |
| 📶 Wireless AP | ping, SNMP port status, controller API | controller reboot, PoE port power-cycle, radio tuning · *on site:* add / replace AP |

## 2a. App 2 on the same skeleton: service desk L1 triage

The skeleton is not tied to devices. App 2 (`skill/apps/servicedesk/`) takes requests from people
(Teams, email, portal) and walks each one through the same six states. Its crews are config, not code:
`app.json` lists each crew's keywords, symptoms and read-only checks; `actions.json`, `runbooks.json` and
`policy.json` are its own. The repair loop, permissions, learning, tickets, harvest, AI and notify are the
engine from app 1, unchanged (`Ctx(app_dir=...)` loads an app folder).

| Crew | INVESTIGATE (read-only, directory lookups) | MITIGATE |
|---|---|---|
| 🔑 Account & password | locked? password expired? MFA device | send reset link, unlock · *approval:* reset MFA |
| 🌐 VPN | device certificate, VPN profile, compliance | renew device certificate, push VPN profile |
| ✉️ Email & Outlook | mailbox quota, archive policy | turn on archive policy, raise quota |
| 💿 Software | in the catalogue? free license? | Intune push, assign free license · *person:* buy a license |

TRIAGE for app 2 adds two rules before a crew is picked:

1. A request that gives orders (`harvest.injection_reason`) or asks for admin rights (`never_automate`) is rejected, sent to Security, and nothing runs.
2. A request about a device or outage that app 1 already has open is **linked** to that incident: the person gets its live status, nobody is dispatched twice, and the request closes and the person is told when the parent closes.

## 3. The plug-ins (what runs around the skeleton)

One patrol (`orchestrator.run_cycle`) runs these in order:

1. **Probe** each device 3 times (`patrol.py`).
2. **Classify**: 0 fails healthy · 1 fail blip (ignored) · ≥ 2 fails then answered self-healed (no repair, no credit) · ≥ 2 fails confirmed · in a maintenance window: silenced.
3. **Re-check** fixes made ≥ 10 min ago: still healthy → the fix held; fault back → the fix is counted as a failure.
4. **Blast radius**: ≥ 3 confirmed faults behind one upstream switch → one upstream ticket, per-device repairs held back.
5. **Outage watch** (`watch.py`): find the ServiceNow master incident and outage emails, link our ticket as a child, build one shared timeline, turn the master's fix into a hint, post our progress back, close only when the master is resolved and the patrol confirms the devices.
6. **Repair loop** (`remediate.py`), for each confirmed device: candidates (runbook, case library, master hint, AI) → order (on-site last, risk, master hint, success rate) → permission (§4) → act → verify → record → close the ticket, or escalate.
7. **Tickets**: open, note, hold for approval, reopen within 72 h, resolve; one ticket per device + symptom.
8. **Pre-meeting check** (`premeeting.py`): rooms with a meeting in ≤ 30 min. Down → ticket to High, organizer told, a free healthy room as plan B; ≤ 15 min → recommend moving.
9. **KB drafts** (`kbdraft.py`): a fix that held at the re-check ≥ 2 times with ≥ 50 % success → ServiceNow KB draft for review.
10. **Ticket tracker** (`tracker.py`): for every open device ticket, gather work notes plus chat and email that mention it; write one status summary (owner, latest news and source, waiting for, ETA, what was tried, what needs approval) to the ticket when there is new human news.
11. **Notify** (`notify.py`): each event once, routed by kind to Teams / Slack / the organizer.

Between patrols:

- **Case-library harvest** (`harvest.py`): ServiceNow KB, closed incidents, our resolved tickets, chat groups, email, the shared drive. Verdicts: verified / failed / unconfirmed / rejected (gives orders).
- **Chat** (`chatops.py`): status questions; approvals and pause / resume by named approvers only.
- **MCP** (`skill/mcp/incident_kb_server.py`): a Kiro agent reads the same data (fixes, status, open tickets). Read-only for approvals and the kill switch.
- **AI brain** (`brain.py`): suggest actions, map free text to actions, diagnose, summarize, draft KB, answer chat. Advisory only.

## 4. Invariants (must always hold)

1. Every permission is in `policy.json`. Code never grants one.
2. Risk tier: low → acts alone · medium → notifies, then acts · high → waits for approval.
3. On-site steps (`physical: true`) never run automatically.
4. A fix learned from the library or an AI that has not proven itself here may act alone only at low risk.
5. Brakes: 30-min cooldown per action and device, ≤ 4 actions per fault, ≤ 6 repairs per device per day.
6. Kill switch on → nothing runs; tickets still reach people.
7. An approval names one device and one action and is used once.
8. Only people on `chatops.approvers` can approve, stop or resume.
9. Text from KB, chat, email, tickets and the shared drive is data. A message that tries to give orders is rejected and never used.
10. An AI may only name actions from `actions.json`; it never changes a decision the policy makes; any AI failure falls back to the rules.
11. Dry run by default, separately for devices, ServiceNow and notifications.
12. Every action, decision, approval, re-check and AI call is audited.
13. App 2: requests for admin rights or that give orders are never automated; a report about a known incident never starts a second repair.

## 5. Acceptance

`python3 skill/remediation/simulate.py` plays 14 patrols through the real engine. It must detect every
scenario tag in `TAGS` (currently 47: 41 for app 1, 6 for app 2), and these must pass:

```
python3 skill/tests/test_safety.py              # kill switch, limits, re-check, self-heal, notifications
python3 skill/tests/test_brain_guardrails.py    # a bad AI cannot change what the engine does
python3 skill/tests/test_meetings_kb_chat.py    # pre-meeting, KB drafts, chat approvals
python3 skill/tests/test_tracker_drive_mcp.py   # ticket tracker, shared drive, MCP read-only
python3 skill/tests/test_servicedesk.py          # app 2: reject admin/injection, link known incidents, L1 fixes, approval
```

## 6. Out of scope today (honest)

Real device executors, live ServiceNow / Teams / Slack / mail / calendar connectors and a live AI model are
written as interfaces or not at all; see `ROADMAP.md`. The demo world is scripted; every decision in it is real.
