#!/usr/bin/env python3
"""Watch: the agent's active loop for big outages, so nobody works from stale news.

Every patrol, for each mass outage (an upstream ticket we opened), it actively looks for:
  - a ServiceNow master (major) incident about the same switch or devices,
    and any new work notes, ETA or state change on it
  - outage emails (notice / update / resolved) that mention the switch or the master
Then it:
  - links our ticket as a child of the master (one investigation, no duplicate work)
  - keeps a status board with one shared timeline: our patrol, ServiceNow, email, automation
  - turns a fix in the master's notes into a hint the repair loop tries first, within its
    permissions; physical steps and anything unmapped go to engineers
  - posts our own progress back to the master (devices healthy N of M, what we fixed)
  - closes the board only when the master is resolved AND our patrol confirms the devices are healthy

Sources here are sample files (sources/servicenow_major.json, sources/outage_mail.json). A live version
would poll the ServiceNow Table API for major incidents and a mailbox; those connectors are not wired.
The summary line is a template; if INCIDENT_AI_CMD is set, the board packet is sent to it to write one.
"""
import json, os, shlex, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remediate as rm
import harvest as hv

SRC = os.path.join(HERE, "sources")


def _board_path(ctx):
    return os.path.join(ctx.dir, "board.json")


def load_board(ctx):
    return rm.load_json(_board_path(ctx), {})


def _vis(ctx, ts):
    return rm.to_epoch(ts) <= ctx.clock()


def masters(ctx):
    out = []
    for m in rm.load_json(os.path.join(SRC, "servicenow_major.json"), []):
        if not _vis(ctx, m["opened_at"]):
            continue
        notes = [n for n in m.get("notes", []) if _vis(ctx, n["ts"])]
        last = notes[-1] if notes else {}
        eta = next((n.get("eta") for n in reversed(notes) if "eta" in n), None)
        out.append(dict(m, notes=notes, state=last.get("state", "New"), eta=eta))
    return out


def mails(ctx):
    return [x for x in rm.load_json(os.path.join(SRC, "outage_mail.json"), []) if _vis(ctx, x["ts"])]


def _item(ts, source, text, **kw):
    d = {"ts": ts, "source": source, "text": text}
    d.update(kw)
    return d


def poll(ctx):
    """Before repairs: find masters and mail for every open outage board. Returns (board, hints)."""
    board = load_board(ctx)
    tk_all = rm.tickets_load(ctx)
    hints, polled = {}, {"servicenow": 0, "email": 0}
    ms, mail = masters(ctx), mails(ctx)
    polled["servicenow"], polled["email"] = len(ms), len(mail)
    for key, num in tk_all["by_key"].items():
        if not key.startswith("upstream|"):
            continue
        tk = tk_all["tickets"][num]
        up, devs = tk["cmdb_ci"], tk.get("devices", [])
        b = board.get(key)
        if not b:
            b = board[key] = {"key": key, "upstream": up, "our_ticket": num, "devices": devs, "timeline": [], "seen": [],
                              "master": None, "solutions": [], "status": "open", "opened": tk["opened_at"], "posted": []}
            b["timeline"].append(_item(tk["opened_at"], "patrol", {
                "en": "Our patrol saw %d devices behind %s fail together. Opened %s for %s; per-device reboots held back." % (len(devs), up, num, tk["assignment_group"]),
                "zh": "我们的巡检发现 %s 下 %d 台设备同时掉线。已开 %s 给 %s；暂停逐台重启。" % (up, len(devs), num, tk["assignment_group"])}, ref=num))
        if b["status"] == "closed":
            continue
        b["checked"] = ctx.ts()
        b["polled"] = polled
        m = next((x for x in ms if x.get("ci") == up or set(x.get("affected", [])) & set(devs)), None)
        if not m and not b.get("searched_none"):
            b["searched_none"] = True
            b["timeline"].append(_item(ctx.ts(), "automation", {
                "en": "Searched ServiceNow for a master incident about %s: none yet. Searched the outage mailbox: nothing yet." % up,
                "zh": "在 ServiceNow 里找 %s 的总单：暂时没有。查了故障邮件：暂时没有。" % up}))
        if m:
            if not b["master"]:
                rm.ticket_update(ctx, key, rm.AUTOMATION, "linked_master", {"master": m["number"]}, parent_incident=m["number"])
                b["linked_at"] = ctx.ts()
                b["timeline"].append(_item(ctx.ts(), "automation", {
                    "en": "Found master incident %s (%s). Linked our %s as its child, so there is one investigation." % (m["number"], m["owner"], num),
                    "zh": "找到总单 %s（%s）。已把我们的 %s 挂成它的子单，只查一次。" % (m["number"], m["owner"], num)}, ref=m["number"], kind="link"))
            b["master"] = {k: m.get(k) for k in ("number", "short_description", "state", "assignment_group", "owner", "opened_at", "eta", "priority")}
            for n in m["notes"]:
                nid = "sn:%s:%s" % (m["number"], n["ts"])
                if nid in b["seen"]:
                    continue
                b["seen"].append(nid)
                b["timeline"].append(_item(n["ts"], "servicenow", n["text"], author=n["author"], ref=m["number"], state=n.get("state")))
                for aid in hv.map_actions(n["text"]["en"]):
                    a = ctx.actions.get(aid, {})
                    if a and not a.get("physical") and not any(s.get("action") == aid for s in b["solutions"]):
                        b["solutions"].append({"kind": "auto", "action": aid, "ref": m["number"], "ts": n["ts"], "text": n["text"], "outcome": None})
                if n.get("engineer"):
                    b["solutions"].append({"kind": "engineer", "action": None, "ref": m["number"], "ts": n["ts"], "text": n["engineer"], "outcome": "for_engineer"})
        for x in mail:
            mid = "mail:" + x["id"]
            if mid in b["seen"]:
                continue
            related = up in x["text"]["en"] or (m and m["number"] in x["subject"]["en"])
            if not related:
                continue
            b["seen"].append(mid)
            b["timeline"].append(_item(x["ts"], "email", x["subject"], author=x["from"], body=x["text"], mail_kind=x.get("kind")))
        for s in b["solutions"]:
            if s["kind"] == "auto":
                for d in devs:
                    hints.setdefault(d, {})[s["action"]] = s["ref"]
        b["timeline"].sort(key=lambda i: i["ts"])
    rm.save_json(_board_path(ctx), board)
    return board, hints


