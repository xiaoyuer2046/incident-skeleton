# Incident Skeleton v5: requirements

v5 keeps the v4 runtime (`skill/skeleton_v4/skeleton.py`) unchanged and adds the owner's rules in `skill/skeleton_v5/rules_v5.json`.
Everything runs as a dry run on simulated data.

## R1 Access layer
- R1.1 Each managed system (ServiceNow, AP controller, meeting-room manager, signage CMS, print manager) is a connector with declared scopes.
- R1.2 A new system is one entry in `connectors_v5.json`; no code change.
- R1.3 A connector names the environment variable that holds its secret. The dry run never reads it. No secret value is in the repo.
- R1.4 Each round checks every connector's health. A system that does not answer is skipped and the admin is told.

## R2 Merge across systems
- R2.1 Open items about the same service, seen in at least `min_systems` systems within `window_minutes`, become one parent.
- R2.2 Open items about the same device, from any systems, within the window, become one parent.
- R2.3 A single item is never merged.

## R3 News consensus
- R3.1 When at least `min_independent_sources` independent websites report a vendor outage within the window, the result is "likely vendor outage", even with no official word.
- R3.2 One vote per website. A repost of a headline already counted counts once. Old reports do not count.
- R3.3 A report whose text gives orders is dropped and never followed.
- R3.4 An official status page or vendor MCP report makes it "confirmed"; the v4 gate then links and holds as before.
- R3.5 On "likely", affected people are told at once, with the sources, and local work continues. Optional holds are set by the owner (`likely_holds`).

## R4 Permission growth
- R4.1 Learning still narrows by itself (v4).
- R4.2 Learning may propose a standing approval for one approval-tier action, one app, one crew and one symptom, when it has at least `min_successes` confirmed successes at `min_rate`.
- R4.3 Only an approver listed for that crew can approve, decline or revoke. Anyone else is refused and logged.
- R4.4 Physical actions and actions in `never_widen` (identity and access) are refused by rule.
- R4.5 A grant expires after `grant_days`. Every proposal, decision and revoke appends a version.
- R4.6 Nothing writes `policy.json`, `actions.json` or `approvals.json`. A grant is passed to the v1 repair loop as its `approvals` map for one call.

## R5 Safe operation
- R5.1 While a room is in a meeting that still works, risky actions (`defer_risks`) wait until the meeting ends; the ticket is on hold.
- R5.2 The v1 kill switch (STOP file or `kill_switch`) still stops every repair.

## R6 Numbers
- R6.1 Each run reports: systems and health, items synced, merged groups, duplicates avoided, alert minutes before the official notice, people told early, items done by AI, waiting, linked, sent to people, useless fixes held, grants, items per site, and an estimate of minutes saved (labelled an estimate).

## R7 Skeleton
- R7.1 `skeleton.py` is not edited. v5 plugs into the same three slots and uses v4 adapters as base classes.
- R7.2 Every item still walks the same six steps.
