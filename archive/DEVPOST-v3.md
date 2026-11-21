# Incident Skeleton v3: the same skeleton, now with global intelligence

**Kiroween 2026 · Skeleton Crew · Version 3**

## Inspiration

Many people cannot sign in to Teams or Outlook. Tickets arrive from several sites. The usual response is local: reinstall Office, reset passwords, rebuild profiles. If Microsoft is having an incident, every one of those steps is wasted work, and some make things worse.

Version 1 patrols office equipment and triages service-desk requests. Version 2 learns from approved internal knowledge. Version 3 adds a third layer: it asks whether a problem that looks local is actually a vendor-wide or internet-wide outage.

`INTERNAL SIGNALS + VENDOR MCP + OFFICIAL STATUS + TRUSTED WEB → CORRELATE → DECIDE → HOLD → NOTIFY → RECHECK`

## One skeleton, three layers

Skeleton Crew is about a reusable bone structure with plug-in crews. Version 3 keeps that structure.

| Layer | Question | Version |
|---|---|---|
| Incident engine | What is broken here, and what is the safe fix? | v1 |
| Intelligence evolution | Has our guidance changed, and do our methods work? | v2 |
| Global intelligence | Is this really our problem, or the vendor's? | v3 |

The same shared incident engine, policy gates and dry-run notices carry all three layers. Version 3 adds new files and does not change Version 1 or 2.

## Business example 1: Microsoft Teams and Outlook

1. Teams and Outlook sign-in failures appear across several sites.
2. Microsoft Graph service health (or a Microsoft MCP) reports an active incident.
3. An official status source confirms degradation.
4. The engine returns `vendor_incident_confirmed` with a score that lists supporting and conflicting evidence.
5. Matching tickets are grouped under one parent incident.
6. Wasteful local actions, such as mass password resets and Office reinstalls, are held as recommendations. Safe read-only checks keep running.
7. A bilingual dry-run notice goes to IT on-call and the service desk. It cites the official source, states confidence, and tells users they need not report again.
8. The system rechecks until Microsoft reports recovery and internal sign-ins succeed. Then the board closes.

## Business example 2: Cisco single-site fault

Wireless failures appear at one site. Cisco Meraki status is healthy and no matching external outage exists. The engine returns `local_issue_likely` and keeps the local network crew path. Global intelligence does not take over local work when the vendor is fine.

## Decisions

`vendor_incident_confirmed`, `global_outage_likely`, `local_issue_likely`, `investigating`, `resolved`.

Recovery needs both vendor resolution and internal recovery. Conflicting evidence stays `investigating`.

## Evidence and trust

Strongest to weakest: authenticated vendor MCP or tenant health, official public status, internal multi-user pattern, trusted web report, public report.

- Public reports can support a conclusion but can never confirm an outage alone.
- Internet content is untrusted data. It never grants permission and never supplies commands. Instructions found in it are rejected.
- Held actions are recommendations. `policy.json` and people still decide real actions.

## Vendor connectors

Microsoft Graph service health needs only the least-privilege permission `ServiceHealth.Read.All` (read-only). Cisco Meraki MCP, Cisco Catalyst Center MCP, Cisco Security Cloud Control (SCC) MCP and Cisco PSIRT OpenVuln MCP are connectors that can be attached through the same normalized signal contract.

## Integration honesty

Version 3 is implemented and covered by 12 acceptance tests. It runs the Microsoft and Cisco stories through the real correlation engine, writes generated demo data, and renders the Global Intelligence Console. The current connectors remain samples and normalized contracts: no Microsoft tenant, Cisco account, or live vendor MCP is signed in. Connecting real systems needs explicit user sign-in, least privilege, and separate verification. All notices are bilingual and marked dry-run.

## Why it matters

The skeleton can now tell the service desk "this is Microsoft, not us" with cited evidence, stop busywork that cannot help, and still keep local fixes for local faults. It does this without new permissions for the AI.

## Built with

Kiro, Kiro Crew concepts, Python standard library, JSON data contracts, and vanilla HTML/CSS/JavaScript, with a Global Intelligence Console in Chinese and English.
