#!/usr/bin/env python3
"""Pre-meeting check: make sure the room works before people walk in.

For every meeting that starts within lead_minutes (30), it looks at the room's latest
patrol result (and whether the repair loop just fixed it):
  ready     the room is healthy
  fixed     the room had a fault this patrol and automation fixed it before the meeting
  at_risk   the room is down: raise the ticket to High, tell the organizer, and name a free,
            healthy room as plan B. Within move_minutes (15) of the start it recommends moving.
When an at-risk room recovers, the organizer is told it is fine to stay.

Calendar data comes from sources/calendar.json. A live version would read Exchange / Outlook
(Microsoft Graph) or Google Calendar room resources; that connector is not wired.
"""
import os
import remediate as rm

HERE = os.path.dirname(os.path.abspath(__file__))


def calendar():
    return rm.load_json(os.path.join(HERE, "sources", "calendar.json"), [])


def _busy(cal, room, start, end, skip):
    return any(m["room"] == room and m["id"] != skip and m["start"] < end and start < m["end"] for m in cal)


def run(ctx, rows, results, devices):
    cfg = ctx.policy.get("premeeting", {})
    lead, move_min = cfg.get("lead_minutes", 30) * 60, cfg.get("move_minutes", 15) * 60
    path = os.path.join(ctx.dir, "premeeting_state.json")
    state = rm.load_json(path, {})
    status = {r["id"]: r["status"] for r in rows}
    fixed = {r["ci"] for r in results if r["resolved"]}
    ok = lambda d: status.get(d) == "healthy" or d in fixed
    now, cal, out, msgs = ctx.clock(), calendar(), [], []
    names = {d["id"]: d.get("loc", {}) for d in devices}
    for m in cal:
        left = rm.to_epoch(m["start"]) - now
        if not 0 <= left <= lead:
            continue
        room = m["room"]
        res = next((r for r in results if r["ci"] == room), None)
        st = ("fixed" if room in fixed else "ready") if ok(room) else "at_risk"
        prev = state.get(m["id"], {})
        rec = {"id": m["id"], "title": m["title"], "room": room, "start": m["start"], "end": m["end"], "organizer": m["organizer"],
               "attendees": m["attendees"], "vip": bool(m.get("vip")), "state": st, "prev": prev.get("state"), "minutes": int(left // 60)}
        when = m["start"][11:16]
        org_en, org_zh = m["organizer"].get("en"), m["organizer"].get("zh")
        title_en, title_zh = m["title"]["en"], m["title"]["zh"]
        if st == "at_risk":
            alt = next((d["id"] for d in devices if d["type"] == "av" and d["id"] != room and ok(d["id"])
                        and not _busy(cal, d["id"], m["start"], m["end"], m["id"])), None)
            tk = (res or {}).get("ticket") or {}
            move = bool(alt) and left <= move_min
            rec.update(alternative=alt, ticket=tk.get("number"), action="move" if move else "watch")
            if prev.get("state") != "at_risk" or (move and prev.get("action") != "move"):
                if res and tk.get("number"):
                    rm.ticket_update(ctx, res["key"], rm.AUTOMATION, "meeting_risk",
                                     {"meeting": title_en, "start": when, "attendees": m["attendees"], "alternative": alt, "move": move},
                                     priority="2 - High", urgency="1")
                alt_en = (" Plan B: %s is free and healthy." % alt) if alt else " No free healthy room found."
                alt_zh = ("备选：%s 空闲且正常。" % alt) if alt else "没有找到空闲且正常的房间。"
                if move:
                    msgs.append(_m(ctx, "room_move", tk.get("number"),
                        "🔁 To %s: “%s” at %s — %s is still down. Please move to %s. Ticket %s is High priority." % (org_en, title_en, when, room, alt, tk.get("number")),
                        "🔁 致 %s：%s 的“%s”——%s 仍未修好。请改到 %s。工单 %s 已提为高优先级。" % (org_zh, when, title_zh, room, alt, tk.get("number"))))
                else:
                    msgs.append(_m(ctx, "meeting_risk", tk.get("number"),
                        "⚠️ To %s: room %s for “%s” at %s has a fault. We are on it (ticket %s, now High).%s" % (org_en, room, title_en, when, tk.get("number"), alt_en),
                        "⚠️ 致 %s：%s 的“%s”所在房间 %s 出了故障，正在处理（工单 %s，已提为高）。%s" % (org_zh, when, title_zh, room, tk.get("number"), alt_zh)))
        elif st == "fixed":
            if prev.get("state") == "at_risk":
                msgs.append(_m(ctx, "meeting_ok_again", None,
                    "✅ To %s: room %s is fixed. “%s” at %s can stay where it is." % (org_en, room, title_en, when),
                    "✅ 致 %s：%s 已修好，%s 的“%s”不用换房间。" % (org_zh, room, when, title_zh)))
            else:
                msgs.append(_m(ctx, "meeting_saved", None,
                    "✅ To %s: room %s had a fault %d min before “%s”; it was fixed automatically. You are good to go." % (org_en, room, left // 60, title_en),
                    "✅ 致 %s：“%s”开始前 %d 分钟，%s 出了故障，已经自动修好，可以照常开会。" % (org_zh, title_zh, left // 60, room)))
        state[m["id"]] = {"state": st, "action": rec.get("action")}
        out.append(rec)
    rm.save_json(path, state)
    return out, msgs


def _m(ctx, kind, ref, en, zh):
    return {"kind": kind, "ts": ctx.ts(), "ref": ref, "text": {"en": en, "zh": zh}}
