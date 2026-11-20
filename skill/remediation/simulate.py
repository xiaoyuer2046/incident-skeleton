#!/usr/bin/env python3
"""Simulate one morning on a site, driving the REAL engine.

What is scripted (the "world"): which devices fail and when, which fix would
work on them, when an engineer picks up or resolves a ticket, and when a
person approves a risky step.

What is decided by the real code, not scripted: the patrol threshold, the
maintenance silence, blast-radius grouping, the case-library harvest and its
verdicts, the ranking of fixes, permissions, cooldown, learning (promote /
demote), and the ServiceNow ticket lifecycle (create, note, hold, reopen,
resolve). The scenario tags at the end are DETECTED from what the engine did.

Writes demo/data/sim.js, which demo/console.html and demo/servicenow.html replay.

    python3 simulate.py            # 12 patrols, 09:00-10:50, every 10 minutes
"""
import argparse, json, os, shutil, sys, tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remediate as rm
import harvest as hv
import orchestrator as orch
import watch as wt

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "demo", "data", "sim.js")
START = datetime(2026, 11, 21, 9, 0, 0)
STEP = timedelta(minutes=10)

DEVICES = [
    {"id": "PRN-3F-01", "type": "printer", "model": "HP LaserJet 405", "upstream": "SW-3F", "loc": {"zh": "三楼东", "en": "Floor 3 east"}},
    {"id": "PRN-5F-02", "type": "printer", "model": "HP LaserJet 405", "upstream": "SW-5F", "loc": {"zh": "五楼", "en": "Floor 5"}},
    {"id": "PRN-2F-03", "type": "printer", "model": "Canon iR-ADV C5840", "upstream": "SW-2F", "loc": {"zh": "二楼", "en": "Floor 2"}},
    {"id": "SIG-LOBBY-E", "type": "signage", "model": "BrightSign XT1144", "upstream": "SW-1F", "loc": {"zh": "大厅东", "en": "Lobby east"}},
    {"id": "SIG-LOBBY-W", "type": "signage", "model": "BrightSign XT1144", "upstream": "SW-1F", "loc": {"zh": "大厅西", "en": "Lobby west"}},
    {"id": "SIG-CAF-01", "type": "signage", "model": "Samsung QM55", "upstream": "SW-2F", "loc": {"zh": "二楼餐厅", "en": "Floor 2 café"}},
    {"id": "AV-3F-301", "type": "av", "model": "Zoom Rooms · Poly X50", "upstream": "SW-3F", "loc": {"zh": "3F-301 会议室", "en": "Room 3F-301"}},
    {"id": "AV-5F-502", "type": "av", "model": "Teams Rooms · Cisco Room Kit", "upstream": "SW-5F", "loc": {"zh": "5F-502 会议室", "en": "Room 5F-502"}},
    {"id": "AV-2F-201", "type": "av", "model": "Zoom Rooms · Poly X30", "upstream": "SW-2F", "loc": {"zh": "2F-201 会议室", "en": "Room 2F-201"}},
    {"id": "AP-3F-12", "type": "wifiap", "model": "Aruba AP-535", "upstream": "SW-3F", "loc": {"zh": "三楼东", "en": "Floor 3 east"}},
    {"id": "AP-4F-07", "type": "wifiap", "model": "Aruba AP-535", "upstream": "SW-4F", "loc": {"zh": "四楼西", "en": "Floor 4 west"}},
    {"id": "AP-4F-08", "type": "wifiap", "model": "Aruba AP-535", "upstream": "SW-4F", "loc": {"zh": "四楼中", "en": "Floor 4 centre"}},
    {"id": "AP-4F-09", "type": "wifiap", "model": "Aruba AP-535", "upstream": "SW-4F", "loc": {"zh": "四楼东", "en": "Floor 4 east"}},
]


def E(check_en, check_zh, res_en, res_zh, status):
    return {"check": {"en": check_en, "zh": check_zh}, "result": {"en": res_en, "zh": res_zh}, "status": status}


