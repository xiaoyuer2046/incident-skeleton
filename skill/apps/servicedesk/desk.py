#!/usr/bin/env python3
"""App 2 — Service desk L1 triage, on the same skeleton as the office-devices app.

People report problems (Teams, email, portal). Each request walks the same six states:

  RECEIVE      the request, who sent it, from where
  TRIAGE       1. gives orders or asks for admin rights?  -> rejected, routed to Security, no automation
               2. about a device or outage the patrol already knows?  -> linked to that incident, the
                  person gets its live status, nobody is dispatched twice, and it closes when that closes
               3. otherwise: which crew (account / VPN / email / software) and which symptom
  INVESTIGATE  the crew's declarative checks against the directory (app.json -> checks)
  MITIGATE     the shared repair loop (remediate.py) with this app's actions, runbooks and policy
  RESOLVE      the person confirms; or it goes to the right L2 group with everything already tried
  LOG          the ticket, the case history, learning

What is app-specific is config (app.json, actions.json, runbooks.json, policy.json, sources/, data/)
plus this intake plugin. The repair loop, permissions, learning, tickets, harvest, AI and notify are
shared with app 1 unchanged.

Sample data: data/requests.json (requests) and data/directory.json (Entra ID / Intune / Exchange
lookups). Live connectors (Graph, Intune, ServiceNow catalog) are not wired.
"""
import argparse, os, re, sys

APP = os.path.dirname(os.path.abspath(__file__))
REM = os.path.join(APP, "..", "..", "remediation")
sys.path.insert(0, REM)
import remediate as rm
import harvest as hv
import chatops
import notify

CFG = rm.load_json(os.path.join(APP, "app.json"), {})
for _crew, _c in CFG.get("crews", {}).items():  # the crews' symptoms join the shared classifier
    rm.SYMPTOMS[_crew] = [(k, tuple(w)) for k, w in _c.get("symptoms", [])]

STATE_ZH = {"New": "新建", "In Progress": "处理中", "On Hold": "挂起", "Resolved": "已解决"}


def ctx_for(data_dir, lang="en", clock=None, live=False):
    return rm.Ctx(data_dir, lang, live=live, clock=clock, ticket_prefix="INC", ticket_start=20000, app_dir=APP)


def _get(d, path):
    for p in path.split("."):
        d = (d or {}).get(p)
    return d


def _fmt(t, user):
    return re.sub(r"\{([\w.]+)\}", lambda m: str(_get(user, m.group(1))), t)


