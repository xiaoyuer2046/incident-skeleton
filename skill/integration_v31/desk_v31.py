"""App 2 (service desk) with the v3 global gate at TRIAGE. Wraps skill/apps/servicedesk/desk.py; edits nothing in it.

TRIAGE order: 1. injection or admin request -> v1 rejection (the gate is never asked)
              2. v3 global gate -> link to the vendor incident, no crew
              3. v1 known-incident link   4. v1 crew selection
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import plugins
from .plugins import rm

import desk  # noqa: E402  (skill/apps/servicedesk/desk.py, put on sys.path by plugins)
import harvest as hv  # noqa: E402

STATE_ZH_DRY = "[演练：未实际发送]"
STATE_EN_DRY = "[DRY-RUN: nothing was sent]"


def ctx_for(data_dir: str, lang: str = "en", clock=None):
    return desk.ctx_for(data_dir, lang, clock=clock)


def _first(name: Dict[str, str]):
    return name["en"].split(" (")[0].split()[0], name["zh"].split("（")[0]


def is_rejected(text: str) -> bool:
    low = (text or "").lower()
    return bool(hv.injection_reason(text) or any(w in low for w in desk.CFG.get("never_automate", [])))


def _link_vendor(ctx, req: Dict[str, Any], user: Dict[str, Any], svc: Dict[str, Any]):
    name = user["name"]
    text = req["text"]
    ci = user["device"]["name"]
    base = {"short_description": text[:120], "description": text, "caller": name["en"], "cmdb_ci": ci, "message": text,
            "category": "Request", "impact": "3", "urgency": "3", "priority": "4 - Low", "kind": "request", "channel": req["channel"]}
    key = "request|%s" % req["id"]
    held = svc["held_ids"]
    data = {"vendor": svc["key"], "parent": svc["parent_id"], "decision": svc["decision"], "held": held}
    num, _ = rm.ticket_upsert(ctx, key, dict(base, assignment_group=desk.CFG["intake_group"], device="vendor-linked"),
                              "linked_vendor", data,
                              extra={"parent_incident": svc["parent_id"], "vendor_key": svc["key"], "app": "servicedesk",
                                     "caller_zh": name["zh"], "who_en": name["en"], "who_zh": name["zh"]})
    rm.ticket_update(ctx, key, rm.AUTOMATION, "linked_vendor", data, keep_state=True,
                     state="On Hold", hold_reason="Linked to vendor incident %s" % svc["parent_id"])
    pct = int(round(svc["confidence"] * 100))
    lab = svc["label"]
    nxt = svc["next_check"] or "n/a"
    held_en = ", ".join(ctx.actions[a]["en"] for a in held if a in ctx.actions) or "none"
    held_zh = "、".join(ctx.actions[a]["zh"] for a in held if a in ctx.actions) or "无"
    first, first_zh = _first(name)
    reply = {
        "en": "Hi %s, %s is down for many people and the vendor is on it (confidence %d%%, vendor status: %s). You do not need to report again. Next check: %s. We will tell you when it is fixed."
              % (first, lab["en"], pct, svc["vendor_summary"] or "investigating", nxt),
        "zh": "%s 你好，%s 目前多人受影响，厂商正在处理（置信度 %d%%）。你不用再重复报障。下次复查：%s。修复后会通知你。"
              % (first_zh, lab["zh"], pct, plugins._next_check_zh(svc["next_check"])),
    }
    states = {
        "RECEIVE": {"en": "%s request from %s" % (req["channel"], name["en"]), "zh": "来自 %s 的 %s 请求" % (name["zh"], req["channel"])},
        "TRIAGE": {"plugin": "v3",
                   "en": "Global gate: %s vendor incident (confidence %d%%). Linked to it. No crew runs." % (lab["en"], pct),
                   "zh": "全局闸门：%s 厂商故障（置信度 %d%%），已挂到它下面，不派班底。" % (lab["zh"], pct)},
        "INVESTIGATE": {"en": "Skipped: the vendor is already investigating.", "zh": "跳过：厂商已在排查。"},
        "MITIGATE": {"en": "Held while the vendor incident is active: %s." % held_en, "zh": "厂商故障期间暂停：%s。" % held_zh},
        "RESOLVE": {"en": "Waiting for %s to recover; the request closes by itself." % lab["en"], "zh": "等待 %s 恢复；请求会自动关闭。" % lab["zh"]},
        "LOG": {"en": "Ticket %s · On Hold, child of the vendor incident." % num, "zh": "工单 %s · 挂起，挂在厂商故障下。" % num},
    }
    msg = desk._msg(ctx, "hd_reply", num, "To %s: %s" % (name["en"], reply["en"]), "致 %s：%s" % (name["zh"], reply["zh"]))
    rec = plugins.skeleton("servicedesk", req["id"], req.get("title") or {"en": text, "zh": text}, "linked_vendor", states, held,
                           {"en": "%s vendor incident" % lab["en"], "zh": "%s 厂商故障" % lab["zh"]})
    rec["ticket"] = num
    rec["reply"] = reply
    return rec, [msg]


def _wrap_v1(req: Dict[str, Any], v1: Dict[str, Any], svc: Optional[Dict[str, Any]], held: List[str]):
    outcome = {"linked": "linked_known"}.get(v1["outcome"], v1["outcome"])
    if outcome == "on_hold":
        outcome = "on_hold"
    local_v3 = bool(svc and svc["evidence"] and v1["outcome"] != "rejected")
    states = {}
    for s in v1["states"]:
        states[s["name"]] = {"en": s["en"], "zh": s["zh"], "plugin": None}
    for name in plugins.STATES:  # a v1 path that stops early still yields all six states
        states.setdefault(name, {"en": "Skipped.", "zh": "跳过。"})
    if local_v3:
        d = svc["decision"]
        states["TRIAGE"]["plugin"] = "v3"
        states["TRIAGE"]["en"] = "Global gate: %s: %s. " % (svc["label"]["en"], plugins.VERDICT_EN.get(d, d)) + states["TRIAGE"]["en"]
        states["TRIAGE"]["zh"] = "全局闸门：%s 未确认厂商故障。" % svc["label"]["zh"] + states["TRIAGE"]["zh"]
    parent = None
    if v1.get("link"):
        parent = {"en": v1["link"]["ref"], "zh": v1["link"]["ref"]}
    rec = plugins.skeleton("servicedesk", req["id"], req.get("title") or {"en": req["text"], "zh": req["text"]}, outcome, states, held, parent)
    rec["ticket"] = v1.get("ticket")
    rec["reply"] = v1.get("reply", {"en": "", "zh": ""})
    return rec


def handle(ctx, office, req: Dict[str, Any], directory: Dict[str, Any], gate: Optional[plugins.GlobalGate]):
    """One request. Returns (skeleton record, notifications)."""
    user = directory.get(req["user"], {"name": {"en": req["user"], "zh": req["user"]}, "device": {"name": req["user"]}})
    # 1. safety first: the gate is not even asked for an injection or admin request
    if is_rejected(req["text"]) or gate is None:
        v1, msgs = desk.handle(ctx, office, req, directory)
        return _wrap_v1(req, v1, None, []), msgs
    # 2. v3 global gate
    svc = gate.check(req["text"])
    if svc and svc["link"]:
        return _link_vendor(ctx, req, user, svc)
    # 3 + 4. v1 path. While a hold is still active (recovery pending) held actions stay out of the allow-list for this call.
    held = svc["held_ids"] if svc else []
    with plugins.narrowed_allow(ctx, {"*": held}):
        v1, msgs = desk.handle(ctx, office, req, directory)
    return _wrap_v1(req, v1, svc, held), msgs


def close_vendor_linked(ctx, gate: plugins.GlobalGate, app: str = "servicedesk"):
    """Linked tickets close when v3 reports `resolved` for their vendor service. Returns (closures, notifications)."""
    closures, msgs = [], []
    data = rm.tickets_load(ctx)
    for key, num in list(data["by_key"].items()):
        tk = data["tickets"][num]
        if tk.get("device") != "vendor-linked" or tk["state"] not in rm.OPEN_STATES:
            continue
        provider, service = tk["vendor_key"].split("|")
        if not gate.is_resolved(provider, service):
            continue
        lab = plugins.LABELS[(provider, service)]
        rm.ticket_resolve(ctx, key, rm.AUTOMATION, "vendor_recovered", {"vendor": tk["vendor_key"], "parent": tk.get("parent_incident")},
                          close_notes="Closed: vendor incident resolved.")
        en = ("To %s: good news, %s has recovered, so %s is closed. Tell us if anything is still wrong. %s"
              % (tk.get("who_en", tk["caller"]), lab["en"], num, STATE_EN_DRY))
        zh = ("致 %s：好消息，%s 已恢复，%s 已关闭。如果还有问题请告诉我们。%s"
              % (tk.get("who_zh", tk.get("caller_zh", tk["caller"])), lab["zh"], num, STATE_ZH_DRY))
        msgs.append(desk._msg(ctx, "hd_linked_closed", num, en, zh))
        closures.append({"app": tk.get("app", app), "id": key.split("|", 1)[1], "ticket": num, "ts": ctx.ts(),
                         "parent": {"en": "%s vendor incident" % lab["en"], "zh": "%s 厂商故障" % lab["zh"]},
                         "reply": {"en": en, "zh": zh}, "dry_run": True})
    return closures, msgs


def send(ctx, msgs):
    """Dry-run delivery: writes the outbox in the (temporary) data dir only."""
    return desk.notify.send(ctx, msgs)
