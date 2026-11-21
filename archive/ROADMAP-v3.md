# Roadmap v3: Global Intelligence

> New version. ROADMAP.md and ROADMAP-v2.md remain unchanged.

Theme: the same Skeleton Crew backbone extended to a third layer, global outage intelligence.

## Now: implemented in simulated dry-run

- Normalized signal contract (internal, vendor_mcp, official_status, trusted_web, public_report).
- Signal fingerprints so unchanged signals create no duplicate notices.
- Scoring with supporting and conflicting evidence.
- Five decisions: `vendor_incident_confirmed`, `global_outage_likely`, `local_issue_likely`, `investigating`, `resolved`.
- Held-action recommendations, bilingual dry-run notices, immutable `3.0.N` patterns.
- Microsoft (Teams/Outlook) and Cisco (single-site Wi-Fi) sample stories.
- Global Intelligence Console demo in Chinese and English, Day/Night/Auto, labelled simulated.
- 12 acceptance tests from SPEC-v3-global-intelligence.md.

No real vendor system is signed in at this stage.

## Next: read-only connectors, one at a time

1. Microsoft Graph service health, permission `ServiceHealth.Read.All` only. Requires explicit admin consent and separate verification.
2. Official status pages as read-only sources.
3. Cisco Meraki MCP.
4. Cisco Catalyst Center MCP.
5. Cisco Security Cloud Control (SCC) MCP.
6. Cisco PSIRT OpenVuln MCP.

Each connector needs user sign-in, least privilege and a verification run before it counts as live.

## Later

- Source reliability tuning from resolved incidents.
- More providers through the same contract.
- ServiceNow parent-incident grouping after the ServiceNow connector is verified.
- Real notification channels after approval. Notices stay dry-run until then.

## Rules that do not change

- Internet content is untrusted data and public reports never decide alone.
- Held actions are advice. `policy.json` and people decide real actions.
- Earlier versions are never overwritten.