KINDS = {
    "jam": ("PAPER JAM (13.20)", "卡纸（错误码 13.20）", [
        E("ping", "ping", "reachable", "可达", "ok"),
        E("SNMP status", "SNMP 状态", "error: paper jam", "错误：卡纸", "err"),
        E("error code 13.20", "错误码 13.20", "fuser-area jam, tray empty", "定影器区卡纸，纸盒是空的", "warn"),
        E("print queue", "打印队列", "3 jobs stuck", "3 个任务卡住", "err")]),
    "offline": ("printer unreachable", "打印机不通", [
        E("ping", "ping", "no reply", "无响应", "err")]),
    "black": ("signage black screen after CMS update", "CMS 更新后标牌黑屏", [
        E("ping player", "ping 播放器", "reachable", "可达", "ok"),
        E("CMS last sync", "CMS 上次同步", "failed after the 09:22 update", "09:22 更新后同步失败", "err"),
        E("HDMI signal", "HDMI 信号", "present", "正常", "ok"),
        E("player app", "播放器应用", "playlist cache stale", "播放列表缓存过期", "err")]),
    "hung": ("can't join meeting, panel frozen", "进不了会，面板卡死", [
        E("ping controller", "ping 控制器", "reachable", "可达", "ok"),
        E("codec API", "编解码器 API", "responds, call service hung", "有响应，通话服务挂起", "err"),
        E("room service", "房间服务", "offline in the admin portal", "管理台显示离线", "err"),
        E("touch panel", "触控面板", "no heartbeat for 6 min", "6 分钟无心跳", "warn")]),
    "ap_after": ("AP still offline after the switch came back", "交换机恢复后 AP 仍离线", [
        E("ping AP", "ping AP", "no reply", "无响应", "err"),
        E("upstream SW-4F", "上游 SW-4F", "back up since 09:57", "09:57 起已恢复", "ok"),
        E("PoE port", "PoE 端口", "port up, 0 W delivered", "端口 up，但供电 0 W", "err")]),
    "ap": ("AP offline, clients dropping", "AP 离线，客户端掉线", [
        E("ping AP", "ping AP", "no reply", "无响应", "err"),
        E("controller API", "控制器 API", "AP state: down", "AP 状态：down", "err"),
        E("PoE port", "PoE 端口", "0 W delivered", "供电 0 W", "err"),
        E("clients", "客户端", "0 associated", "0 个关联", "warn")]),
}

DOWN, BLIP = [False, False, False], [True, False, True]
UP4 = {"AP-4F-07": ("ap", []), "AP-4F-08": ("ap", []), "AP-4F-09": ("ap", [])}
APPROVER = {"en": "Chen Wei (AV lead) · Teams approval", "zh": "陈伟（AV 主管）· Teams 审批"}

# The scripted world. fixes = the actions that would actually work on that device right now.
CYCLES = [
    {"harvest": True, "probes": {"SIG-CAF-01": BLIP}},
    {"faults": {"PRN-3F-01": ("jam", ["clear-queue"])}},
    {"faults": {"AV-3F-301": ("hung", ["reboot-codec"])}},
    {"harvest": True, "faults": {"SIG-LOBBY-E": ("black", ["clear-player-cache"])}},
    {"faults": dict(UP4)},
    {"faults": dict(UP4, **{"AP-3F-12": ("ap", [])}), "probes": {"PRN-5F-02": BLIP},
     "after": [("ack", "wifiap|AP-3F-12|offline", "Zhang Min (Network)",
                {"en": "Picked up. Heading to floor 3 east with a spare PoE injector.", "zh": "已接单，带备用 PoE 供电器去三楼东。"})]},
    {"harvest": True, "faults": {"AP-4F-09": ("ap_after", ["poe-cycle"]), "AP-3F-12": ("ap", []), "PRN-2F-03": ("offline", [])}},
    {"faults": {"AP-3F-12": ("ap", []), "PRN-2F-03": ("offline", []), "AV-5F-502": ("hung", ["reset-room-profile"])},
     "after": [("ack", "av|AV-5F-502|hung", "Chen Wei (AV lead)",
                {"en": "Saw the approval request for the profile reset. Checking the vendor note first.", "zh": "看到重置配置的审批请求，先核对厂商说明。"})]},
    {"before": [("resolve", "wifiap|AP-3F-12|offline", "Zhang Min (Network)",
                 "Replaced the failed PoE injector and moved the AP to a PoE+ port.")],
     "faults": {"PRN-2F-03": ("offline", []), "AV-5F-502": ("hung", ["reset-room-profile"])},
     "approvals": {"reset-room-profile": APPROVER}},
    {"harvest": True, "faults": {"PRN-2F-03": ("offline", [])}},
    {"faults": {"AP-3F-12": ("ap", []), "AV-2F-201": ("hung", ["reboot-codec"])}},
    {"faults": {"AV-3F-301": ("hung", ["reboot-codec"])}, "probes": {"SIG-LOBBY-W": BLIP}},
]
WINDOWS = [{"device": "PRN-2F-03", "from": "2026-11-21T09:55:00", "to": "2026-11-21T10:35:00",
            "reason": {"en": "Fuser replacement (CHG0004417)", "zh": "更换定影器（CHG0004417）"}}]

