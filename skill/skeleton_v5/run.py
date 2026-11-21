"""Incident Skeleton v5: one dry-run morning on SIMULATED data. Nothing is sent and no real system is called.

09:05  The access layer checks five managed systems and pulls their open items. Items about the same service or device merge.
       Teams sign-in fails at HQ and the branch. No official word yet, but four independent sites report it: "likely".
       Affected people are told at once. Local work continues through the v4 six-step runtime with the v5 plug-ins.
       A room in a working meeting waits. A full mailbox waits for approval.
09:06  Learning proposes a standing approval for "raise the mailbox quota". A person approves it. The next one runs alone.
       Identity actions are refused by rule; a non-approver cannot approve.
09:20  Microsoft confirms. The v4 gate links the next Teams request to the vendor incident and holds useless repairs.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from typing import Any, Dict, List

if __package__ in (None, ""):  # direct run: python skill/skeleton_v5/run.py
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    __package__ = "skeleton_v5"

from skeleton_v5 import HERE, SKILL  # noqa: E402
import remediate as rm  # noqa: E402

from skeleton_v4 import app_devices, app_servicedesk, learning as L, skeleton  # noqa: E402
from skeleton_v4.run import AV, AV_FAULT, BOARD, DIRECTORY, REQUESTS_V31, fake_clock, prime  # noqa: E402
from integration_v31.plugins import GlobalGate  # noqa: E402

from skeleton_v5 import adapters_v5, connectors as C, news as N, permissions as P, plugins_v5  # noqa: E402

RULES_FILE = os.path.join(HERE, "rules_v5.json")
SOURCES_V5 = os.path.join(HERE, "learning_sources_v5.json")

ROOM_301 = {"id": "AV-3F-301", "type": "av", "loc": {"en": "Room 3F-301", "zh": "3F-301 会议室"}}
ROOM_301_FAULT = {"message": "Camera image flickers during the meeting", "message_zh": "开会时摄像头画面闪烁",
                  "title": {"en": "Room 3F-301: camera image flickers", "zh": "3F-301 会议室：摄像头画面闪烁"}, "fixes": ["reboot-codec"]}
MAIL_1 = {"id": "V5-MAIL-1", "ts": "2026-11-21T09:05:00", "user": "zhang", "channel": "Teams", "text": "My mailbox is full and mail bounces",
          "title": {"en": "Mailbox full (before the grant)", "zh": "邮箱满了（授权前）"}, "fixes": ["raise-mailbox-quota"]}
MAIL_2 = {"id": "V5-MAIL-2", "ts": "2026-11-21T09:07:00", "user": "marco", "channel": "Portal", "text": "My mailbox is full and mail bounces",
          "title": {"en": "Mailbox full (after the grant)", "zh": "邮箱满了（授权后）"}, "fixes": ["raise-mailbox-quota"]}
# SIMULATED people's decisions for the dry run. A real deployment takes these from the approver, never from code.
DECISIONS = [("raise-mailbox-quota", "ext", True), ("raise-mailbox-quota", "liuyan", True), ("reset-mfa", "liuyan", True)]
METRIC = {
    "systems": ("Systems connected", "接入的系统"), "systems_ok": ("Systems answering", "正常响应的系统"),
    "items_synced": ("Open items synced", "同步的单子"), "merged_groups": ("Merged groups", "合并成的总单"),
    "duplicates_avoided": ("Duplicate items avoided", "少处理的重复单"), "alert_minutes_before_official": ("Alert minutes before official", "比官方早提醒（分钟）"),
    "people_told_early": ("People told early", "提前通知的人/单"), "done_by_ai": ("Done by AI", "AI 自己做完"),
    "waiting": ("Waiting (meeting, approval)", "等待中（会议、审批）"), "linked_to_vendor": ("Linked to vendor incident", "挂到厂商故障"),
    "to_people": ("Sent to people", "交给人"), "useless_fixes_held": ("Useless fixes held", "暂停的无用修复"),
    "grants_approved": ("Standing approvals granted", "批准的长期授权"), "grants_refused": ("Grants refused by rule", "规则拒绝的授权"),
    "by_site": ("Items by site", "各办公点单子数"), "minutes_saved_estimate": ("Minutes saved (estimate)", "估计省下的分钟"),
}
METRIC = {k: {"en": v[0], "zh": v[1]} for k, v in METRIC.items()}


def load_rules(path: str = RULES_FILE) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_sources_v5(path: str = SOURCES_V5) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def prime_v5(learning: L.Learning) -> List[Dict[str, Any]]:
    """Earlier confirmed re-checks (simulated): the KB methods for a full mailbox and a lost MFA device worked 5 of 5 times."""
    out = []
    for device, symptom, action in (("email", "full", "raise-mailbox-quota"), ("account", "mfa", "reset-mfa")):
        for i in range(1, 6):
            e = learning.absorb_attempt("servicedesk", {"ts": "2026-11-1%dT10:00:00" % i, "device": device, "symptom": symptom, "action": action,
                                                        "target": "u%d" % i, "confirmed": True, "outcome": "ran", "rechecked_at": "2026-11-1%dT10:20:00" % i})
            if e:
                out.append(e)
    return out


def build(tmp_root: str = None) -> Dict[str, Any]:
    rules = load_rules()
    box = {"now": _epoch("2026-11-21T09:05:00")}
    clock = lambda: box["now"]  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="skeleton-v5-", dir=tmp_root) as tmp:
        # 1. access layer
        reg = C.Registry()
        health = reg.health()
        synced = reg.sync()
        groups = C.merge(synced, rules)

        # 2. learning (v4 engine, v4 + v5 sources) and the permission book
        learning = L.Learning(now=fake_clock())
        learn_events = learning.cycle(L.load_sources() + load_sources_v5())
        primed = prime(learning) + prime_v5(learning)
        book = P.PermissionBook(learning, rules, now=lambda: "2026-11-21T09:06:00Z")

        # 3. gate and news at 09:05: Microsoft has said nothing yet
        gate = GlobalGate()
        gate.advance(1)
        reports = N.load()
        news_at = {"ts": "2026-11-21T09:05:00Z"}

        def news_view(provider, service):
            d = gate.decision_for(provider, service)
            return N.consensus(reports, provider, service, news_at["ts"], rules, official=d["decision"] == "vendor_incident_confirmed")

        teams_0905 = news_view("microsoft", "teams")

        d1 = app_devices.make_ctx(os.path.join(tmp, "devices"), "en", clock)
        d2 = app_servicedesk.make_ctx(os.path.join(tmp, "servicedesk"), "en", clock)
        office = rm.Ctx(os.path.join(tmp, "office"), "en", live=False, clock=clock, ticket_prefix="INC", ticket_start=10000)
        os.makedirs(office.dir, exist_ok=True)
        rm.save_json(os.path.join(office.dir, "board.json"), BOARD)
        directory = rm.load_json(DIRECTORY, {})
        reqs = {r["id"]: r for r in rm.load_json(REQUESTS_V31, [])}
        a1, a2 = adapters_v5.DevicesAdapterV5(), adapters_v5.ServiceDeskAdapterV5(directory, office)
        p1 = plugins_v5.build(gate, learning, "devices", news_view, book, rules)
        p2 = plugins_v5.build(gate, learning, "servicedesk", news_view, book, rules)
        rows: List[Dict[str, Any]] = []

        def go(item, adapter, slots, ctx, phase):
            rec = skeleton.run(item, adapter, slots, ctx)
            rows.append({"item": item, "record": rec, "phase": phase})
            return rec

        # 4. 09:05 local work while the outage is only likely
        notices = []
        for h in health:
            if h["status"] != "ok":
                notices.append({"kind": "connector_down", "to": ["admin"], "dry_run": True,
                                "en": "%s is %s. Its items are skipped this round; the admin is told." % (h["label"]["en"], h["text"]["en"]),
                                "zh": "%s%s。这一轮跳过它的单子，已通知管理员。" % (h["label"]["zh"], h["text"]["zh"])})
        if teams_0905["level"] == "likely" and rules["news_consensus"]["notify_employees"]:
            g = next((g for g in groups if g["key"] == "microsoft|teams"), None)
            src = ", ".join(s["domain"] for s in teams_0905["sources"])
            notices.append({"kind": "likely_outage", "to": g["children"] if g else [], "dry_run": True,
                            "en": "Heads-up: Microsoft Teams sign-in is likely down for many companies (%d independent sites: %s). "
                                  "Microsoft has not confirmed yet. It is not your computer. No need to report again." % (teams_0905["count"], src),
                            "zh": "提醒：Microsoft Teams 登录大概率在大范围故障（%d 个独立网站报道：%s）。微软还没确认。不是你电脑的问题，不用重复报障。"
                                  % (teams_0905["count"], src)})
        go(dict(reqs["V31-01"]), a2, p2, d2, "09:05")
        go(app_devices.item_from(dict(AV, id="AV-5F-502"), dict(AV_FAULT, message="Teams Rooms cannot sign in, the meeting cannot start",
                                                                 message_zh="Teams Rooms 登录不了，会议开不了")), a1, p1, d1, "09:05")
        room = app_devices.item_from(ROOM_301, ROOM_301_FAULT)
        room["meeting"] = {"until": "10:00", "blocked": False}
        go(room, a1, p1, d1, "09:05")
        go(dict(MAIL_1), a2, p2, d2, "09:05")

        # 5. 09:06 learning proposes, people decide (simulated), 09:07 the next full mailbox
        proposals = book.propose()
        by_action = {p["action"]: p["id"] for p in book.proposals.values()}
        decisions = [dict(action=a, by=who, **book.decide(by_action[a], who, ok)) for a, who, ok in DECISIONS if a in by_action]
        box["now"] = _epoch("2026-11-21T09:07:00")
        go(dict(MAIL_2), a2, p2, d2, "09:07")

        # 6. 09:20 Microsoft confirms: the v4 gate links and holds
        gate.advance(3)
        news_at["ts"] = "2026-11-21T09:20:00Z"
        box["now"] = _epoch("2026-11-21T09:20:00")
        teams_0920 = news_view("microsoft", "teams")
        go(dict(reqs["V31-02"]), a2, p2, d2, "09:20")

        official_at = next(c["ts"] for c in gate.cycles if any(s["source"] == "official_status" and s["service"] == "teams"
                                                                   and s["status"] != "healthy" for s in c["signals"]))
        metrics = measure(rules, health, synced, groups, rows, teams_0905, official_at, notices, book)
        return {"rules": rules, "health": health, "synced": synced, "groups": groups, "news": [teams_0905, teams_0920], "notices": notices,
                "rows": rows, "items": [r["record"] for r in rows], "learning": learning, "learn_events": learn_events, "primed": primed,
                "book": book, "proposals": proposals, "decisions": decisions, "gate": gate, "metrics": metrics,
                "ctx": {"devices": d1, "servicedesk": d2}}


def measure(rules, health, synced, groups, rows, alert, official_at, notices, book) -> Dict[str, Any]:
    m = rules["metrics"]
    dup = sum(len(g["children"]) - 1 for g in groups)
    held = sum(len(r["record"]["held_actions"]) for r in rows)
    out = [r["record"]["outcome"] for r in rows]
    early = int((N._t(official_at) - N._t(alert["checked_at"])).total_seconds() // 60) if alert["level"] == "likely" else 0
    sites: Dict[str, int] = {}
    for t in synced:
        sites[t["site"]] = sites.get(t["site"], 0) + 1
    return {"systems": len(health), "systems_ok": sum(h["status"] == "ok" for h in health), "items_synced": len(synced), "merged_groups": len(groups),
            "duplicates_avoided": dup, "alert_minutes_before_official": early, "people_told_early": sum(len(n["to"]) for n in notices if n["kind"] == "likely_outage"),
            "done_by_ai": sum(o in ("resolved", "local_repair") for o in out), "waiting": sum(o == "on_hold" for o in out),
            "linked_to_vendor": sum(o == "linked_vendor" for o in out), "to_people": sum(o == "escalated" for o in out),
            "useless_fixes_held": held, "grants_approved": sum(p["state"] == "approved" for p in book.proposals.values()),
            "grants_refused": sum(p["state"] == "refused" for p in book.proposals.values()), "by_site": sites,
            "minutes_saved_estimate": dup * m["minutes_per_duplicate_ticket"] + held * m["minutes_per_avoided_fix"], "dry_run": True}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="One dry-run morning of Incident Skeleton v5 (simulated data).")
    parser.add_argument("--lang", choices=("zh", "en"), default="en")
    lang = parser.parse_args().lang
    zh = lang == "zh"
    out = build()
    print("Incident Skeleton v5 · %s" % ("演练 · 模拟数据" if zh else "dry run · simulated data"))
    print("\n== %s" % ("接入的系统" if zh else "Connected systems"))
    for h in out["health"]:
        print("  %-22s %-10s scopes=%s secret=%s (%s)" % (h["label"][lang], h["text"][lang], ",".join(h["scopes"]), h["secret_env"],
                                                        "演练不读取" if zh else "not read in dry run"))
    print("\n== %s" % ("合并的单子" if zh else "Merged items"))
    for g in out["groups"]:
        print("  %s %s: %s  (%s)" % (g["parent"], g["label"][lang], ", ".join(g["children"]), ", ".join(g["systems"])))
    c = out["news"][0]
    print("\n== %s" % ("新闻核查 09:05" if zh else "News check 09:05"))
    print("  %s: %d/%d" % (c["label"][lang], c["count"], c["need"]))
    for s in c["sources"]:
        print("   + %s  %s" % (s["domain"], s["title"]))
    for s in c["dropped"]:
        print("   - %s  (%s)" % (s["domain"], N.DROP[s["why"]][lang]))
    for n in out["notices"]:
        print("  >> " + n[lang])
    print("\n== %s" % ("六步处理" if zh else "Six steps"))
    for r in out["rows"]:
        rec = r["record"]
        app = ("设备" if zh else "devices") if rec["app"] == "devices" else ("服务台" if zh else "service desk")
        print("\n[%s %s] %s -> %s" % (r["phase"], app, rec["label"][lang], rec["outcome"]))
        for step in rec["steps"]:
            mark = "-" if step["status"] == "skipped" else ">"
            slot = " [%s]" % step["slot"] if step["slot"] else ""
            print("  %s %-11s%s %s" % (mark, step["name"], slot, step[lang]))
        for note in rec["learning_used"]:
            print("      * " + note[lang])
    print("\n== %s" % ("权限进化" if zh else "Permission growth"))
    for p in out["book"].proposals.values():
        why = P.WHY[p["reason"]][lang] if p["reason"] else ""
        print("  %s %s: %s -> %s  [%s] %s %s" % (p["id"], p["label"][lang], p["from"][lang], p["to"][lang], P.STATES[p["state"]][lang],
                                                 (("批准人 " if zh else "by ") + p["approver"]) if p["approver"] else "", why))
    for d in out["decisions"]:
        if not d["ok"]:
            print("  x %s %s %s: %s" % (d["by"], "想批准" if zh else "tried to approve", d["action"], d["text"][lang]))
    print("\n== %s" % ("数字（演练估算）" if zh else "Numbers (dry-run estimate)"))
    for k, v in out["metrics"].items():
        if k != "dry_run":
            print("  %-32s %s" % (METRIC[k][lang], v))


if __name__ == "__main__":
    main()
