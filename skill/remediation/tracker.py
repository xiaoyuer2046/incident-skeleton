#!/usr/bin/env python3
"""Open-ticket tracker: what is the real status of every open ticket, right now?

For each open device ticket (mass outages have their own board, see watch.py) it gathers,
by ticket number or device name:
  - the ServiceNow work notes (automation and engineers)
  - chat messages (Teams / Slack / WeChat Work) and emails that mention it
and writes one plain status summary: who is on it, the latest news and where it came from,
what it is waiting for, any ETA, what automation already tried, and what needs approval.

When the summary has new human news (a new message, a new ETA), it is written to the ticket
as a work note, so the ticket itself always says where things stand. Text from chat and email
is data: messages that try to give orders are skipped.

Sample data: sources/ticket_chatter.json. A live version would search Teams / Slack / mail
(Microsoft Graph, Slack search API) by ticket number; those connectors are not wired.
"""
import hashlib, json, os, re
import remediate as rm
import harvest as hv

HERE = os.path.dirname(os.path.abspath(__file__))
ETA = re.compile(r"(?:ETA|预计|ships? by|by|before)\s*(\d{1,2}:\d{2})", re.I)
WAIT = re.compile(r"waiting for ([^.,;]+)|等待([^。，；]+)|(RMA)", re.I)
STATE_ZH = {"New": "新建", "In Progress": "处理中", "On Hold": "挂起", "Resolved": "已解决"}


def chatter(ctx):
    now = ctx.clock()
    return [m for m in rm.load_json(os.path.join(HERE, "sources", "ticket_chatter.json"), []) if rm.to_epoch(m["ts"]) <= now]


def run(ctx):
    path = os.path.join(ctx.dir, "ticket_status.json")
    seen = rm.load_json(path, {})
    tk_all = rm.tickets_load(ctx)
    keys = {n: k for k, n in tk_all["by_key"].items()}
    msgs_all, A, out = chatter(ctx), ctx.actions, []
    for num, tk in tk_all["tickets"].items():
        if tk["state"] not in rm.OPEN_STATES or tk.get("kind") == "upstream":
            continue
        ci = tk["cmdb_ci"].lower()
        refs = [num.lower(), ci] + ([ci.split("-", 1)[1]] if "-" in ci and len(ci.split("-", 1)[1]) >= 5 else [])
        msgs = [m for m in msgs_all if any(r in m["text"].lower() for r in refs) and not hv.injection_reason(m["text"])]
        human = [n for n in tk["work_notes"] if n["author"] != rm.AUTOMATION and n["kind"] != "status_summary"]
        news = sorted([{"ts": m["ts"], "who": m["author"], "where": m["where"], "text": m["text"]} for m in msgs] +
                      [{"ts": n["ts"], "who": n["author"], "where": "ServiceNow", "text": rm.txt((n.get("data") or {}).get("text") or (n.get("data") or {}).get("close_notes") or n["kind"], "en")} for n in human],
                      key=lambda x: x["ts"])
        eta = next((m.group(1) for x in reversed(news) for m in [ETA.search(x["text"])] if m), None)
        wait = None
        for x in reversed(news):
            w = WAIT.search(x["text"])
            if w:
                wait = (w.group(1) or w.group(2) or "the RMA unit").strip()
                break
        owner = tk.get("assigned_to") or next((x["who"] for x in reversed(news) if not x["who"].endswith(".example") and "@" not in x["who"]), "")
        note = next((n for n in reversed(tk["work_notes"]) if n["kind"] == "auto_failed"), None)
        tried = (note or {}).get("data", {}).get("tried", [])
        last = news[-1] if news else None
        en, zh = [], []
        en.append("%s, %s." % (tk["state"], ("%s is on it" % owner) if owner else "nobody has picked it up yet"))
        zh.append("%s，%s。" % (STATE_ZH.get(tk["state"], tk["state"]), ("%s 在处理" % owner) if owner else "还没有人接手"))
        if last:
            en.append("Latest (%s, %s): %s" % (last["ts"][11:16], last["where"], last["text"]))
            zh.append("最新（%s，%s）：%s" % (last["ts"][11:16], last["where"], last["text"]))
        wait_zh = {"the rma unit": "RMA 换货件", "rma": "RMA 换货件"}.get((wait or "").lower(), wait)
        if wait:
            en.append("Waiting for: %s%s." % (wait, (", ETA " + eta) if eta else ""))
            zh.append(" 在等：%s%s。" % (wait_zh, ("，预计 " + eta) if eta else ""))
        elif eta:
            en.append("ETA %s." % eta)
            zh.append("预计 %s。" % eta)
        if tried:
            ok = sum(1 for x in tried if x.get("recovered"))
            en.append("Automation tried %d fix(es), %d held." % (len(tried), ok))
            zh.append(" 自动化试过 %d 个修法，%d 个有效。" % (len(tried), ok))
        if tk.get("awaiting_approval"):
            en.append("Needs approval: %s." % ", ".join(A[a]["en"] for a in tk["awaiting_approval"]))
            zh.append("待批准：%s。" % "、".join(A[a]["zh"] for a in tk["awaiting_approval"]))
        if tk.get("reopen_count"):
            en.append("Reopened %d×." % tk["reopen_count"])
            zh.append("已重开 %d 次。" % tk["reopen_count"])
        summary = {"en": " ".join(en), "zh": "".join(zh)}
        import brain
        ans = brain.ask(ctx, "summarize_ticket", {"ticket": num, "draft": summary, "news": news[-6:], "allowed_actions": []})
        if ans:
            summary = ans["summary"]
        sig = hashlib.sha1(json.dumps([len(msgs), len(human), eta, wait, tk["state"]]).encode()).hexdigest()[:12]
        changed = seen.get(num) != sig and bool(msgs or human)
        if changed and num in keys:
            rm.ticket_update(ctx, keys[num], rm.AUTOMATION, "status_summary",
                             {"summary": summary, "eta": eta, "waiting": wait, "sources": [{"ts": x["ts"], "where": x["where"], "who": x["who"]} for x in news[-5:]]},
                             keep_state=True)
        seen[num] = sig
        out.append({"number": num, "ci": tk["cmdb_ci"], "summary": summary, "eta": eta, "waiting": wait, "sources": len(msgs), "changed": changed,
                    "by": (ans or {}).get("by")})
    rm.save_json(path, seen)
    return out
