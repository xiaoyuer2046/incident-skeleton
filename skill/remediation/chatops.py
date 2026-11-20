#!/usr/bin/env python3
"""Chat with the crew (Teams / Slack): ask what is going on, approve a waiting step, pause or resume.

  status    "what's wrong with 2F-201?", "Floor 4 Wi-Fi ETA?", "what's broken?"
            -> answered from the latest patrol, open tickets, the outage board and meetings
  approve   "approve the profile reset on 5F-502" / "批准 5F-502 重置配置"
            -> only people on policy.json chatops.approvers for that device type may approve.
               The approval is for ONE device and ONE action, used once by the next patrol,
               and the policy still applies. Written to the ticket and the audit log.
  stop      "stop automatic repairs" / "暂停自动修复"   -> kill switch on (any approver)
  resume    "resume automatic repairs" / "恢复自动修复" -> kill switch off (any approver)

The message is parsed into one of these intents; it is never executed as a command.
The sender's identity comes from the chat platform (here: the --from argument).

  python3 chatops.py --from "Chen Wei (AV lead)" --say "批准 5F-502 重置配置" --data-dir data
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remediate as rm

ZH_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6"}
ST = {"healthy": ("healthy", "正常"), "blip": ("one missed probe, ignored", "偶发一次，忽略"), "confirmed": ("down", "故障"),
      "fixed": ("fixed this patrol", "本轮已修好"), "maintenance": ("in maintenance", "维护中"), "upstream": ("down with its switch", "随上游交换机掉线"),
      "self_healed": ("came back on its own", "自己恢复了")}


def _approvals_path(ctx):
    return os.path.join(ctx.dir, "approvals.json")


def _last(ctx):
    return rm.load_json(os.path.join(ctx.dir, "last_patrol.json"), {"devices": [], "status": {}, "ts": None})


def find_devices(text, devices):
    t = text.upper()
    hits = [d for d in devices if d["id"].upper() in t]
    if not hits:
        hits = [d for d in devices if "-" in d["id"] and d["id"].split("-", 1)[1].upper() in t]
    return hits


def floor_of(text):
    m = re.search(r"floor\s*(\d)|(\d)\s*f\b|(\d)\s*楼|([一二三四五六])楼", text, re.I)
    if not m:
        return None
    g = next(x for x in m.groups() if x)
    return ZH_NUM.get(g, g)


def _ticket_for(ctx, ci):
    d = rm.tickets_load(ctx)
    tks = [t for t in d["tickets"].values() if t.get("cmdb_ci") == ci]
    open_ = [t for t in tks if t["state"] in rm.OPEN_STATES]
    return (open_ or sorted(tks, key=lambda t: t["updated_at"])[-1:] or [None])[0]


def _approvers(ctx, dtype):
    a = ctx.policy.get("chatops", {}).get("approvers", {})
    return a.get(dtype, []) + a.get("*", [])


def _anyone(ctx):
    return {p for v in ctx.policy.get("chatops", {}).get("approvers", {}).values() for p in v}


def _r(intent, ok, en, zh, refs=None):
    return {"intent": intent, "ok": ok, "reply": {"en": en, "zh": zh}, "refs": refs or []}


def device_status(ctx, d, last):
    A = ctx.actions
    st = last["status"].get(d["id"], "unknown")
    s_en, s_zh = ST.get(st, (st, st))
    en, zh = ["%s: %s." % (d["id"], s_en)], ["%s：%s。" % (d["id"], s_zh)]
    refs = []
    tk = _ticket_for(ctx, d["id"])
    if tk:
        refs.append(tk["number"])
        note = next((n for n in reversed(tk["work_notes"]) if n["kind"] == "auto_failed"), None)
        en.append("Ticket %s → %s, %s." % (tk["number"], tk["assignment_group"], tk["state"]))
        zh.append("工单 %s → %s，%s。" % (tk["number"], tk["assignment_group"], {"New": "新建", "In Progress": "处理中", "On Hold": "挂起", "Resolved": "已解决"}.get(tk["state"], tk["state"])))
        if note:
            tried = note["data"].get("tried", [])
            if tried:
                en.append("Tried: %s (not recovered)." % ", ".join(A[x["action"]]["en"] for x in tried))
                zh.append("已试：%s（没恢复）。" % "、".join(A[x["action"]]["zh"] for x in tried))
        ss = next((n for n in reversed(tk["work_notes"]) if n["kind"] == "status_summary"), None)
        if ss and (ss["data"].get("waiting") or ss["data"].get("eta")):
            en.append("Engineer side: waiting for %s%s." % (ss["data"].get("waiting") or "an update", (", ETA " + ss["data"]["eta"]) if ss["data"].get("eta") else ""))
            zh.append("工程师那边：在等 %s%s。" % (ss["data"].get("waiting") or "进展", ("，预计 " + ss["data"]["eta"]) if ss["data"].get("eta") else ""))
        if tk.get("awaiting_approval"):
            en.append("Waiting for approval: %s." % ", ".join(A[x]["en"] for x in tk["awaiting_approval"]))
            zh.append("等待批准：%s。" % "、".join(A[x]["zh"] for x in tk["awaiting_approval"]))
    meet = rm.load_json(os.path.join(ctx.dir, "premeeting_last.json"), [])
    for m in meet:
        if m["room"] == d["id"]:
            if m["state"] == "at_risk" and m.get("action") == "move":
                en.append("Meeting “%s” at %s: we asked the organizer to move to %s." % (m["title"]["en"], m["start"][11:16], m["alternative"]))
                zh.append("%s 的会议“%s”：已建议组织者改到 %s。" % (m["start"][11:16], m["title"]["zh"], m["alternative"]))
            elif m["state"] == "at_risk":
                en.append("Meeting “%s” at %s is at risk; plan B is %s." % (m["title"]["en"], m["start"][11:16], m.get("alternative") or "none"))
                zh.append("%s 的会议“%s”有风险；备选 %s。" % (m["start"][11:16], m["title"]["zh"], m.get("alternative") or "无"))
    return " ".join(en), "".join(zh), refs


def handle(ctx, sender, text):
    t = text.lower()
    last = _last(ctx)
    devices = last["devices"]
    if re.search(r"approve|批准|同意", t):
        return approve(ctx, sender, text, devices)
    if re.search(r"\bstop\b|\bpause\b|暂停|紧急开关", t):
        if sender not in _anyone(ctx):
            return _r("stop", False, "Only approvers can pause automation. Nothing changed.", "只有审批人可以暂停自动修复。没有做任何改动。")
        rm.save_json(os.path.join(ctx.dir, "STOP"), {"by": sender, "ts": ctx.ts(), "via": "chat"})
        rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "kill_switch_on", "by": sender, "via": "chat"})
        return _r("stop", True, "⛔ Kill switch on. Automatic repairs are paused; tickets still go to people. Say “resume” to undo.",
                  "⛔ 紧急开关已打开。自动修复已暂停，工单照样开给人。说“恢复自动修复”可撤销。")
    if re.search(r"\bresume\b|恢复自动|继续自动", t):
        if sender not in _anyone(ctx):
            return _r("resume", False, "Only approvers can resume automation. Nothing changed.", "只有审批人可以恢复自动修复。没有做任何改动。")
        p = os.path.join(ctx.dir, "STOP")
        if os.path.exists(p):
            os.remove(p)
        rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "kill_switch_off", "by": sender, "via": "chat"})
        return _r("resume", True, "▶️ Automatic repairs resumed. The next patrol acts under the normal policy.",
                  "▶️ 自动修复已恢复。下一轮巡检按正常权限执行。")
    return status(ctx, text, devices, last)


def status(ctx, text, devices, last):
    hits = find_devices(text, devices)
    if hits:
        parts = [device_status(ctx, d, last) for d in hits[:3]]
        return _ask(ctx, text, _r("status", True, " ".join(p[0] for p in parts), "".join(p[1] for p in parts), sum((p[2] for p in parts), [])))
    fl = floor_of(text)
    boards = rm.load_json(os.path.join(ctx.dir, "board.json"), {})
    if fl:
        b = next((b for b in boards.values() if b["upstream"].upper() == "SW-%sF" % fl), None)
        if b:
            m = b.get("master") or {}
            refs = [x for x in (m.get("number"), b["our_ticket"]) if x]
            return _ask(ctx, text, _r("status", True, b["summary"]["en"], b["summary"]["zh"], refs))
    bad = [(i, s) for i, s in last["status"].items() if s not in ("healthy",)]
    tks = [t for t in rm.tickets_load(ctx)["tickets"].values() if t["state"] in rm.OPEN_STATES]
    en = "Last patrol %s: %d of %d devices healthy. Not healthy: %s. Open tickets: %s." % (
        (last["ts"] or "?")[11:16], len(last["status"]) - len(bad), len(last["status"]),
        ", ".join("%s (%s)" % (i, ST.get(s, (s,))[0]) for i, s in bad) or "none", ", ".join(t["number"] for t in tks) or "none")
    zh = "上次巡检 %s：%d / %d 台正常。异常：%s。未关工单：%s。" % (
        (last["ts"] or "?")[11:16], len(last["status"]) - len(bad), len(last["status"]),
        "、".join("%s（%s）" % (i, ST.get(s, (s, s))[1]) for i, s in bad) or "无", "、".join(t["number"] for t in tks) or "无")
    return _ask(ctx, text, _r("status", True, en, zh, [t["number"] for t in tks]))


def approve(ctx, sender, text, devices):
    A = ctx.actions
    hits = find_devices(text, devices)
    if not hits:
        return _r("approve", False, "Which device? Example: “approve the profile reset on 5F-502”.", "是哪台设备？例如：“批准 5F-502 重置配置”。")
    d = hits[0]
    if sender not in _approvers(ctx, d["type"]):
        who = ", ".join(_approvers(ctx, d["type"])) or "nobody"
        rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "approval_refused", "device": d["id"], "by": sender, "via": "chat"})
        return _r("approve", False, "Sorry, %s cannot approve repairs on %s. Approvers: %s. Nothing was approved." % (sender, d["id"], who),
                  "抱歉，%s 没有权限批准 %s 的修复。可以批准的人：%s。没有批准任何操作。" % (sender, d["id"], who))
    tk = _ticket_for(ctx, d["id"])
    waiting = (tk or {}).get("awaiting_approval") or []
    if not waiting:
        return _r("approve", False, "Nothing is waiting for approval on %s." % d["id"], "%s 没有等待批准的操作。" % d["id"])
    pick = [a for a in waiting if a in text.lower() or A[a]["en"].lower() in text.lower() or A[a]["zh"].rstrip("文件") in text
            or any(w in text.lower() for w in A[a]["en"].lower().split() if len(w) > 5)]
    act = (pick or waiting)[0] if (pick or len(waiting) == 1) else None
    if not act:
        return _r("approve", False, "More than one step is waiting on %s: %s. Name the one to approve." % (d["id"], ", ".join(A[a]["en"] for a in waiting)),
                  "%s 有多个操作在等批准：%s。请说明批准哪一个。" % (d["id"], "、".join(A[a]["zh"] for a in waiting)))
    ap = rm.load_json(_approvals_path(ctx), {})
    ap[d["id"]] = {"action": act, "by": sender, "ts": ctx.ts(), "via": "chat"}
    rm.save_json(_approvals_path(ctx), ap)
    rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "approved", "device": d["id"], "action": act, "by": sender, "via": "chat"})
    k = next((k for k, n in rm.tickets_load(ctx)["by_key"].items() if n == tk["number"]), None)
    if k:
        rm.ticket_update(ctx, k, sender, "chat_approval", {"action": act, "via": "chat"})
    nxt = ctx.policy.get("patrol", {}).get("interval_minutes", 10)
    return _r("approve", True,
              "✅ Approved by %s: “%s” on %s (%s). The next patrol, within %d min, will run it under the policy." % (sender, A[act]["en"], d["id"], tk["number"], nxt),
              "✅ %s 已批准：对 %s 执行“%s”（%s）。下一轮巡检（%d 分钟内）会按权限执行。" % (sender, d["id"], A[act]["zh"], tk["number"], nxt), [tk["number"]])


def _ask(ctx, question, r):
    import brain
    ans = brain.ask(ctx, "answer_chat", {"question": question, "draft": r["reply"], "allowed_actions": []})
    if ans:
        r["reply"], r["by"] = ans["reply"], ans.get("by")
    return r


def main():
    ap = argparse.ArgumentParser(description="Chat with the crew")
    ap.add_argument("--from", dest="sender", required=True)
    ap.add_argument("--say", required=True)
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--data-dir", default=os.path.join(HERE, "data"))
    a = ap.parse_args()
    ctx = rm.Ctx(a.data_dir, a.lang)
    r = handle(ctx, a.sender, a.say)
    print(r["reply"][a.lang])


if __name__ == "__main__":
    main()