def after(ctx, rows, results):
    """After repairs: record what automation did, post progress to the master, set the board status."""
    board = load_board(ctx)
    by_id = {r["id"]: r for r in rows}
    res_by = {r["ci"]: r for r in results}
    for key, b in board.items():
        if b["status"] == "closed":
            continue
        up, devs = b["upstream"], b["devices"]
        st = {}
        for d in devs:
            r, res = by_id.get(d, {}), res_by.get(d)
            st[d] = "healthy" if r.get("status") == "healthy" or (res and res["resolved"]) else r.get("status", "unknown")
            if res:
                ran = [x for x in res["trace"] if x["decision"] == "run"]
                fx = ran[-1] if ran else None
                if res["resolved"] and fx:
                    hint = fx.get("hint")
                    b["timeline"].append(_item(ctx.ts(), "automation", {
                        "en": "%s still down after %s came back. Tried “%s”%s (%s) → recovered." % (d, up, ctx.actions[fx["action"]]["en"],
                               " from the master's guidance" if hint else "", fx["tier"].replace("_", " ")),
                        "zh": "%s 在 %s 恢复后仍不在线。尝试“%s”%s（%s）→ 已恢复。" % (d, up, ctx.actions[fx["action"]]["zh"],
                               "（来自总单的修法）" if hint else "", {"auto": "自动", "notify_then_act": "先通知再修", "approval": "批准后"}.get(fx["tier"], fx["tier"]))}, device=d))
                    for s in b["solutions"]:
                        if s.get("action") == fx["action"]:
                            s["outcome"] = "fixed:" + d
                elif not res["resolved"]:
                    tried = ", ".join(ctx.actions[x["action"]]["en"] for x in ran) or "nothing permitted"
                    b["timeline"].append(_item(ctx.ts(), "automation", {
                        "en": "%s still down. Tried: %s. Not recovered; the engineer steps from the master are on the ticket." % (d, tried),
                        "zh": "%s 仍不在线。已试：%s。没恢复；总单里的人工步骤已写进工单。" % (d, tried)}, device=d))
                    for s in b["solutions"]:
                        if s["kind"] == "auto" and any(x["action"] == s["action"] for x in ran):
                            s["outcome"] = "failed:" + d
        b["device_status"] = st
        healthy = sum(1 for v in st.values() if v == "healthy")
        sig = "%d/%d" % (healthy, len(devs))
        if b["master"] and b.get("posted_sig") != sig:
            fixed = [t for t in b["timeline"] if t["source"] == "automation" and t.get("device") and t["ts"] == ctx.ts()]
            note = {"ts": ctx.ts(), "author": rm.AUTOMATION, "ref": b["master"]["number"], "text": {
                "en": "Automated patrol at %s: %d of %d devices behind %s healthy.%s Child ticket %s." % (
                    ctx.ts()[11:16], healthy, len(devs), up, (" " + fixed[-1]["text"]["en"]) if fixed else "", b["our_ticket"]),
                "zh": "自动巡检 %s：%s 下 %d / %d 台正常。%s子单 %s。" % (
                    ctx.ts()[11:16], up, healthy, len(devs), (fixed[-1]["text"]["zh"] + " ") if fixed else "", b["our_ticket"])}}
            b["posted"].append(note)
            b["posted_sig"] = sig
            b["timeline"].append(_item(ctx.ts(), "automation", {
                "en": "Posted our progress to master %s: %s healthy." % (b["master"]["number"], sig),
                "zh": "已把进度写到总单 %s：%s 正常。" % (b["master"]["number"], sig)}, ref=b["master"]["number"], kind="post"))
        master_done = bool(b["master"]) and b["master"]["state"] in ("Resolved", "Closed")
        if healthy == len(devs) and master_done:
            b["status"] = "closed"
            b["closed_at"] = ctx.ts()
            b["timeline"].append(_item(ctx.ts(), "automation", {
                "en": "Board closed: master %s is resolved and our patrol confirms %d/%d healthy." % (b["master"]["number"], healthy, len(devs)),
                "zh": "面板关闭：总单 %s 已解决，巡检确认 %d/%d 正常。" % (b["master"]["number"], healthy, len(devs))}, kind="close"))
        elif healthy == len(devs):
            b["status"] = "recovering"
        else:
            b["status"] = "open"
        b["summary"] = summarize(b, ctx)
        b["timeline"].sort(key=lambda i: i["ts"])
    rm.save_json(_board_path(ctx), board)
    return board


