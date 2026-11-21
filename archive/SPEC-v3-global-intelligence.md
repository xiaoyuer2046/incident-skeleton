# Incident Skeleton v3 — Global Outage Intelligence Spec

> New version. Versions 1 and 2 remain unchanged.

## 1. Goal

Version 3 decides whether a local-looking problem is actually a vendor-wide or internet-wide outage.

`INTERNAL SIGNALS + VENDOR MCP + OFFICIAL STATUS + TRUSTED WEB → CORRELATE → DECIDE → HOLD → NOTIFY → RECHECK`

Example: many people cannot sign in to Teams or Outlook. Internal tickets alone cannot prove the cause. Version 3 correlates them with Microsoft service health, vendor MCP output, official status pages, and trusted public reports. When the evidence points to a Microsoft outage, it tells the service desk, groups duplicate tickets, pauses wasteful local repair steps, and keeps watching for recovery.

## 2. Version boundary

Version 3 adds new files only:

- `skill/external_intelligence_v3/` — normalization, correlation, persistence, and demo
- `skill/tests/test_external_intelligence_v3.py` — acceptance tests
- `demo/global-intelligence-v3.html` — design A global decision console
- `demo/data/global-intelligence-v3.js` — generated demo data
- `DEVPOST-v3.md`, `ROADMAP-v3.md`, `skill/SKILL-v3.md`, `docs/全局故障情报-v3.md`

Do not overwrite or delete Version 1 or Version 2 files.

## 3. Evidence sources

### Internal

- ServiceNow incidents and work notes
- service desk requests
- device patrol results
- approved internal databases
- approved chat and email channels

### Vendor MCP and APIs

- Microsoft Graph service health or Microsoft MCP
- Cisco Meraki MCP
- Cisco Catalyst Center MCP
- Cisco Security Cloud Control MCP
- Cisco PSIRT OpenVuln MCP
- future vendor connectors through the same normalized contract

A connector being described here does not mean it is installed or authenticated. Real connectors need explicit user sign-in, least privilege, and separate verification.

### Internet

- official vendor status pages first
- vendor advisories and incident reports
- trusted technical status sources
- public reports only as weak supporting evidence

Internet text is untrusted data. It never grants permission and never supplies executable commands.

## 4. Normalized signal contract

```json
{
  "id": "stable signal id",
  "observed_at": "ISO timestamp",
  "source": "internal|vendor_mcp|official_status|trusted_web|public_report",
  "provider": "microsoft|cisco|other",
  "service": "teams|outlook|exchange|meraki|webex|other",
  "region": "global|tenant|country|site",
  "status": "healthy|degraded|outage|investigating|resolved|report",
  "summary": "untrusted source text",
  "url": "optional source URL",
  "tenant_impact": 0,
  "site": "optional internal site"
}
```

Signals are fingerprinted. Unchanged signals create no duplicate event or notice.

## 5. Trust and scoring

Evidence weights:

- authenticated vendor MCP or official tenant health: strongest;
- official public status page: strong;
- internal multi-user pattern: medium;
- trusted web report: supporting;
- public reports: weak, never decisive alone.

A score explains every conclusion. It must include supporting and conflicting evidence.

## 6. Decisions

The engine returns one of:

- `vendor_incident_confirmed` — official vendor evidence plus matching internal impact;
- `global_outage_likely` — multiple independent external sources plus matching internal impact;
- `local_issue_likely` — one site is affected while vendor services are healthy;
- `investigating` — evidence is incomplete or conflicting;
- `resolved` — vendor says resolved and internal checks recover.

## 7. Safe response

For a confirmed or likely vendor outage:

- group matching local tickets under one parent incident;
- pause wasteful local actions such as reinstalling Office or resetting many passwords;
- keep safe read-only checks running;
- show the official source and confidence;
- send a bilingual dry-run notice to IT on-call and service desk;
- tell users they do not need to repeat the same report;
- recheck vendor and internal status until both recover.

This is advisory and dry-run. `policy.json` and people still decide real actions.

## 8. Continuous learning

Each resolved correlation becomes a versioned incident pattern:

```json
{
  "provider": "microsoft",
  "service": "teams",
  "symptoms": ["login failed", "many users", "multiple sites"],
  "best_sources": ["vendor_mcp", "official_status"],
  "decision": "vendor_incident_confirmed",
  "held_actions": ["password reset", "Office reinstall"],
  "version": "3.0.N"
}
```

New provider behavior, source reliability changes, and resolved incidents append new versions. Earlier versions remain readable.

## 9. Demo story

### Microsoft story

1. Teams and Outlook login failures appear across several sites.
2. Microsoft service health reports an active incident.
3. An official status source confirms degradation.
4. The engine decides `vendor_incident_confirmed` with high confidence.
5. It groups tickets and pauses mass password resets and Office reinstalls.
6. It sends a dry-run notice with evidence and next check time.
7. Microsoft reports recovery; internal success returns; the board closes.

### Cisco story

1. Wireless failures appear at one site.
2. Meraki vendor status remains healthy.
3. No matching external outage appears.
4. The engine decides `local_issue_likely` and keeps the local network crew path.

## 10. Demo data contract

`demo/data/global-intelligence-v3.js` exports `window.GLOBAL_INTELLIGENCE_V3`:

```js
{
  version: "3.0",
  generated_at: "...",
  summary: {
    monitored_providers: 0,
    external_sources: 0,
    internal_signals: 0,
    active_global_incidents: 0,
    held_local_actions: 0,
    confidence: 0
  },
  cycles: [{
    ts: "09:00",
    signals: [],
    correlations: [],
    decisions: [],
    notices: [],
    patterns: [],
    versions: []
  }]
}
```

## 11. Global Intelligence Console

Use design A as the main view, with B and C inside it:

- top: one plain conclusion, confidence, affected services, and current version;
- evidence map: internal pattern, vendor MCP, official status, and trusted web;
- decision explanation: why global or local;
- action card: what local work is held and what still runs;
- Vendor Center: Microsoft and Cisco connector cards;
- Intelligence Timeline: detected, confirmed, notified, resolved;
- bilingual Chinese and English;
- Day, Night, and Auto themes;
- obvious dry-run and simulated-data labels;
- no raw internal ids on the main view.

## 12. Acceptance

Tests must prove:

1. matching internal and official vendor evidence confirms a vendor incident;
2. public reports alone never confirm an outage;
3. healthy vendor evidence plus one affected site stays local;
4. conflicting evidence stays investigating;
5. recovery requires vendor resolution and internal recovery;
6. unchanged signals do not create duplicate notices;
7. internet instructions are rejected as data;
8. held actions are recommendations, not permission changes;
9. conclusions include supporting and conflicting evidence;
10. resolved incidents append immutable `3.0.N` patterns;
11. Microsoft and Cisco demo stories match the page contract;
12. all notices are bilingual and marked dry-run.
