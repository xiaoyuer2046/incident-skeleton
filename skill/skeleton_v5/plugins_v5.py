"""v5 plug-ins. Same three slots as v4; each v5 slot wraps the v4 one and adds one rule.

triage_gate    v4 global gate first (an official vendor incident still links and holds). If it does not link, the v5 news
               check runs: enough independent reports -> a "likely vendor outage" note, the ticket is told, local work continues.
mitigate_rank  v4 ranking and pauses, plus: a person's standing approval for this exact crew and symptom; the meeting window
               (risky actions wait while a working meeting is on); optional holds while an outage is only likely.
log_learn      unchanged from v4.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from . import SKILL  # noqa: F401
import remediate as rm  # noqa: E402
from integration_v31.plugins import LABELS, detect_service  # noqa: E402
from skeleton_v4 import plugins as v4  # noqa: E402
from skeleton_v4.skeleton import Stop  # noqa: E402

from . import news as N


def _join(a: Optional[Dict[str, str]], b: Dict[str, str]) -> Dict[str, str]:
    return {"en": (a["en"] + " " + b["en"]).strip(), "zh": a["zh"] + b["zh"]} if a else b


def build(gate: Any, learning: Any, app: str, news_view: Optional[Callable] = None, book: Any = None,
          rules: Optional[Dict[str, Any]] = None) -> Dict[str, Callable]:
    rules = rules or {}
    base = v4.build(gate, learning, app)
    slots = dict(base)
    v4_gate, v4_rank = base.get("triage_gate"), base.get("mitigate_rank")

    def triage_gate(item: Dict[str, Any], ctx: Any):
        got = v4_gate(item, ctx) if v4_gate else None
        if isinstance(got, Stop) or news_view is None:
            return got
        found = detect_service(item["text"])
        c = news_view(*found) if found else None
        if not c or c["level"] != "likely":
            return got
        item["_news"] = c
        return _join(got, N.note(c, LABELS[found]))

    def mitigate_rank(item: Dict[str, Any], crew: str, ctx: Any) -> Dict[str, Any]:
        plan = v4_rank(item, crew, ctx) if v4_rank else {}
        plan = {"hints": {}, "narrow": {}, "notes": [], **(plan or {})}
        if book is not None:
            grants = book.standing(app, crew, rm.symptom_key(crew, item["text"]))
            if grants:
                plan["approvals"] = grants
                for aid, why in grants.items():
                    plan["notes"].append({"en": "Runs under a person's standing approval: %s (%s)." % (ctx.actions[aid]["en"], why),
                                          "zh": "按人已批准的长期授权执行：%s（%s）。" % (ctx.actions[aid]["zh"], why), "tier": "-"})
        meet = item.get("meeting")
        if meet and not meet.get("blocked"):
            risky = set(rules.get("meeting_window", {}).get("defer_risks", ["medium", "high"]))
            defer = [a for a in ctx.policy.get("allow", {}).get(crew, []) if ctx.actions[a]["risk"] in risky]
            if defer:
                plan["narrow"][crew] = sorted(set(plan["narrow"].get(crew, [])) | set(defer))
                plan["deferred"] = {"actions": defer, "until": meet["until"]}
                plan["notes"].append({"en": "Meeting on until %s: risky steps wait." % meet["until"],
                                      "zh": "会议进行到 %s：有风险的步骤先等。" % meet["until"], "tier": "-"})
        holds = rules.get("news_consensus", {}).get("likely_holds", [])
        if item.get("_news") and holds:
            plan["narrow"]["*"] = sorted(set(plan["narrow"].get("*", [])) | set(holds))
        return plan

    slots["triage_gate"] = triage_gate
    slots["mitigate_rank"] = mitigate_rank
    return slots