def classify(text):
    t = text.lower()
    scores = {k: sum(1 for w in c["keywords"] if w in t) for k, c in CFG["crews"].items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def investigate(crew, user):
    out = []
    for c in CFG["crews"][crew]["checks"]:
        v = _get(user, c["path"])
        bad = (("eq" in c and v == c["eq"]) or ("gte" in c and v is not None and v >= c["gte"]) or ("lte" in c and v is not None and v <= c["lte"]))
        msg = c["err"] if bad else c["ok"]
        out.append({"check": c["label"], "result": {k: _fmt(msg[k], user) for k in ("en", "zh")}, "status": "err" if bad else "ok"})
    return out


def _st(name, en, zh):
    return {"name": name, "en": en, "zh": zh}


def _msg(ctx, kind, ref, en, zh):
    return {"kind": kind, "ts": ctx.ts(), "ref": ref, "text": {"en": en, "zh": zh}}


def _known(office, text):
    """A device or outage the office patrol already has open. Returns (kind, ref, answer, extra) or None."""
    if office is None:
        return None
    last = chatops._last(office)
    for d in chatops.find_devices(text, last["devices"]):
        tk = chatops._ticket_for(office, d["id"])
        if tk and tk["state"] in rm.OPEN_STATES:
            en, zh, _ = chatops.device_status(office, d, last)
            return "device", tk["number"], {"en": en, "zh": zh}, {"ci": d["id"]}
    fl = chatops.floor_of(text)
    if fl and re.search(r"wi-?fi|wireless|network|网|无线", text, re.I):
        for k, b in rm.load_json(os.path.join(office.dir, "board.json"), {}).items():
            if b["upstream"].upper() == "SW-%sF" % fl and b["status"] != "closed":
                ref = (b.get("master") or {}).get("number") or b["our_ticket"]
                return "outage", ref, b["summary"], {"board": k, "upstream": b["upstream"]}
    return None


def handle(ctx, office, req, directory):
    user = directory.get(req["user"], {"name": {"en": req["user"], "zh": req["user"]}, "device": {"name": req["user"]}})
    name = user["name"]
    ci = user["device"]["name"]
    text = req["text"]
    rec = {"id": req["id"], "ts": req["ts"], "user": req["user"], "name": name, "channel": req["channel"], "text": text, "states": [], "trace": []}
    S = rec["states"]
    S.append(_st("RECEIVE", "%s request from %s" % (req["channel"], name["en"]), "来自 %s 的 %s 请求" % (name["zh"], req["channel"])))
    msgs = []
    groups = ctx.policy["escalation"]["groups"]
    base = {"short_description": text[:120], "description": text, "caller": name["en"], "cmdb_ci": ci, "message": text,
            "category": "Request", "impact": "3", "urgency": "3", "priority": "4 - Low", "kind": "request", "channel": req["channel"]}

    # TRIAGE 1: orders or admin rights are never automated
    code = hv.injection_reason(text)
    admin = next((w for w in CFG.get("never_automate", []) if w in text.lower()), None)
    if code or admin:
        why_en = {"override": "tries to override the rules", "credential": "contains a password"}.get(code, "asks for admin rights")
        why_zh = {"override": "试图改写规则", "credential": "含有密码"}.get(code, "申请管理员权限")
        num, _ = rm.ticket_upsert(ctx, "request|%s" % req["id"], dict(base, assignment_group=groups["security"], device="security", priority="2 - High"),
                                  "request_rejected", {"reason": code or "admin", "text": text})
        S += [_st("TRIAGE", "Rejected: it %s. Never automated." % why_en, "拒绝：它%s。永不自动处理。" % why_zh),
              _st("INVESTIGATE", "Skipped.", "跳过。"), _st("MITIGATE", "Nothing run.", "什么都没做。"),
              _st("RESOLVE", "Routed to %s for review." % groups["security"], "转给 %s 审查。" % groups["security"]),
              _st("LOG", "Ticket %s · audit entry." % num, "工单 %s · 已记审计。" % num)]
        rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "request_rejected", "request": req["id"], "reason": code or "admin"})
        rec.update(outcome="rejected", ticket=num, group=groups["security"], reply={"en": "", "zh": ""})
        msgs.append(_msg(ctx, "hd_rejected", num, "⛔ %s %s rejected (%s) and sent to %s. No automation." % (req["id"], name["en"], why_en, groups["security"]),
                         "⛔ %s（%s）已拒绝（%s），转给 %s，未做任何自动操作。" % (req["id"], name["zh"], why_zh, groups["security"])))
        return rec, msgs

    # TRIAGE 2: already known to the patrol?
    known = _known(office, text)
    if known:
        kind, ref, ans, extra = known
        num, _ = rm.ticket_upsert(ctx, "request|%s" % req["id"], dict(base, assignment_group=CFG["intake_group"], device="linked"),
                                  "linked_known", {"parent": ref, "kind": kind}, extra={"parent_incident": ref, "caller_zh": name["zh"]})
        rm.ticket_update(ctx, "request|%s" % req["id"], rm.AUTOMATION, "linked_known", {"parent": ref, "answer": ans}, keep_state=True,
                         state="On Hold", hold_reason="Linked to %s" % ref)
        what_en = "the %s outage" % extra.get("upstream") if kind == "outage" else extra.get("ci")
        what_zh = "%s 大面积故障" % extra.get("upstream") if kind == "outage" else extra.get("ci")
        S += [_st("TRIAGE", "Known incident: linked to %s (%s). No new work." % (ref, what_en), "已知故障：挂到 %s（%s），不重复派人。" % (ref, what_zh)),
              _st("INVESTIGATE", "Skipped: the patrol is already on it.", "跳过：巡检已经在处理。"),
              _st("MITIGATE", "Skipped: repairs run on %s." % ref, "跳过：修复在 %s 上进行。" % ref),
              _st("RESOLVE", "Waiting for %s; it closes when that closes." % ref, "等 %s；它关闭时一起关闭。" % ref),
              _st("LOG", "Ticket %s · On Hold, child of %s." % (num, ref), "工单 %s · 挂起，挂在 %s 下。" % (num, ref))]
        reply = {"en": "Thanks %s, we already know. %s We'll tell you when it's fixed." % (name["en"].split(" (")[0].split()[0], ans["en"]),
                 "zh": "谢谢 %s，我们已经知道了。%s修好后会通知你。" % (name["zh"].split("（")[0], ans["zh"])}
        rec.update(outcome="linked", link={"kind": kind, "ref": ref, **extra}, ticket=num, group=CFG["intake_group"], reply=reply)
        msgs.append(_msg(ctx, "hd_reply", num, "To %s: %s" % (name["en"], reply["en"]), "致 %s：%s" % (name["zh"], reply["zh"])))
        return rec, msgs

    # TRIAGE 3: which crew
    crew = classify(text)
    if not crew:
        num, _ = rm.ticket_upsert(ctx, "request|%s" % req["id"], dict(base, assignment_group=CFG["intake_group"], device="unknown"), "request_received", {})
        S += [_st("TRIAGE", "No crew matches; a person reads it.", "没有匹配的班底，交给人看。")]
        rec.update(outcome="escalated", ticket=num, group=CFG["intake_group"], reply={"en": "", "zh": ""})
        return rec, msgs
    label = CFG["crews"][crew]["label"]
    skey = rm.symptom_key(crew, text)
    rec.update(crew=crew, crew_label=label, symptom=skey)
    key = "%s|%s|%s" % (crew, ci, skey)
    num, _ = rm.ticket_upsert(ctx, key, dict(base, assignment_group=CFG["intake_group"], device=crew, symptom=skey), "request_received", {"crew": crew})
    S.append(_st("TRIAGE", "%s crew · symptom “%s”." % (label["en"], skey), "%s班底 · 症状“%s”。" % (label["zh"], skey)))

    # INVESTIGATE: declarative checks
    ev = investigate(crew, user)
    S.append(_st("INVESTIGATE", "; ".join("%s: %s" % (e["check"]["en"], e["result"]["en"]) for e in ev),
                 "；".join("%s：%s" % (e["check"]["zh"], e["result"]["zh"]) for e in ev)))

    # MITIGATE + RESOLVE: the shared repair loop with this app's catalogue and policy
    ns = argparse.Namespace(type=crew, target=ci, ci=ci, source=req["channel"], message=text, message_zh=None)
    res = rm.remediate(ns, ctx, scenario=set(req.get("fixes", [])), quiet=True, evidence=ev)
    rec["trace"] = res["trace"]
    A = ctx.actions
    ran = [t for t in res["trace"] if t["decision"] == "run"]
    S.append(_st("MITIGATE", "; ".join("%s → %s" % (A[t["action"]]["en"], "recovered" if t.get("recovered") else "not recovered") for t in ran) or "nothing allowed to run",
                 "；".join("%s → %s" % (A[t["action"]]["zh"], "恢复" if t.get("recovered") else "没恢复") for t in ran) or "没有可自动执行的步骤"))
    first = name["en"].split(" (")[0].split()[0]
    first_zh = name["zh"].split("（")[0]
    if res["resolved"]:
        fx = ran[-1]["action"]
        if req.get("confirm"):
            S.append(_st("RESOLVE", "%s confirmed: “%s”" % (first, req["confirm"]), "%s 确认：“%s”" % (first_zh, req["confirm"])))
        else:
            S.append(_st("RESOLVE", "Fixed; %s is asked to confirm." % first, "已修好，请 %s 确认。" % first_zh))
        S.append(_st("LOG", "Ticket %s resolved at L1 by automation." % num, "工单 %s 由自动化在一线解决。" % num))
        reply = {"en": "Hi %s, I did this for you: %s. %s" % (first, A[fx]["en"].lower(), "Tell me if it is still broken."),
                 "zh": "%s 你好，已经帮你%s。如果还有问题告诉我。" % (first_zh, A[fx]["zh"])}
        rec.update(outcome="resolved", ticket=num, group=CFG["intake_group"], reply=reply, confirm=req.get("confirm"))
        msgs.append(_msg(ctx, "hd_resolved", num, "To %s: %s" % (name["en"], reply["en"]), "致 %s：%s" % (name["zh"], reply["zh"])))
        return rec, msgs
    grp = groups.get(crew, CFG["intake_group"])
    rm.ticket_update(ctx, key, rm.AUTOMATION, "routed_l2", {"group": grp}, keep_state=True, assignment_group=grp)
    tk = rm.tickets_load(ctx)["tickets"][num]
    waiting = tk.get("awaiting_approval") or []
    left = [x for x in res["left"] if x["why"] == "human"]
    if waiting:
        how_en = "needs approval for “%s”" % ", ".join(A[a]["en"] for a in waiting)
        how_zh = "“%s”需要批准" % "、".join(A[a]["zh"] for a in waiting)
    elif left:
        how_en = "needs a person: %s" % ", ".join(A[x["action"]]["en"] for x in left)
        how_zh = "需要人来做：%s" % "、".join(A[x["action"]]["zh"] for x in left)
    else:
        how_en, how_zh = "automatic steps did not fix it", "自动步骤没能解决"
    S.append(_st("RESOLVE", "Sent to %s: %s. Everything tried is on the ticket." % (grp, how_en), "转给 %s：%s。做过的都写在工单上。" % (grp, how_zh)))
    S.append(_st("LOG", "Ticket %s · %s." % (num, tk["state"]), "工单 %s · %s。" % (num, STATE_ZH.get(tk["state"], tk["state"]))))
    reply = {"en": "Hi %s, I couldn't finish this myself: it %s. %s has it now with everything I checked; you don't need to explain again." % (first, how_en, grp),
             "zh": "%s 你好，这个我没法自己完成：%s。已转给 %s，我查过的都附上了，你不用再解释一遍。" % (first_zh, how_zh, grp)}
    rec.update(outcome="on_hold" if waiting else "escalated", ticket=num, group=grp, reply=reply)
    msgs.append(_msg(ctx, "hd_escalated", num, "To %s: %s" % (name["en"], reply["en"]), "致 %s：%s" % (name["zh"], reply["zh"])))
    return rec, msgs


