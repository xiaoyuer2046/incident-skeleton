# Incident Skeleton v5: design

```
connectors_v5.json ──► connectors.Registry ──► sync ──► merge ──► parents
news_v5.json ───────► news.consensus ─────────────────────────► "likely" / "confirmed"
learning (v4) ──────► permissions.PermissionBook ──► proposal ──► person ──► standing approval
                                    │
items ──► skeleton_v4.skeleton.run(item, adapter_v5, plugins_v5, ctx)
             RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
                         ▲                      ▲                  ▲
                 triage_gate (v4 gate,   mitigate_rank (v4 ranking,  log_learn
                 then news check)        grants, meeting window)     (v4)
```

| File | Job |
|---|---|
| `skill/skeleton_v5/rules_v5.json` | the owner's rules; read only |
| `skill/skeleton_v5/connectors.py` | connectors, health, sync, merge |
| `skill/skeleton_v5/news.py` | independent-report count and level |
| `skill/skeleton_v5/permissions.py` | proposals, approver check, expiry, revoke, versions |
| `skill/skeleton_v5/plugins_v5.py` | wraps the v4 slots |
| `skill/skeleton_v5/adapters_v5.py` | v4 adapters plus grants and meeting hold |
| `skill/skeleton_v5/run.py` | the dry-run morning and the numbers |

## Decisions
- **News level is separate from the v3 gate.** The v3 gate still decides "confirmed" and holds. The news check only adds "likely" when the gate does not link. That keeps the official path unchanged.
- **"Likely" does not hold repairs by default.** The owner asked for work to continue while the AI checks the news. `likely_holds` lets the owner change that.
- **Widening reuses the v1 `approvals` map.** No change to the repair loop and no write to any permission file.
- **One step only.** A proposal moves an action from "approval each time" to "standing approval". It never adds an action to the allow-list.
- **Connectors are data.** The generic connector covers every system in the demo; a real system would replace `pull()` behind the same shape.