def summarize(b, ctx=None):
    """Template draft; the brain (brain.py) may rewrite it. The template is the fallback."""
    draft = _template(b)
    import brain
    compact = {k: b.get(k) for k in ("upstream", "devices", "device_status", "status", "master", "our_ticket")}
    compact["timeline"] = [{"ts": t["ts"], "source": t["source"], "text": t["text"]} for t in b["timeline"][-8:]]
    ans = brain.ask(ctx, "summarize_outage_board", {"board": compact, "draft": draft, "allowed_actions": []})
    if ans:
        b["summary_by"] = ans.get("by")
        return ans["summary"]
    b["summary_by"] = None
    return draft


def _template(b):
    up, devs = b["upstream"], b["devices"]
    st = b.get("device_status", {})
    healthy = sum(1 for v in st.values() if v == "healthy")
    m = b.get("master")
    last_sn = next((t for t in reversed(b["timeline"]) if t["source"] == "servicenow"), None)
    last_mail = next((t for t in reversed(b["timeline"]) if t["source"] == "email"), None)
    if b["status"] == "closed":
        return {"en": "Resolved. Master %s closed; our patrol confirms %d/%d healthy%s." % (m["number"], healthy, len(devs), "; '%s' email seen" % last_mail["text"]["en"] if last_mail else ""),
                "zh": "已解决。总单 %s 已关闭；巡检确认 %d/%d 正常%s。" % (m["number"], healthy, len(devs), "；已收到邮件“%s”" % last_mail["text"]["zh"] if last_mail else "")}
    if not m:
        return {"en": "%d devices behind %s down. No master incident or outage email yet; our %s is with the network team." % (len(devs), up, b["our_ticket"]),
                "zh": "%s 下 %d 台设备掉线。暂时没有总单，也没有故障邮件；我们的 %s 已在网络组手上。" % (up, len(devs), b["our_ticket"])}
    eta = (" ETA %s." % m["eta"]) if m.get("eta") else ""
    eta_zh = ("预计 %s。" % m["eta"]) if m.get("eta") else ""
    latest = last_sn["text"] if last_sn else {"en": "", "zh": ""}
    if b["status"] == "recovering":
        return {"en": "Our side recovered: %d/%d healthy. Waiting for master %s (%s) to close. Latest: %s" % (healthy, len(devs), m["number"], m["state"], latest["en"]),
                "zh": "我们这边已恢复：%d/%d 正常。等总单 %s（%s）关闭。最新：%s" % (healthy, len(devs), m["number"], {"In Progress": "处理中", "New": "新建"}.get(m["state"], m["state"]), latest["zh"])}
    return {"en": "Master %s is %s with %s.%s Latest: %s %d/%d healthy." % (m["number"], m["state"], m["assignment_group"], eta, latest["en"], healthy, len(devs)),
            "zh": "总单 %s %s，由 %s 处理。%s最新：%s 目前 %d/%d 正常。" % (m["number"], {"In Progress": "处理中", "New": "新建"}.get(m["state"], m["state"]), m["assignment_group"], eta_zh, latest["zh"], healthy, len(devs))}
