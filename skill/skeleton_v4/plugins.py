"""Incident Skeleton v4 plug-ins. They attach only to the three named slots of skeleton.py.

triage_gate    v3 global outage gate (reused through the v3.1 wrapper): link to a vendor parent, hold useless actions.
mitigate_rank  adopted learned methods become hints; paused methods are removed from an in-memory allow-list copy.
log_learn      a confirmed delayed re-check teaches the v4 learning engine. A provisional result teaches nothing.

Nothing here writes policy.json, actions.json or app.json.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from . import SKILL  # noqa: F401
import remediate as rm  # noqa: E402
import desk  # noqa: E402,F401  (registers the service-desk symptoms with the shared classifier)
from integration_v31.plugins import GlobalGate, VERDICT_EN  # noqa: E402

from .learning import Learning, STATE  # noqa: E402
from .skeleton import Stop  # noqa: E402

VERDICT_ZH = {"local_issue_likely": "只有一个站点受影响，厂商正常，按本地问题处理", "investigating": "厂商未确认故障，走正常流程",
              "resolved": "厂商已恢复，走正常流程"}


def _labels(ctx: Any, ids: List[str]) -> Dict[str, str]:
    known = [a for a in ids if a in ctx.actions]
    return {"en": ", ".join(ctx.actions[a]["en"] for a in known) or "none", "zh": "、".join(ctx.actions[a]["zh"] for a in known) or "无"}


def make_triage_gate(gate: GlobalGate) -> Callable:
    def triage_gate(item: Dict[str, Any], ctx: Any):
        svc = gate.check(item["text"])
        if not svc:
            return None
        item["_gate"] = svc
        lab, pct = svc["label"], int(round(svc["confidence"] * 100))
        if not svc["link"]:
            if not svc["evidence"]:
                return None
            d = svc["decision"]
            return {"en": "Global gate: %s: %s." % (lab["en"], VERDICT_EN.get(d, d)),
                    "zh": "全局闸门：%s：%s。" % (lab["zh"], VERDICT_ZH.get(d, d))}
        allow = ctx.policy.get("allow", {})
        held_ids = sorted(allow.get(item.get("type"), [])) if item.get("type") in allow else list(svc["held_ids"])
        held = [{"en": ctx.actions[a]["en"], "zh": ctx.actions[a]["zh"]} for a in held_ids if a in ctx.actions]
        hl = _labels(ctx, held_ids)
        return Stop(
            "linked_vendor",
            "Global gate: %s vendor incident (confidence %d%%). Linked to it. No crew runs." % (lab["en"], pct),
            "全局闸门：%s 厂商故障（置信度 %d%%）。已挂到它下面，不派班底。" % (lab["zh"], pct),
            parent={"en": "%s vendor incident" % lab["en"], "zh": "%s 厂商故障" % lab["zh"]}, held=held,
            notes={"INVESTIGATE": {"en": "Skipped: the vendor is already investigating.", "zh": "已跳过：厂商已经在排查。"},
                   "MITIGATE": {"en": "Held while the vendor incident is active: %s." % hl["en"], "zh": "厂商故障期间暂停：%s。" % hl["zh"]},
                   "RESOLVE": {"en": "Waiting for %s to recover; this item closes by itself." % lab["en"], "zh": "等待 %s 恢复，恢复后自动关闭。" % lab["zh"]},
                   "LOG": {"en": "Ticket kept on hold as a child of the vendor incident.", "zh": "工单保持挂起，挂在厂商故障下。"}},
            svc=svc, held_ids=held_ids, pct=pct)
    return triage_gate


def hold_ticket(ctx: Any, key: str, fields: Dict[str, Any], stop: Stop, app: str, who: Dict[str, str]) -> str:
    """Shared ticket side effect of a vendor link, so both adapters close the same way when the vendor recovers."""
    svc = stop.meta["svc"]
    data = {"vendor": svc["key"], "parent": svc["parent_id"], "decision": svc["decision"], "held": stop.meta["held_ids"]}
    num, _ = rm.ticket_upsert(ctx, key, dict(fields, device="vendor-linked"), "linked_vendor", data,
                              extra={"parent_incident": svc["parent_id"], "vendor_key": svc["key"], "app": app,
                                     "caller_zh": who["zh"], "who_en": who["en"], "who_zh": who["zh"]})
    rm.ticket_update(ctx, key, rm.AUTOMATION, "linked_vendor", data, keep_state=True, state="On Hold",
                     hold_reason="Linked to vendor incident %s" % svc["parent_id"])
    return num


def make_mitigate_rank(learning: Learning, app: str) -> Callable:
    def mitigate_rank(item: Dict[str, Any], crew: str, ctx: Any) -> Dict[str, Any]:
        view = learning.view(app, crew, rm.symptom_key(crew, item["text"]))
        notes, narrow = [], {}
        for aid, method in view["hints"].items():
            act, tier = ctx.actions[aid], learning.best_tier(method)
            notes.append({"en": "Learned method tried first: %s (source tier %s)." % (act["en"], tier),
                          "zh": "优先尝试学到的方法：%s（来源 %s 级）。" % (act["zh"], tier), "tier": tier})
        for aid in view["paused"]:
            act = ctx.actions[aid]
            method = next(m for m in learning.methods.values() if m["app"] == app and m["device"] == crew and m["action"] == aid)
            src = next((s for s in method["sources"] if s["tier"] == "A"), method["sources"][0] if method["sources"] else None)
            by = src["label"] if src else {"en": "a source", "zh": "某来源"}
            notes.append({"en": "Paused for this call, removed from the allowed list: %s (%s)." % (act["en"], by["en"]),
                          "zh": "本次已暂停，已从允许列表移除：%s（%s）。" % (act["zh"], by["zh"]), "tier": learning.best_tier(method)})
        if view["paused"]:
            narrow[crew] = list(view["paused"])
        gate = item.get("_gate")
        if gate and gate["held_ids"]:  # recovery still pending: keep the held actions out for this call as well
            narrow["*"] = list(gate["held_ids"])
        return {"hints": {a: "learned" for a in view["hints"]}, "narrow": narrow, "notes": notes}
    return mitigate_rank


def make_log_learn(learning: Learning, app: str) -> Callable:
    def log_learn(item: Dict[str, Any], result: Dict[str, Any], ctx: Any) -> Optional[Dict[str, str]]:
        status = item.get("recheck")
        if not status or not os.path.exists(ctx.attempts_path):
            return None
        original = ctx.clock
        wait = ctx.policy.get("recheck_minutes", 10) * 60 + 60
        ctx.clock = lambda: original() + wait  # the delayed re-check, for this call only
        try:
            rm.recheck(ctx, {item["target"]: status})
        finally:
            ctx.clock = original
        events = [e for e in (learning.absorb_attempt(app, row) for row in rm.read_jsonl(ctx.attempts_path)) if e]
        if not events:
            return None
        e = events[-1]
        act = ctx.actions[e["method"].split("|")[2]]
        new = STATE[e["new_state"]]
        return {"en": "Re-check held; learned: %s is now %s (%d of %d)." % (act["en"], new["en"], e["successes"], e["attempts"]),
                "zh": "复查通过，已学习：%s 现在是“%s”（%d/%d）。" % (act["zh"], new["zh"], e["successes"], e["attempts"])}
    return log_learn


def build(gate: Optional[GlobalGate], learning: Optional[Learning], app: str) -> Dict[str, Callable]:
    """The three slots for one app. A missing piece simply leaves its slot empty."""
    slots = {}
    if gate is not None:
        slots["triage_gate"] = make_triage_gate(gate)
    if learning is not None:
        slots["mitigate_rank"] = make_mitigate_rank(learning, app)
        slots["log_learn"] = make_log_learn(learning, app)
    return slots