def close_linked(ctx, office):
    """Linked requests close by themselves when the incident they wait for closes."""
    out, msgs = [], []
    d = rm.tickets_load(ctx)
    boards = rm.load_json(os.path.join(office.dir, "board.json"), {}) if office else {}
    otk = rm.tickets_load(office)["tickets"] if office else {}
    for key, num in list(d["by_key"].items()):
        tk = d["tickets"][num]
        if tk.get("device") != "linked" or tk["state"] not in rm.OPEN_STATES:
            continue
        ref = tk.get("parent_incident")
        done = (ref in otk and otk[ref]["state"] == "Resolved") or any(
            b["status"] == "closed" and ((b.get("master") or {}).get("number") == ref or b["our_ticket"] == ref) for b in boards.values())
        if not done:
            continue
        rm.ticket_resolve(ctx, key, rm.AUTOMATION, "linked_closed", {"parent": ref}, close_notes="Closed with %s." % ref)
        who = tk["caller"]
        en = "To %s: good news, %s is fixed, so your request %s is closed. Tell me if anything is still wrong." % (who, ref, num)
        zh = "致 %s：好消息，%s 已修好，你的请求 %s 已关闭。还有问题随时告诉我。" % (tk.get("caller_zh", who), ref, num)
        msgs.append(_msg(ctx, "hd_linked_closed", num, en, zh))
        out.append({"ticket": num, "parent": ref, "ts": ctx.ts(), "reply": {"en": en, "zh": zh}, "request": key.split("|", 1)[1]})
    return out, msgs


