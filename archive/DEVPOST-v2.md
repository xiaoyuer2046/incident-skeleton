# Incident Skeleton v2: a skeleton that keeps learning

**Kiroween 2026 · Skeleton Crew · Version 2**

## Inspiration

Operations teams rarely lack runbooks. They struggle to notice when guidance changes, determine whether a new fix actually works, and prevent an old recommendation from quietly getting worse.

Incident Skeleton already runs proactively: it patrols office equipment, confirms faults, applies policy gates, ranks known fixes, verifies outcomes, tracks incidents, and notifies people in dry run. Version 2 extends that active system with a visible, continuous intelligence loop:

`WATCH → DIFF → LEARN → VERIFY → EVOLVE → NOTIFY`

## Two applications, one skeleton

The shared six-state incident engine powers exactly two applications:

| Application | Intake | Domain crews |
|---|---|---|
| Office-device proactive patrol | Machine health probes | Printer, digital signage, meeting-room AV, wireless AP |
| Service-desk L1 triage | Requests from people | Account, VPN, email, software |

The four office-device crews are plug-ins inside the first application, not four separate applications. The service desk can link a person's report to an office-device incident that patrol has already found, avoiding duplicate diagnosis and dispatch.

## What Version 2 adds

Version 2 watches approved knowledge records from ServiceNow KB, resolved incidents, chat, email, and shared drives. Each record receives a stable identity and SHA-256 fingerprint. A new fingerprint creates a `discovered` event, a changed fingerprint creates a `changed` event, and an unchanged record creates nothing.

A source change can produce a candidate method only when it maps to a known action. The method then follows an explicit lifecycle:

`observed → candidate → trial → promoted | demoted`

Dry-run outcomes update the method's success evidence. Policy thresholds decide promotion and demotion. Every meaningful transition appends an immutable strategy version, so operators can inspect what changed, why it changed, and what the previous strategy contained. Reverting also appends a version instead of rewriting history.

The system proactively creates one bilingual, deduplicated dry-run notice when a source changes, a method is promoted or demoted, or hostile instructions are rejected. Each notice states the source, method, old and new state, reason, and policy effect.

## Safety model

AI is advisory only. It may summarize evidence, normalize symptoms, or suggest a known action. It cannot add an action, promote a method, change a risk tier, grant permission, or bypass approval.

`policy.json` remains the authority. Every candidate still passes the device allow-list, risk tier, approval rules, attempt limits, cooldowns, and kill switch. Physical actions never become automatic. A higher success rate changes ranking, not permission.

All KB, incident, chat, email, and shared-drive text is untrusted data. Existing injection checks reject override requests, credential requests, destructive instructions, shell-pipe payloads, and attempts to bypass safeguards.

## What is implemented today

The existing project contains the active six-state engine, proactive office-device patrol, service-desk L1 intake, policy gates, dry-run remediation, outcome scoring, case-library logic, incident tracking, notifications, and simulated demos. Real read-only probes include ping, curl, and optional SNMP.

Version 2 is implemented in `skill/evolution_v2/`. Its real engine detects source changes, creates policy-bound candidate methods, absorbs confirmed delayed re-checks, promotes or demotes methods, appends immutable `2.0.N` strategy versions, and emits bilingual proactive notices. A persistent no-LLM runner stays quiet when nothing changes. Fourteen v2 tests pass. `demo/evolution-v2.html` presents the generated four-cycle evolution story from `demo/data/evolution-v2.js`.

## Integration honesty

ServiceNow payload and REST paths exist in the earlier system, but they have not been validated against a live ServiceNow instance. Teams and email use sample data or dry-run outboxes; their live connectors are not wired. The PostToolUse audit Hook is supplied as a script and installation recipe, not installed automatically. Version 2 source watching therefore begins with approved sample or local records until each connector is integrated and tested.

No demo result means that an external system changed. No dry-run repair is reported as a real repair.

## Why it matters

The skeleton now has a path from reusable incident handling to governed operational learning. It does not merely collect more text. It detects source changes, tests candidate methods, measures outcomes, preserves strategy history, and tells people when its recommendation changed. People retain authority while the system keeps improving its evidence.

## Built with

Kiro, Kiro Crew concepts, Python standard library, JSON policy and data contracts, and vanilla HTML/CSS/JavaScript. Version 2 includes a tested intelligence-evolution engine, immutable strategy history, generated demo data, and a bilingual Intelligence Evolution Console.