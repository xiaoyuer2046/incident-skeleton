"""App 1 (office devices) with the v3 gate at TRIAGE and v2 ranking at MITIGATE / learning at LOG.
Wraps skill/remediation/remediate.py; edits nothing in it.

v2 adopted (promoted) -> `hints` entry, tried first, still checked by policy.
v2 paused (demoted)   -> removed from an in-memory copy of the allow-list for this call only.
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, Optional

from . import plugins
from .plugins import rm

DEFAULT_EVIDENCE = [{"check": {"en": "patrol probe", "zh": "巡检探测"},
                     "result": {"en": "no answer in 3 of 3 probes", "zh": "3 次探测都没有回应"}, "status": "err"}]
STATE_EN = {"promoted": "adopted", "demoted": "paused", "trial": "being verified", "candidate": "needs verification"}
NEW_STATE_ZH = {"promoted": "已采用", "demoted": "已停用", "trial": "验证中", "candidate": "待验证"}
CREW_LABEL = {"printer": ("Printer", "打印机"), "signage": ("Digital signage", "数字标牌"),
              "av": ("Meeting-room AV", "会议室音视频"), "wifiap": ("Wireless AP", "无线 AP")}


def ctx_for(data_dir: str, lang: str = "en", clock=None):
    return rm.Ctx(data_dir, lang, live=False, clock=clock, ticket_prefix="INC", ticket_start=30000)


def _txt(items, key):
    return "; ".join("%s: %s" % (rm.txt(e["check"], key), rm.txt(e["result"], key)) for e in items)


def _link_vendor(ctx, dev, fault, svc):
    ci = dev["id"]
    dtype = dev["type"]
    loc = dev.get("loc", {"en": ci, "zh": ci})
    held = sorted(ctx.policy.get("allow", {}).get(dtype, []))  # every automatic repair of this device is held
    key = "vendor|%s" % ci
    data = {"vendor": svc["key"], "parent": svc["parent_id"], "decision": svc["decision"], "held": held}
    fields = {"short_description": "[Auto] %s: linked to vendor incident - %s" % (ci, fault["message"]), "description": fault["message"],
              "cmdb_ci": ci, "assignment_group": ctx.policy.get("escalation", {}).get("groups", {}).get(dtype, "Service Desk"),
              "device": "vendor-linked", "symptom": "vendor", "message": fault["message"], "category": "Hardware",
              "impact": "2", "urgency": "2", "priority": "3 - Moderate", "kind": "device", "caller": rm.AUTOMATION}
    num, _ = rm.ticket_upsert(ctx, key, fields, "linked_vendor", data,
                              extra={"parent_incident": svc["parent_id"], "vendor_key": svc["key"], "app": "devices",
                                     "who_en": "the organisers of %s" % loc["en"], "who_zh": "%s 的会议组织者" % loc["zh"]})
    rm.ticket_update(ctx, key, rm.AUTOMATION, "linked_vendor", data, keep_state=True,
                     state="On Hold", hold_reason="Linked to vendor incident %s" % svc["parent_id"])
    pct = int(round(svc["confidence"] * 100))
    lab = svc["label"]
    held_en = ", ".join(ctx.actions[a]["en"] for a in held) or "none"
    held_zh = "、".join(ctx.actions[a]["zh"] for a in held) or "无"
    states = {
        "RECEIVE": {"en": "Patrol confirmed a fault on %s: %s" % (loc["en"], fault["message"]),
                    "zh": "巡检确认 %s 故障：%s" % (loc["zh"], fault.get("message_zh") or fault["message"])},
        "TRIAGE": {"plugin": "v3",
                   "en": "Global gate: %s vendor incident (confidence %d%%). The room fault is linked to it." % (lab["en"], pct),
                   "zh": "全局闸门：%s 厂商故障（置信度 %d%%），会议室故障已挂到它下面。" % (lab["zh"], pct)},
        "INVESTIGATE": {"en": "Skipped: the room software is waiting on the vendor service.", "zh": "跳过：会议室软件在等厂商服务恢复。"},
        "MITIGATE": {"en": "Device repair held: %s." % held_en, "zh": "设备修复已暂停：%s。" % held_zh},
        "RESOLVE": {"en": "Waiting for %s to recover; re-check then." % lab["en"], "zh": "等待 %s 恢复后再复查。" % lab["zh"]},
        "LOG": {"en": "Ticket %s · On Hold, child of the vendor incident." % num, "zh": "工单 %s · 挂起，挂在厂商故障下。" % num},
    }
    rec = plugins.skeleton("devices", ci, fault.get("title") or {"en": fault["message"], "zh": fault.get("message_zh") or fault["message"]},
                           "linked_vendor", states, held, {"en": "%s vendor incident" % lab["en"], "zh": "%s 厂商故障" % lab["zh"]})
    rec["ticket"] = num
    return rec


def handle(ctx, dev: Dict[str, Any], fault: Dict[str, Any], gate: Optional[plugins.GlobalGate], evo=None, recheck: Optional[str] = None):
    """One confirmed device fault through the six states. `recheck` ('healthy' | 'confirmed') supplies the delayed
    re-check result in simulations; without it a fix stays provisional and v2 learns nothing yet."""
    dtype, ci = dev["type"], dev["id"]
    loc = dev.get("loc", {"en": ci, "zh": ci})
    msg = fault["message"]
    svc = gate.check(msg) if gate is not None else None
    if svc and svc["link"]:
        return _link_vendor(ctx, dev, fault, svc)

    skey = rm.symptom_key(dtype, msg)
    hints, paused = plugins.v2_view(evo, dtype, skey)
    ev = fault.get("evidence") or DEFAULT_EVIDENCE
    ns = argparse.Namespace(type=dtype, target=dev.get("target", ci), ci=ci, source=loc["en"], message=msg, message_zh=fault.get("message_zh"))
    scenario = set(fault.get("fixes", []))
    with plugins.narrowed_allow(ctx, {dtype: paused}):
        res = rm.remediate(ns, ctx, scenario=scenario, quiet=True, evidence=ev, hints=hints or None)
    A = ctx.actions
    ran = [t for t in res["trace"] if t["decision"] == "run"]
    c_en, c_zh = CREW_LABEL.get(dtype, (dtype, dtype))

    if svc and svc["evidence"]:
        tri = {"plugin": "v3",
               "en": "Global gate: %s: %s. %s crew · symptom “%s”." % (svc["label"]["en"], plugins.VERDICT_EN.get(svc["decision"], svc["decision"]), c_en, skey),
               "zh": "全局闸门：%s 未确认厂商故障，走本地维修。%s班底 · 症状“%s”。" % (svc["label"]["zh"], c_zh, skey)}
    else:
        tri = {"en": "%s crew · symptom “%s”." % (c_en, skey), "zh": "%s班底 · 症状“%s”。" % (c_zh, skey)}

    mit_en = "; ".join("%s → %s" % (A[t["action"]]["en"], "recovered" if t.get("recovered") else "not recovered") for t in ran) or "nothing allowed to run"
    mit_zh = "；".join("%s → %s" % (A[t["action"]]["zh"], "恢复" if t.get("recovered") else "没恢复") for t in ran) or "没有可自动执行的步骤"
    if hints:
        mit_en += ". v2 adopted, tried first: %s" % ", ".join(A[a]["en"] for a in hints)
        mit_zh += "。v2 已采用，优先尝试：%s" % "、".join(A[a]["zh"] for a in hints)
    if paused:
        mit_en += ". v2 paused, removed for this call: %s" % ", ".join(A[a]["en"] for a in paused)
        mit_zh += "。v2 已停用，本次移除：%s" % "、".join(A[a]["zh"] for a in paused)
    mit = {"plugin": "v2" if (hints or paused) else None, "en": mit_en, "zh": mit_zh}

    events = []
    ticket = (res.get("ticket") or {}).get("number")
    if res["resolved"]:
        fx = ran[-1]["action"]
        events = plugins.learn_from_recheck(ctx, evo, {dev.get("target", ci): recheck}) if recheck else []
        resolve = {"en": "Recovered by “%s”; re-check due in %d minutes." % (A[fx]["en"], ctx.policy.get("recheck_minutes", 10)),
                   "zh": "已用“%s”恢复；%d 分钟后复查。" % (A[fx]["zh"], ctx.policy.get("recheck_minutes", 10))}
        if events:
            e = events[-1]
            en_log = "Re-check held; v2 learned: %s now %s (%d/%d)." % (A[fx]["en"], STATE_EN.get(e["new_state"], e["new_state"]), e["successes"], e["attempts"])
            zh_log = "复查通过；v2 已学习：%s 现为“%s”（%d/%d）。" % (A[fx]["zh"], NEW_STATE_ZH.get(e["new_state"], e["new_state"]),
                                                         e["successes"], e["attempts"])
        else:
            en_log, zh_log = "Fix recorded as provisional; v2 learns after the re-check.", "修复先记为暂定；复查后 v2 才会学习。"
        log = {"plugin": "v2" if events else None, "en": en_log + (" Ticket %s." % ticket if ticket else ""),
               "zh": zh_log + (" 工单 %s。" % ticket if ticket else "")}
        outcome = "local_repair"
    else:
        group = (res.get("ticket") or {}).get("group", "Service Desk")
        resolve = {"en": "Sent to %s with everything tried." % group, "zh": "转给 %s，已附上做过的步骤。" % group}
        log = {"en": "Ticket %s · escalated." % ticket, "zh": "工单 %s · 已升级。" % ticket}
        outcome = "escalated"

    states = {
        "RECEIVE": {"en": "Patrol confirmed a fault on %s: %s" % (loc["en"], msg),
                    "zh": "巡检确认 %s 故障：%s" % (loc["zh"], fault.get("message_zh") or msg)},
        "TRIAGE": tri,
        "INVESTIGATE": {"en": _txt(ev, "en"), "zh": _txt(ev, "zh")},
        "MITIGATE": mit, "RESOLVE": resolve, "LOG": log,
    }
    rec = plugins.skeleton("devices", ci, fault.get("title") or {"en": msg, "zh": fault.get("message_zh") or msg}, outcome, states, [], None)
    rec["ticket"] = ticket
    return rec


def close_vendor_linked(ctx, gate):
    from . import desk_v31
    return desk_v31.close_vendor_linked(ctx, gate, app="devices")
