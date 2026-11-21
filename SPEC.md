# Incident Skeleton — Spec (v4.1)

> Kiroween 2026 · Skeleton Crew. This is the short source of truth. The full requirements, design and tasks are in `.kiro/specs/incident-skeleton-v4/`. Code is checked against both; anything the code does that is not written here or there is a bug in one of them.

## 0. The rule of this project

**The skeleton stays small. Apps are adapters. Everything else plugs in around it.**

| Layer | Files | Size | May change when a feature is added? |
|---|---|---|---|
| **Skeleton**: six steps, three slots | `skill/skeleton_v4/skeleton.py` | 102 lines | No |
| **Apps**: one adapter each | `skill/skeleton_v4/app_devices.py`, `skill/skeleton_v4/app_servicedesk.py` | ~100–180 lines each | Only to add an app |
| **Plug-ins**: outage gate, ranking, learning | `skill/skeleton_v4/plugins.py`, `skill/skeleton_v4/learning.py` | — | Yes |
| **Shared repair library**: repair loop, tickets, case library, notify, probes | `skill/remediation/`, `skill/apps/servicedesk/`, `skill/scripts/` | — | Yes, never to add a step |
| **Policy**: every permission | `skill/remediation/policy.json`, `skill/apps/servicedesk/policy.json` | — | Yes, by people only |

The skeleton imports nothing app-specific. The adapters call the shared repair library. The library is a set of parts, not a second skeleton.

A third app = one adapter file plus config. `skeleton.py` does not change. `skill/tests/test_skeleton_v4.py` (`test_1_7_a_third_app_needs_only_an_adapter`) proves this.

## 1. The skeleton

Every item walks the same six steps, in this order, through `skeleton.run()`:

| # | Step | Kind | Contract |
|---|---|---|---|
| 1 | RECEIVE | shared | the adapter describes the intake |
| 2 | TRIAGE | shared | safety → `triage_gate` → known-incident link → crew choice |
| 3 | INVESTIGATE | **crew** | read-only checks for the chosen crew |
| 4 | MITIGATE | **crew** | repair through the policy; `mitigate_rank` may add hints and narrow the allow-list |
| 5 | RESOLVE | shared | re-check, or hand to a person |
| 6 | LOG | shared | ticket, case history; `log_learn` learns from confirmed re-checks |

If TRIAGE stops early (rejected, linked to a known or vendor incident), the later steps are recorded as skipped with a reason, so every record has six steps.

## 2. The two apps

| | App 1 · office devices | App 2 · service desk L1 |
|---|---|---|
| Input | patrol probes (machines report) | a person's message (Teams, email, portal) |
| Crews | printer, digital signage, meeting-room AV, wireless AP | account, VPN, email, software |
| INVESTIGATE | ping, SNMP, HTTP, controller API | directory lookups declared in `app.json` |
| MITIGATE | restart, reboot, PoE cycle, … | reset link, VPN profile, archive policy, Intune push, … |
| Special TRIAGE | blast radius, Teams Rooms under a vendor outage | admin and injection rejection, Teams and Outlook detection, links to app 1 incidents |

## 3. The three plug-in slots

| Slot | Step | Job |
|---|---|---|
| `triage_gate` | TRIAGE | Is a vendor-wide outage the cause? If so, link to one vendor parent and hold useless actions. |
| `mitigate_rank` | MITIGATE | Adopted methods become "try first" hints; paused methods are removed from an in-memory allow-list copy. |
| `log_learn` | LOG | Learn only from confirmed re-checks. Provisional results teach nothing. |

Learning reads sources by tier: A vendor MCP and official status → B company sources → C trusted web → D public reports.

## 4. Invariants (must always hold)

1. Every permission is in a `policy.json`. Code never grants one.
2. Risk tier: low → acts alone · medium → notifies, then acts · high → waits for approval.
3. On-site steps (`physical: true`) never run automatically.
4. A fix learned from the library or an AI that has not proven itself here may act alone only at low risk.
5. Brakes: 30-min cooldown per action and device, ≤ 4 actions per fault, ≤ 6 repairs per device per day.
6. Kill switch on → nothing runs; tickets still reach people.
7. An approval names one device and one action and is used once.
8. Only people on `chatops.approvers` can approve, stop or resume.
9. Text from KB, chat, email, tickets, the shared drive, vendor MCP output and the web is data. A message that tries to give orders is rejected and never used.
10. An AI may only name actions from `actions.json`; it never changes a decision the policy makes; any AI failure falls back to the rules.
11. Dry run by default, separately for devices, ServiceNow and notifications.
12. Every action, decision, approval, re-check and AI call is audited.
13. App 2: requests for admin rights or that give orders are never automated; a report about a known incident never starts a second repair.
14. The skeleton runs exactly six steps in fixed order. Plug-ins attach only to the three named slots.
15. Learning may narrow permission and never widen it. A full run leaves every `policy.json`, `actions.json` and `app.json` byte-identical.
16. Tier C and D sources need corroboration from tier A or B. A public report never promotes or demotes a method.
17. Safety rejection runs before any plug-in in TRIAGE.

## 5. Acceptance

```
python3 skill/remediation/simulate.py     # must print "scenarios covered: 47/47   missing: none"
python3 skill/skeleton_v4/run.py          # one dry-run cycle of both apps through the runtime
for f in skill/tests/test_*.py; do python3 "$f"; done   # all pass
```

On Windows use `python` instead of `python3`.

## 6. Out of scope today (honest)

Real device executors, live ServiceNow / Teams / Slack / mail / calendar connectors, signed-in vendor MCP servers (Microsoft, Cisco), live web search and a live AI model are written as interfaces or not at all. The demo world is scripted; every decision in it is made by the real code in dry run.
