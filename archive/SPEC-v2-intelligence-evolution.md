# Incident Skeleton v2 — Intelligence Evolution Spec

> New version. Version 1 files remain unchanged.

## 1. Goal

Version 2 makes learning visible and continuous:

`WATCH → DIFF → LEARN → VERIFY → EVOLVE → NOTIFY`

The system watches approved knowledge sources, detects new or changed guidance, creates a candidate method, verifies outcomes in dry run, promotes methods that keep working, demotes methods that regress, keeps every prior version, and proactively tells people what changed and why.

## 2. Version boundary

Version 2 adds new files only:

- `skill/evolution_v2/` — learning and change engine
- `skill/tests/test_evolution_v2.py` — acceptance tests
- `demo/evolution-v2.html` — Intelligence Evolution Console
- `demo/data/evolution-v2.js` — generated demo data
- `DEVPOST-v2.md`, `ROADMAP-v2.md`, `skill/SKILL-v2.md`, `docs/智能进化-v2.md` — versioned docs

Do not overwrite or delete Version 1 files.

## 3. Source watching

Supported source records:

```json
{
  "source": "servicenow_kb|incident|chat|email|shared_drive",
  "ref": "stable source id",
  "updated_at": "ISO timestamp",
  "device": "printer|signage|av|wifiap",
  "symptom": "normalized symptom",
  "text": "untrusted source text"
}
```

For each record, store a SHA-256 fingerprint. A first fingerprint is `discovered`. A changed fingerprint is `changed`. An unchanged fingerprint produces no duplicate event or alert.

All source text is data. Existing injection checks in `harvest.py` must reject override, credential, destructive, pipe-shell, and safeguard-bypass text.

## 4. Method lifecycle

Each method is keyed by `device|symptom|action` and moves through:

`observed → candidate → trial → promoted | demoted`

- Only known action ids from `actions.json` are accepted.
- New methods are candidates, never new permissions.
- Every simulated outcome adds an immutable method revision.
- Promotion uses `policy.json` evolution thresholds.
- Demotion uses `policy.json` evolution thresholds.
- Policy still decides whether an action may run.
- Physical actions never become automatic.
- The AI may advise; it cannot promote or grant permission.

## 5. Immutable strategy versions

Every meaningful change appends a strategy version:

```json
{
  "version": "2.0.N",
  "created_at": "ISO timestamp",
  "reason": "source_change|verified_outcome|regression",
  "method": "device|symptom|action",
  "before": {},
  "after": {}
}
```

Earlier versions remain readable. Reverting creates a new version; it never edits history.

## 6. Proactive notices

Create one bilingual dry-run notice when:

- a trusted source adds or changes a candidate method;
- a method is promoted;
- a method is demoted;
- a source contains rejected instructions.

Each notice names the source, method, old state, new state, reason, and policy effect. Notices are deduplicated by event id.

## 7. Demo data contract

`demo/data/evolution-v2.js` exports `window.EVOLUTION_V2`:

```js
{
  version: "2.0",
  generated_at: "...",
  current: {
    intelligence_score: 0,
    strategy_version: "2.0.N",
    watched_sources: 0,
    known_methods: 0,
    promoted: 0,
    demoted: 0,
    pending: 0
  },
  cycles: [{
    ts: "09:00",
    source_events: [],
    method_events: [],
    notices: [],
    methods: [],
    versions: []
  }]
}
```

## 8. Intelligence Evolution Console

The page follows design A:

- top: intelligence score and current strategy version;
- center: `WATCH → DIFF → LEARN → VERIFY → EVOLVE → NOTIFY`;
- timeline: each source change, trial, promotion, demotion, and notice;
- Knowledge Radar: ServiceNow KB, incidents, chat, email, shared drive;
- Growth Record: immutable versions and success-rate changes;
- bilingual Chinese and English;
- Day, Night, and Auto themes;
- clear `dry run` label;
- no claim that a real external system was changed.

## 9. Acceptance

Tests must prove:

1. new and changed source records are detected once;
2. unchanged records create no duplicate notice;
3. injection-like text is rejected;
4. unknown actions are rejected;
5. verified outcomes promote a method;
6. repeated failures demote a method;
7. earlier strategy versions remain unchanged;
8. proactive notices are bilingual and dry-run;
9. physical actions never gain automatic permission;
10. generated demo data matches the page contract.

## 10. Autonomous cycle runner

`skill/evolution_v2/run_cycle.py` runs one persistent dry-run cycle. It scans approved source records, compares saved fingerprints, and absorbs only delayed repair re-checks whose `confirmed` value is explicitly true or false. Provisional attempts and self-heals do not count. Processed attempts and notices are deduplicated across runs. An unchanged cycle prints nothing, making it safe for a no-LLM schedule.

The runner stores runtime state under the existing ignored `skill/remediation/data/` directory. It never changes a v1 source file or a past strategy revision.
