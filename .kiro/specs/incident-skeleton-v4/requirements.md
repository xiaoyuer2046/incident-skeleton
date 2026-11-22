# Incident Skeleton v4 — Requirements

> Final version for Kiroween 2026 · Skeleton Crew. v4 is the current version. v1, v2, v3 and v3.1 files remain unchanged as history.

## Why v4

A theme review of v3.1 found three problems:

1. The six-step skeleton is only a name both apps share. `run_incident.py` defines it, but neither app runs through it. App 1 calls the repair loop directly. App 2 and v3.1 hand-write six state strings.
2. The repository is not lean. Judges cannot tell which files are current.
3. Learning only reads company-internal sources. Vendor MCP servers and public internet information are used for outage checks, but never learned from.

## Requirement 1 — one shared skeleton runtime

**User story:** As a judge, I can open one file and see the six-step skeleton that both applications actually run through.

Acceptance criteria:

1. WHEN either application handles an item THEN it SHALL run through one shared runtime in `skill/skeleton_v4/skeleton.py`.
2. The runtime SHALL execute exactly six steps in order: RECEIVE, TRIAGE, INVESTIGATE, MITIGATE, RESOLVE, LOG.
3. Each application SHALL supply only an app adapter: intake, crew selection, crew INVESTIGATE, crew MITIGATE.
4. Plug-ins SHALL attach only to named slots: `triage_gate`, `mitigate_rank`, `log_learn`.
5. A plug-in or crew SHALL NOT add, remove or reorder steps.
6. WHEN a step short-circuits (rejected, linked to a known or vendor incident) THEN later steps SHALL still be recorded as "skipped" with a reason, so every record has six steps.
7. Adding a third app SHALL need only a new adapter file plus config. The runtime file SHALL not change. A test SHALL prove this with a tiny third adapter.

## Requirement 2 — two distinct applications on the runtime

1. App 1 office devices: patrol-confirmed faults for printer, signage, meeting-room AV and wireless AP. Crew work reuses v1 `remediate.py` through its public functions.
2. App 2 service desk L1: requests from people for account, VPN, email and software. Crew work reuses v1 `desk.py` checks and the shared repair loop.
3. Existing v1 behavior SHALL hold: admin and injection requests rejected; "no Wi-Fi on floor 4" linked to the known incident; L1 fixes; approval waits.
4. Teams and Outlook requests SHALL be recognized by the service desk adapter, even though v1 `app.json` has no Teams keyword.

## Requirement 3 — safety order

1. Safety rejection SHALL run first in TRIAGE, before any plug-in.
2. The global outage gate SHALL run second.
3. The v1 known-incident link SHALL run third.
4. Crew selection SHALL run last.

## Requirement 4 — learning from internal, vendor and internet sources

**User story:** As an IT lead, the AI should learn methods not only from our KB and tickets, but first from vendor MCP servers such as Microsoft, and from public internet information, then tell me what changed.

Learning sources and trust:

| Tier | Source | Examples | Weight |
|---|---|---|---|
| A | `vendor_mcp` | Microsoft MCP or Graph Message Center known issues, Cisco Meraki MCP, Cisco PSIRT advisories | 0.45 |
| A | `official_status` | vendor status pages and incident reports | 0.35 |
| B | `servicenow_kb`, `incident` | company KB, resolved tickets | 0.30 |
| B | `chat`, `email`, `shared_drive` | approved team channels, mailboxes, runbooks | 0.20 |
| C | `trusted_web` | vendor docs, recognized technical sites | 0.10 |
| D | `public_report` | forums, social posts, outage crowd reports | 0.04 |

Acceptance criteria:

1. Each learning cycle SHALL read vendor and official sources **before** internal and web sources.
2. A vendor known-issue workaround SHALL create a candidate method for a known action, for either app.
3. A Tier C or D source alone SHALL NOT create a usable candidate. It needs corroboration from Tier A or B.
4. A public report SHALL never promote or demote a method.
5. All external text SHALL pass injection checks. Instructions, commands, credentials and permission requests SHALL be rejected and recorded.
6. Unknown actions, and actions that belong to another device type, SHALL be rejected.
7. A vendor advisory that says a method is harmful or deprecated SHALL pause that method and notify people.
8. Learning SHALL cover both apps. App 2 methods (for example `send-outlook-steps`) SHALL be learnable.
9. Every change SHALL append an immutable `4.0.N` version. Earlier versions SHALL stay unchanged.
10. Every change SHALL create one bilingual dry-run notice naming the source tier, method, old state, new state and reason.
11. Unchanged sources SHALL create no new event or notice.

## Requirement 5 — permission invariant

1. Learning MAY narrow permission (pause a method in memory). It SHALL NEVER widen permission.
2. `policy.json` and the app `policy.json` SHALL remain the only permission sources.
3. A full run SHALL leave every `policy.json`, `actions.json` and `app.json` byte-identical.
4. Physical actions SHALL never become automatic.

## Requirement 6 — global outage gate

1. The gate SHALL reuse the v3 engine.
2. Under a confirmed or likely vendor incident, matching requests and Teams Rooms faults SHALL link to one vendor parent and hold useless actions (password reset, Office reinstall).
3. A Cisco single-site fault with a healthy vendor SHALL stay local.
4. Vendor recovery plus internal recovery SHALL close linked items with a bilingual dry-run notice.

## Requirement 7 — lean, clear repository

1. `VERSIONS.md` SHALL list the current files and the history files.
2. One judge entry page: `demo/guide-v4.html`.
3. One demo page: `demo/skeleton-v4.html`.
4. One Devpost text: `DEVPOST-v4.md` (now `DEVPOST.md`).
5. `README.md` SHALL point reviewers to v4 only.

## Requirement 8 — Kiro usage

1. This spec SHALL live in `.kiro/specs/incident-skeleton-v4/` as requirements, design and tasks.
2. A cross-platform Python audit hook SHALL exist next to the old shell hook.
3. The steering file and agents SHALL stay valid.

## Requirement 9 — honesty

1. Everything SHALL be dry run with simulated data.
2. Pages and docs SHALL say Microsoft, Cisco and live internet connectors are not signed in.
3. No dry-run result SHALL be described as a real repair.