TAGS = ["quiet", "blip", "library_reordered", "notify", "library_grows", "new_knowledge", "blast",
        "master_linked", "comms_detected", "master_hint", "progress_posted", "board_closed", "duplicate",
        "escalated", "upstream_resolved", "cooldown", "maintenance", "approval_wait", "approved_fix", "auto_resolved",
        "engineer_learned", "injection", "reopened", "demoted"]


def detect_tags(cyc, library, prev_ts):
    tags = set()
    for b in cyc.get("boards", []):
        for it in b["timeline"]:
            fresh = prev_ts < it["ts"] <= cyc["ts"]
            if not fresh:
                continue
            if it.get("kind") == "link":
                tags.add("master_linked")
            if it["source"] == "email":
                tags.add("comms_detected")
            if it.get("kind") == "post":
                tags.add("progress_posted")
            if it.get("kind") == "close":
                tags.add("board_closed")
    st = [r["status"] for r in cyc["rows"]]
    if not any(s in ("confirmed", "maintenance", "upstream") for s in st):
        tags.add("quiet")
    if "blip" in st:
        tags.add("blip")
    if "maintenance" in st:
        tags.add("maintenance")
    for e in cyc["events"]:
        if e["kind"] == "upstream":
            tags.add({"created": "blast", "updated": "duplicate"}.get(e["event"], "blast"))
        if e["kind"] == "upstream_recovered":
            tags.add("upstream_resolved")
    for r in cyc["results"]:
        decs = {x["decision"] for x in r["trace"]}
        ran = [x for x in r["trace"] if x["decision"] == "run"]
        tags |= decs & {"cooldown", "demoted"}
        if r["resolved"] and ran:
            fx = ran[-1]
            if ran[0] is fx and "lib" in fx["sources"] and r["builtin_first"] != fx["action"]:
                tags.add("library_reordered")
            if "lib" in fx["sources"] and "builtin" not in fx["sources"] and "master" not in fx["sources"]:
                tags.add("new_knowledge")
            if fx["tier"] == "notify_then_act":
                tags.add("notify")
            if fx.get("approved_by"):
                tags.add("approved_fix")
            if fx.get("hint"):
                tags.add("master_hint")
        elif "approval" in decs:
            tags.add("approval_wait")
        ev = (r.get("ticket") or {}).get("event")
        tags.add({"created": "escalated", "updated": "duplicate", "reopened": "reopened", "resolved": "auto_resolved"}.get(ev, "")) if ev else None
    h = cyc.get("harvest")
    if h:
        if h["rejected_new"]:
            tags.add("injection")
        if cyc["n"] > 1 and h["new"]:
            tags.add("library_grows")
        lib = {e["id"]: e for e in library.get("entries", [])}
        if any(s["type"] == "ticket" for i in h["new"] for s in lib.get(i, {}).get("sources", [])):
            tags.add("engineer_learned")
    tags.discard("")
    return [t for t in TAGS if t in tags]


