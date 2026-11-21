"""Incident Skeleton v4: THE shared six-step runtime. Both apps run through `run()`.

No app-specific logic lives here. An app supplies an adapter; plug-ins attach
only to three named slots. Nobody can add, remove or reorder the six steps.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

STEPS = ("RECEIVE", "TRIAGE", "INVESTIGATE", "MITIGATE", "RESOLVE", "LOG")
KIND = {"RECEIVE": "shared", "TRIAGE": "shared", "INVESTIGATE": "crew", "MITIGATE": "crew", "RESOLVE": "shared", "LOG": "shared"}
SLOTS = ("triage_gate", "mitigate_rank", "log_learn")
OUTCOMES = ("rejected", "linked_vendor", "linked_known", "resolved", "escalated", "on_hold", "local_repair")


class Stop:
    """Ends TRIAGE early. `en`/`zh` is the TRIAGE text; `notes` maps a later step to its own skip reason."""

    def __init__(self, outcome: str, en: str, zh: str, parent=None, held=(), notes=None, **meta: Any) -> None:
        assert outcome in OUTCOMES, outcome
        self.outcome, self.en, self.zh, self.parent = outcome, en, zh, parent
        self.held, self.notes, self.meta = list(held), dict(notes or {}), meta


@contextmanager
def narrowed(ctx: Any, narrow: Dict[str, List[str]]):
    """Remove actions from an in-memory copy of ctx.policy['allow'] for one call. Can only remove."""
    original = ctx.policy
    pol = copy.deepcopy(original)
    for crew, base in original.get("allow", {}).items():
        gone = set(narrow.get(crew, [])) | set(narrow.get("*", []))
        pol["allow"][crew] = [a for a in base if a not in gone]
        assert set(pol["allow"][crew]) <= set(base), "learning may only narrow permission"
    ctx.policy = pol
    try:
        yield pol
    finally:
        ctx.policy = original


def _step(name: str, body: Dict[str, Any], slot: Optional[str] = None, status: str = "done") -> Dict[str, Any]:
    assert body.get("en") and body.get("zh"), "every step needs English and Chinese text: " + name
    return {"name": name, "kind": KIND[name], "status": status, "slot": slot, "en": body["en"], "zh": body["zh"]}


def run(item: Dict[str, Any], adapter: Any, plugins: Optional[Dict[str, Any]], ctx: Any) -> Dict[str, Any]:
    plugins = plugins or {}
    unknown = set(plugins) - set(SLOTS)
    if unknown:
        raise ValueError("plug-ins attach only to %s, not %s" % (SLOTS, sorted(unknown)))
    steps = [_step("RECEIVE", adapter.receive(item, ctx))]
    title = item.get("title") or {"en": str(item.get("id")), "zh": str(item.get("id"))}
    rec = {"app": adapter.app, "label": title, "outcome": None, "crew": None, "steps": steps, "held_actions": [],
           "parent": None, "learning_used": [], "dry_run": True}

    # TRIAGE: 1 safety, 2 triage_gate, 3 known link, 4 crew
    slot, note, crew = None, None, None
    stop = adapter.safety(item, ctx)
    if not stop and plugins.get("triage_gate"):
        got = plugins["triage_gate"](item, ctx)
        slot = "triage_gate" if got else None
        stop, note = (got, None) if isinstance(got, Stop) else (None, got)
    stop = stop or adapter.known_link(item, ctx)
    if not stop:
        crew = adapter.select_crew(item, ctx)
        stop = crew if isinstance(crew, Stop) else None
    if stop:
        pre = note or {"en": "", "zh": ""}
        steps.append(_step("TRIAGE", {"en": (pre["en"] + " " + stop.en).strip(), "zh": pre["zh"] + stop.zh}, slot))
        for name in STEPS[2:]:
            why = stop.notes.get(name) or {"en": "Skipped: " + stop.en, "zh": "已跳过：" + stop.zh}
            steps.append(_step(name, why, status="skipped"))
        rec.update(outcome=stop.outcome, parent=stop.parent, held_actions=stop.held)
        if hasattr(adapter, "on_stop"):
            adapter.on_stop(item, stop, ctx)
        return rec
    label = adapter.crews[crew]
    tri = {"en": "%s crew." % label["en"], "zh": "%s班底。" % label["zh"]}
    if note:
        tri = {"en": note["en"] + " " + tri["en"], "zh": note["zh"] + tri["zh"]}
    steps.append(_step("TRIAGE", tri, slot))
    rec["crew"] = crew

    steps.append(_step("INVESTIGATE", adapter.investigate(item, crew, ctx)))
    plan = plugins["mitigate_rank"](item, crew, ctx) if plugins.get("mitigate_rank") else {}
    plan = {"hints": {}, "narrow": {}, "notes": [], **(plan or {})}
    with narrowed(ctx, plan["narrow"]):
        result = adapter.mitigate(item, crew, plan, ctx)
    steps.append(_step("MITIGATE", result, "mitigate_rank" if (plan["hints"] or plan["narrow"]) else None))
    rec["learning_used"] = plan["notes"]
    steps.append(_step("RESOLVE", adapter.resolve(item, result, ctx)))
    log, learned = adapter.log(item, result, ctx), None
    if plugins.get("log_learn"):
        learned = plugins["log_learn"](item, result, ctx)
        if learned:
            log = {"en": log["en"] + " " + learned["en"], "zh": log["zh"] + learned["zh"]}
    steps.append(_step("LOG", log, "log_learn" if learned else None))
    rec["outcome"] = result.get("outcome", "escalated")
    assert rec["outcome"] in OUTCOMES and [s["name"] for s in steps] == list(STEPS)
    return rec
