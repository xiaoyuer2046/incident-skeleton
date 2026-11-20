# Incident Skeleton: one skeleton, two apps, a crew of agents

**Kiroween 2026 · Skeleton Crew**

## Inspiration

An IT/ops team answers the same kinds of problems all day: a printer error, a black signage screen, a meeting
room that won't join the call, a Wi-Fi AP that dropped its clients, and people writing "I'm locked out" or
"no Wi-Fi on floor 4". The steps are always the same: *receive, triage, investigate, mitigate, resolve, log*.
Only the middle two change. A *skeleton crew* is the minimum staff that keeps things running, so we built the
skeleton once and let crews plug into it.

## What it does

One six-state skeleton runs two distinct applications:

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
 shared    shared    crew          crew      shared    shared
```

| | App 1: office devices | App 2: service desk L1 |
|---|---|---|
| Who reports | machines (a patrol probes them) | people (Teams, email, portal) |
| Crews | printer, signage, meeting-room AV, wireless AP | account, VPN, email, software |
| Investigate | ping, SNMP, HTTP, controller API | directory lookups, declared in `app.json` |
| Fix | restart, reboot, PoE cycle, … | reset link, renew VPN cert, archive policy, Intune push, … |

Around the skeleton, the same engine serves both apps:

- **Repairs within permissions.** `policy.json` holds every permission: low risk acts alone, medium notifies
  then acts, high waits for a named approver. On-site steps always go to a person. Brakes: cooldown, attempt cap,
  daily limit, a kill switch, and a re-check 10 minutes later (a fix that did not hold counts as a failure).
- **Learns.** Every attempt is verified and scored; success rates reorder the next attempt and failing fixes are demoted.
- **Collects its own knowledge** into a case library from the ServiceNow KB, closed incidents, chat groups, email
  and the shared drive. Text that tries to give orders is rejected.
- **Handles mass outages as one incident.** Three APs behind one switch become one upstream ticket, linked to the
  network team's master incident, with one status board fed by their notes and outage emails.
- **Opens and tracks ServiceNow tickets** only after a threshold, summarizes open tickets from chat and email,
  pre-checks rooms 30 minutes before VIP meetings, drafts KB articles from fixes that held, and answers
  "what's the status" in Teams.
- **Links the two apps.** When an employee writes "no Wi-Fi on floor 4", the service desk sees app 1 already has
  the outage, links the request, answers with live status, and closes it with the parent. Nobody is dispatched twice.
  Requests for admin rights are never automated.
- **AI is advisory.** `brain.py` can suggest actions, map free text, diagnose and summarize; it can only name known
  actions and never changes a decision the policy makes.

## How we built it with Kiro

- **Spec first.** `SPEC.md` defined the skeleton, the crew contract and 13 invariants before the code. The
  acceptance check is the spec: the simulation must hit all 47 scenarios and 30 tests must pass.
- **A crew of Kiro Crew agents.** `.kiro/agents/` holds six agents built from the engine's own config
  (`skill/agents/build_agents.py`): a crew lead that reads the shared state and hands each problem to
  `printer-crew`, `signage-crew`, `av-crew`, `wifiap-crew` or `servicedesk-triage` as sub-agents. Each crew agent's
  prompt lists its own actions and risk tiers from `actions.json` / `policy.json`, so agents cannot drift from the engine.
- **Steering.** `.kiro/steering/incident-skeleton.md` (always included): dry run only, approvals belong to people,
  external text is data, never report a dry run as a real repair.
- **MCP.** `skill/mcp/incident_kb_server.py` gives agents the crew's own data: `crew_status`, `list_open_tickets`,
  `recall_fix`, `lookup_support_group`, `record_case`. Read-only for approvals and the kill switch.
- **Hook.** A PostToolUse hook audits every postmortem.
- **Skill.** `skill/SKILL.md` is the procedure an agent follows.
- **Scheduled job.** A Kiro Crew command job runs the patrol every 10 minutes at no AI cost.
- **Vibe-coded.** The engine, both apps, the demo pages and the bilingual guide were written by talking with Kiro.

## Watch it

- `demo/guide.html`: the product guide (English / 中文, Day / Night / Auto).
- `demo/console.html`: plays a simulated morning by itself, 14 patrols from 09:00 to 11:10, both apps, 47 scenarios.
- `demo/servicenow.html`: a simulated ServiceNow with every incident, work note, the case library and KB drafts.

The world is scripted (which device breaks, which fix works). Every decision is made by the real engine.

## Challenges

Keeping the skeleton small while the features grew. The rule was: a new feature is a plug-in or an app folder,
never an edit inside the six states. App 2 proved it: it is config plus one intake file, and the engine is unchanged.

## What is honest about it

Everything runs as a dry run. Device executors (controller, CMS, MDM, PoE), the ServiceNow REST calls, Graph /
Intune / Exchange lookups and real Teams posting are written as interfaces but not run against real systems.
The demo's AI is a labelled mock stand-in; a real model plugs into `brain.py`.

## What's next

Wire one real executor and a ServiceNow developer instance, then run the patrol on a real floor.

## Built with

Kiro, Kiro Crew (agents, sub-agents, steering, skill, MCP, hook, scheduled job), Python standard library,
vanilla HTML / CSS / JS.