def master_tickets(ctx, ours):
    """Turn the sample master incidents into ticket records for the simulated ServiceNow page,
    with our progress notes (watch.py posts) merged in and the child incidents listed."""
    board = wt.load_board(ctx)
    out = []
    for m in rm.load_json(os.path.join(HERE, "sources", "servicenow_major.json"), []):
        notes = []
        for i, n in enumerate(m["notes"]):
            notes.append({"ts": n["ts"], "author": n["author"], "type": "created" if i == 0 else ("resolved" if n["state"] == "Resolved" else "comment"),
                          "kind": "master_note", "data": {"text": n["text"], "engineer": n.get("engineer"), "eta": n.get("eta")}, "state": n["state"]})
        for b in board.values():
            for p in b.get("posted", []):
                if p["ref"] == m["number"]:
                    notes.append({"ts": p["ts"], "author": p["author"], "type": "comment", "kind": "child_progress", "data": {"text": p["text"]},
                                  "state": next((n["state"] for n in reversed(m["notes"]) if n["ts"] <= p["ts"]), "In Progress")})
        notes.sort(key=lambda n: n["ts"])
        res = next((n for n in m["notes"] if n["state"] == "Resolved"), None)
        out.append({"number": m["number"], "kind": "master", "major": True, "key": "master|" + m["number"], "caller": m["owner"],
                    "assigned_to": m["owner"], "opened_at": m["opened_at"], "updated_at": notes[-1]["ts"], "state": notes[-1]["state"],
                    "resolved_at": res["ts"] if res else None, "close_code": "Solved (Permanently)" if res else "",
                    "close_notes": res["text"]["en"] if res else "", "short_description": m["short_description"]["en"],
                    "message": m["short_description"]["en"], "message_zh": m["short_description"]["zh"], "cmdb_ci": m["ci"],
                    "assignment_group": m["assignment_group"], "priority": m["priority"], "impact": m["impact"], "urgency": m["urgency"],
                    "category": m["category"], "description": "Affected: " + ", ".join(m["affected"]), "devices": m["affected"],
                    "children": [t["number"] for t in ours if t.get("parent_incident") == m["number"]], "work_notes": notes,
                    "reopen_count": 0, "knowledge": [], "awaiting_approval": []})
    return out


