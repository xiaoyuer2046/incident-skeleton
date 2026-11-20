#!/usr/bin/env python3
"""KB drafts: once a fix has proven itself here, write the ServiceNow KB article for it.

A fix qualifies when, for one device type and symptom, it held at the delayed re-check at least
min_confirmed (2) times and its success rate is at least min_rate (0.5). The draft lists the
steps, what NOT to bother with (fixes that keep failing on this symptom), the evidence, and the
case-library sources. It is written as a draft awaiting human review, never published.

The brain (brain.py, task "draft_kb") may rewrite the wording; the template is the fallback.
A live version would POST to /api/now/table/kb_knowledge with workflow_state=draft (not wired).
"""
import os
import remediate as rm

TYPE = {"printer": ("Printer", "打印机"), "signage": ("Digital signage", "数字标牌"), "av": ("Meeting-room AV", "会议室音视频"),
        "wifiap": ("Wireless AP", "无线 AP")}
SYM = {"jam": ("paper jam", "卡纸"), "offline": ("offline", "离线"), "down": ("black screen / not updating", "黑屏 / 不更新"),
       "hung": ("frozen panel / cannot join", "面板卡死 / 进不了会"), "generic": ("general fault", "一般故障")}


def run(ctx):
    cfg = ctx.policy.get("kb_draft", {})
    need, min_rate = cfg.get("min_confirmed", 2), cfg.get("min_rate", 0.5)
    path = os.path.join(ctx.dir, "kb_drafts.json")
    drafts = rm.load_json(path, {})
    rows = [r for r in rm.read_jsonl(ctx.attempts_path) if r.get("outcome") == "ran"]
    agg = {}
    for r in rows:
        a = agg.setdefault((r["device"], r["symptom"], r["action"]), {"tries": 0, "ok": 0, "held": 0, "where": []})
        a["tries"] += 1
        a["ok"] += 1 if r.get("verified") else 0
        if r.get("confirmed") is True:
            a["held"] += 1
            if r["target"] not in a["where"]:
                a["where"].append(r["target"])
    lib = rm.load_json(ctx.library_path, {}).get("entries", [])
    new = []
    for (dev, sym, act), a in sorted(agg.items()):
        key = "%s|%s|%s" % (dev, sym, act)
        if key in drafts or a["held"] < need or a["ok"] / a["tries"] < min_rate:
            continue
        dont = [(x, b) for (d2, s2, x), b in agg.items() if d2 == dev and s2 == sym and x != act and b["tries"] >= 2 and b["ok"] / b["tries"] <= 0.34]
        src = [e["id"] for e in lib if e.get("device") == dev and e.get("action") == act]
        A = ctx.actions
        tn, sn = TYPE[dev], SYM.get(sym, SYM["generic"])
        draft = {
            "number": "KB-DRAFT-%04d" % (len(drafts) + 1), "key": key, "ts": ctx.ts(), "status": "draft",
            "device": dev, "symptom": sym, "action": act, "held": a["held"], "ok": a["ok"], "tries": a["tries"], "where": a["where"], "sources": src,
            "title": {"en": "%s: %s — %s" % (tn[0], sn[0], A[act]["en"]), "zh": "%s：%s —— %s" % (tn[1], sn[1], A[act]["zh"])},
            "steps": {"en": ["Confirm the symptom: %s." % sn[0], A[act]["en"] + ".", "Wait 10 minutes and check the device is still healthy."],
                      "zh": ["确认症状：%s。" % sn[1], A[act]["zh"] + "。", "等 10 分钟，确认设备仍然正常。"]},
            "dont": {"en": ["%s — helped %d of %d times here." % (A[x]["en"], b["ok"], b["tries"]) for x, b in dont],
                     "zh": ["%s —— 在这里 %d / %d 次有效。" % (A[x]["zh"], b["ok"], b["tries"]) for x, b in dont]},
            "evidence": {"en": "Worked %d of %d times; held at the 10-minute re-check %d times (%s)." % (a["ok"], a["tries"], a["held"], ", ".join(a["where"])),
                         "zh": "%d / %d 次有效；%d 次在 10 分钟复查时稳住（%s）。" % (a["ok"], a["tries"], a["held"], "、".join(a["where"]))},
        }
        import brain
        ans = brain.ask(ctx, "draft_kb", {"draft": draft, "allowed_actions": []})
        draft["written_by"] = (ans or {}).get("by")
        drafts[key] = draft
        new.append(draft)
    rm.save_json(path, drafts)
    msgs = [{"kind": "kb_draft", "ts": ctx.ts(), "ref": d["number"], "text": {
        "en": "📝 KB draft %s written for review: “%s”. %s" % (d["number"], d["title"]["en"], d["evidence"]["en"]),
        "zh": "📝 已起草 KB %s，等待审核：“%s”。%s" % (d["number"], d["title"]["zh"], d["evidence"]["zh"])}} for d in new]
    return new, msgs