def run(ctx, office, prev_ts):
    """One service-desk round: new requests since prev_ts, then linked requests whose incident closed."""
    reqs = rm.load_json(os.path.join(APP, "data", "requests.json"), [])
    directory = rm.load_json(os.path.join(APP, "data", "directory.json"), {})
    now = ctx.ts()
    recs, msgs = [], []
    for r in sorted(reqs, key=lambda r: r["ts"]):
        if prev_ts < r["ts"] <= now:
            rec, m = handle(ctx, office, r, directory)
            recs.append(rec)
            msgs += m
    closed, m2 = close_linked(ctx, office)
    sent = notify.send(ctx, msgs + m2)
    return {"requests": recs, "closed": closed, "notifications": sent}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Service desk L1 triage (app 2)")
    ap.add_argument("--from", dest="user", default="amy", help="user id in data/directory.json")
    ap.add_argument("--say", required=True)
    ap.add_argument("--channel", default="Teams")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--data-dir", default=os.path.join(APP, "data", "run"))
    ap.add_argument("--office-data", default=os.path.join(REM, "data"))
    ap.add_argument("--works", default="all", help="dry run has no real check: which actions count as working (all | none | id,id)")
    a = ap.parse_args()
    c = ctx_for(a.data_dir, a.lang)
    office = rm.Ctx(a.office_data, a.lang) if os.path.isdir(a.office_data) else None
    from datetime import datetime
    req = {"id": "CLI-" + datetime.now().strftime("%H%M%S"), "ts": c.ts(), "user": a.user, "channel": a.channel, "text": a.say,
           "fixes": list(c.actions) if a.works == "all" else ([] if a.works == "none" else a.works.split(","))}
    rec, m = handle(c, office, req, rm.load_json(os.path.join(APP, "data", "directory.json"), {}))
    print("  [dry run · simulated result: --works %s]" % a.works)
    for s in rec["states"]:
        print("  %-12s %s" % (s["name"], s[a.lang]))
    if rec.get("reply", {}).get(a.lang):
        print("\n  → %s" % rec["reply"][a.lang])