def main():
    ap = argparse.ArgumentParser(description="Simulate one morning with the real engine")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--keep", action="store_true", help="keep the temporary data directory")
    ap.add_argument("--brain", default="mock", choices=["mock", "off", "claude", "http", "cmd"],
                    help="AI backend for the run (default: mock stand-in, no model, no cost)")
    a = ap.parse_args()
    os.environ["BRAIN"] = a.brain
    import brain

    data_dir = tempfile.mkdtemp(prefix="incident-sim-")
    clock = {"t": START}
    ctx = rm.Ctx(data_dir, "en", live=False, clock=lambda: clock["t"].timestamp(), ticket_prefix="INC", ticket_start=10000)
    cycles, seen = [], {}
    for i, spec in enumerate(CYCLES):
        clock["t"] = START + STEP * i
        human = []

        def do(evs):
            for ev in evs or []:
                if ev[0] == "ack":
                    num = rm.ticket_update(ctx, ev[1], ev[2], "engineer_ack", {"text": ev[3]}, assigned_to=ev[2])
                    human.append({"kind": "ack", "ticket": num, "author": ev[2], "text": ev[3]})
                elif ev[0] == "resolve":
                    num = rm.ticket_resolve(ctx, ev[1], ev[2], "engineer_resolved", {"close_notes": ev[3]}, close_notes=ev[3])
                    human.append({"kind": "resolve", "ticket": num, "author": ev[2], "text": {"en": ev[3], "zh": ev[3]}})

        do(spec.get("before"))
        for aid, who in (spec.get("approvals") or {}).items():
            human.append({"kind": "approve", "action": aid, "author": who})
        harvest = hv.harvest(ctx) if spec.get("harvest") else None
        faults, probes = {}, dict(spec.get("probes", {}))
        for dev, (kind, fixes) in (spec.get("faults") or {}).items():
            msg, msg_zh, ev = KINDS[kind]
            faults[dev] = {"message": msg, "message_zh": msg_zh, "fixes": fixes, "evidence": ev}
            probes.setdefault(dev, DOWN)
        approvals = {k: v["en"] for k, v in (spec.get("approvals") or {}).items()}
        rep = orch.run_cycle(ctx, DEVICES, probes, faults, approvals=approvals, windows=WINDOWS)
        do(spec.get("after"))
        library = rm.load_json(ctx.library_path, {})
        cyc = {"n": i + 1, "ts": ctx.ts(), "harvest": harvest, "human": human, "rows": rep["rows"], "events": rep["events"],
               "results": rep["results"], "scoreboard": rm.scoreboard(ctx),
               "library_size": len(library.get("entries", [])), "library_verified": sum(1 for e in library.get("entries", []) if e.get("status") == "verified"),
               "boards": json.loads(json.dumps(list(rep["board"].values()), ensure_ascii=False))}
        cyc["tags"] = detect_tags(cyc, library, cycles[-1]["ts"] if cycles else "")
        for t in cyc["tags"]:
            seen.setdefault(t, i + 1)
        cycles.append(cyc)

    tickets = sorted(rm.tickets_load(ctx)["tickets"].values(), key=lambda t: t["number"])
    tickets = master_tickets(ctx, tickets) + tickets
    library = rm.load_json(ctx.library_path, {})
    pol = ctx.policy
    sim = {"meta": {"generated": datetime.now().isoformat(timespec="seconds"), "start": START.isoformat(), "step_minutes": 10,
                    "note": "Scripted world, real engine, dry run. Nothing was sent to any device or to ServiceNow.",
                    "brain": brain.label()},
           "devices": DEVICES, "windows": WINDOWS, "catalogue": ctx.actions, "tags": TAGS, "coverage": seen,
           "policy": {"autonomy": pol.get("autonomy"), "allow": pol.get("allow"), "cooldown_minutes": pol.get("cooldown_minutes"),
                      "reopen_hours": pol.get("reopen_hours"), "blast_min": pol.get("blast_radius", {}).get("min_devices"),
                      "need": pol.get("patrol", {}).get("need"), "rounds": pol.get("patrol", {}).get("rounds"),
                      "groups": pol.get("escalation", {}).get("groups"), "evolution": pol.get("evolution")},
           "cycles": cycles, "tickets": tickets, "library": library}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("// Generated by skill/remediation/simulate.py. Scripted world, real engine, dry run.\n")
        f.write("window.SIM = " + json.dumps(sim, ensure_ascii=False) + ";\n")

    print("\n  simulated morning  %s → %s  (%d patrols)" % (START.strftime("%H:%M"), clock["t"].strftime("%H:%M"), len(cycles)))
    print("  " + "─" * 74)
    for c in cycles:
        bad = [r for r in c["rows"] if r["status"] != "healthy"]
        parts = []
        for r in bad:
            if r["status"] == "confirmed":
                parts.append("%s %s%s" % (r["id"], "fixed" if r.get("resolved") else "→" , "" if r.get("resolved") else " " + str(r.get("ticket"))))
            else:
                parts.append("%s %s" % (r["id"], r["status"]))
        print("  C%-2d %s  %-48s %s" % (c["n"], c["ts"][11:16], "; ".join(parts)[:48] or "all healthy", ",".join(c["tags"])))
    print("  " + "─" * 74)
    print("  scenarios covered: %d/%d   missing: %s" % (len(seen), len(TAGS), ", ".join(t for t in TAGS if t not in seen) or "none"))
    print("  tickets: %s" % ", ".join("%s %s" % (t["number"], t["state"]) for t in tickets))
    print("  case library: %d entries, %d verified, %d rejected" % (len(library.get("entries", [])),
          sum(1 for e in library.get("entries", []) if e.get("status") == "verified"), len(library.get("rejected", []))))
    print("  wrote %s (%d KB)" % (a.out, os.path.getsize(a.out) // 1024))
    if a.keep:
        print("  data dir kept: %s" % data_dir)
    else:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
