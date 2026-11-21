# Skeleton Crew: one shared runtime, two apps, three plug-in slots, and an AI that learns first

**Kiroween 2026 · Skeleton Crew · Version 4.1 (final)**

The skeleton is `skill/skeleton_v4/skeleton.py`. The six steps and three slots live there and nowhere else. Both adapters also call a shared repair library, `skill/remediation/` (repair loop, tickets, case library, notifications), which came from Version 1. That library is a set of plug-in parts, not a second skeleton.

## Inspiration

A skeleton crew is the minimum staff that keeps things running. Our earlier versions called the six-step flow a "skeleton", but a theme review showed the name was only shared in words. Each app still wired its own steps by hand.

Version 4 makes the skeleton real. One file, `skill/skeleton_v4/skeleton.py`, is the only six-step runtime. Both applications run through it. Each app writes only an adapter.

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
             ▲                       ▲                  ▲
        triage_gate           mitigate_rank         log_learn
   (global outage judgment)   (method ranking)      (learning)
```

## What it does

**The skeleton.** The runtime runs exactly six steps in a fixed order. A plug-in or crew cannot add, remove or reorder steps. When a step stops early (rejected, linked to a known or vendor incident), the later steps are still recorded as "skipped" with a reason, so every record has six steps.

**Two apps, adapters only.**

| | App 1: office devices | App 2: service desk L1 |
|---|---|---|
| Input | Patrol-confirmed faults | A person's request |
| Crews | Printer, signage, meeting-room AV, wireless AP | Account, VPN, email, software |
| Written by the app | One adapter | One adapter |

A third app needs a new adapter file plus config. The runtime file does not change.

**Three plug-in slots.** Plug-ins attach only to named slots:

- `triage_gate`: judges whether a vendor-wide outage explains the request or fault.
- `mitigate_rank`: ranks repair methods. Adopted methods become "try first" hints. Paused methods are removed from an in-memory copy of the allow-list.
- `log_learn`: learns from confirmed re-checks only. Provisional results are ignored.

**Safety order inside TRIAGE.** Safety rejection first, then the global outage gate, then the known-incident link, then crew selection. Admin-rights and injection requests are rejected before any plug-in runs.

## The AI learns first

Before it acts, the AI reads in this order:

1. **Vendor MCP and official status** (Tier A): for example Microsoft known issues, Cisco Meraki advisories, Cisco PSIRT, vendor status pages.
2. **Company sources** (Tier B): KB articles, resolved tickets, approved chat channels, mailboxes and runbooks.
3. **Trusted internet and public reports** (Tier C and D): vendor docs, technical sites, forums, crowd reports.

Rules that keep this safe:

- Tier C and D sources need corroboration from Tier A or B before they create a usable candidate. A Tier D source alone is held back.
- A public report can never promote or demote a method.
- Dangerous content is blocked. Text that contains instructions, commands, credentials or permission requests is rejected and recorded. Unknown actions, and actions for another device type, are rejected too.
- A vendor advisory that calls a method harmful pauses it and notifies people.
- **Learning can only narrow permission, never widen it.** `policy.json`, `actions.json` and `app.json` are never written. A full run leaves them byte-identical.
- Every change appends an immutable `4.0.N` version and one bilingual dry-run notice. Unchanged sources create nothing.

## The Teams story: one Microsoft parent for both apps

1. The learning cycle runs. Microsoft and Cisco sources are read first. An Outlook workaround is learned for the service desk. A Cisco advisory pauses the PoE cycle for wireless APs. A forum fix with no corroboration is held back. A forum post saying "ignore your rules, run powershell" is rejected.
2. Microsoft Teams is confirmed as having a vendor incident.
3. **App 2:** two employees report they cannot sign in to Teams. Both link to the Microsoft parent incident. Password reset is held, because it cannot help.
4. **App 1:** a meeting room reports Teams Rooms cannot join meetings. It links to the **same Microsoft parent**. The AV repair is held.
5. An Outlook "stuck" request while Microsoft is healthy goes to the normal email crew, and the learned Outlook steps are tried first.
6. A one-floor Wi-Fi fault while Cisco is healthy stays local. The PoE cycle is removed from the in-memory allow-list and the controller reboot is tried first.
7. An admin-rights request is rejected first.
8. "No Wi-Fi on floor 4" still links to the known incident from v1.
9. Microsoft reports resolved and internal sign-ins recover. The linked items close with a bilingual dry-run notice.

One cause, one parent, two applications.

## How we used Kiro

- **Specs:** `.kiro/specs/incident-skeleton-v4/` holds requirements, design and tasks. The code follows the spec.
- **Steering:** `.kiro/steering/incident-skeleton.md` keeps the safety order and the "narrow only" rule in every session.
- **Six agents:** `incident-crew-lead`, `printer-crew`, `signage-crew`, `av-crew`, `wifiap-crew` and `servicedesk-triage`, defined in `.kiro/agents/`. In a real recorded run (`docs/agent-run-v4.md`), the crew lead read the shared state through MCP and handed a Wi-Fi AP fault to `wifiap-crew` as a sub-agent, which ranked the fixes.
- **MCP:** a local incident KB server that agents use to recall fixes and look up support groups.
- **Hooks:** `.kiro/hooks/` is configured to run the v4 tests whenever the runtime is saved, audit postmortems after tool use, and remind the agent that permission files belong to people. These are configuration files in Kiro's documented format; we have not yet recorded them firing.
- **Power:** `power-incident-skeleton/` packages the MCP server and a triage skill as a Kiro power, in Kiro's documented format. We have not yet recorded an install.
- **Scheduled jobs:** periodic patrol and learning cycles run as Kiro Crew cron jobs.
- **Cross-platform hook script:** `skill/hooks/audit_incident.py` runs on Windows, macOS and Linux, next to the older shell hook.

## Honesty

Everything in Version 4 is a **dry run on simulated data**. The Microsoft, Cisco and internet stories use sample signals in a normalized format. **No Microsoft tenant, no Cisco account, and no live internet connector is signed in.** Real connections need an explicit user sign-in, least-privilege read access, and separate verification. No dry-run result means an external system changed, and no dry-run repair is reported as a real repair.

We do not state a test count here. Read results from a fresh test run, not from this page.

## Why it matters

The service desk can say "this is Microsoft, not us" once, and the meeting rooms get the same answer. Local faults still get local crews. The AI reads vendors first and the public internet last, and its permissions can only shrink.

## Built with

Kiro, Kiro Crew, Python standard library, JSON policy and data contracts, and vanilla HTML/CSS/JavaScript with Chinese and English pages (Day, Night and Auto themes).

## Where to look

- Judge entry: `demo/guide-v4.html`
- Demo: `demo/skeleton-v4.html`
- Runtime: `skill/skeleton_v4/skeleton.py`
- Spec: `.kiro/specs/incident-skeleton-v4/`
