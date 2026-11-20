#!/usr/bin/env python3
"""Harvest: the case library collects fixes on its own.

Sources (sample files in sources/, or a live ServiceNow when configured):
  ServiceNow KB articles, closed ServiceNow incidents, team chat groups
  (Teams / Slack / WeChat Work), email threads, and the incidents this system
  escalated that engineers later resolved (so it learns from engineers).

For every reply that looks like a fix it decides a verdict:
  verified    the asker confirmed it worked, the KB article is published with
              >= 3 helpful votes, or the incident closed "Solved (Permanently)"
  failed      the asker said it did not work, or the incident came back
  unverified  nobody confirmed
  rejected    the text tries to give orders (override instructions, pipe a
              download into a shell, switch off a safeguard, a credential).
              Never used; kept in a list for a person to review.

All text is DATA, never instructions. A fix becomes usable by automation only
if it maps to an action in actions.json, and policy.json still decides whether
it may run. Anything else is advice for the engineer, attached to the ticket.

  python3 harvest.py --data-dir data
"""
import argparse, base64, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remediate as rm

SRC = os.path.join(HERE, "sources")

# phrase in a message -> action id. The no-AI floor; an AI advisor can map better.
KEYWORDS = [
    ("stuck print jobs", "clear-queue"), ("stuck jobs", "clear-queue"), ("clear the queue", "clear-queue"),
    ("清空打印", "clear-queue"), ("清空队列", "clear-queue"),
    ("print spooler", "restart-spooler"), ("restart the spooler", "restart-spooler"), ("重启打印后台", "restart-spooler"),
    ("re-add the print queue", "readd-queue"),
    ("player cache", "clear-player-cache"), ("清除播放器缓存", "clear-player-cache"), ("清缓存", "clear-player-cache"),
    ("re-push", "repush-content"), ("重推", "repush-content"),
    ("reboot the player", "reboot-player"), ("重启播放器", "reboot-player"),
    ("restart the room app", "restart-room-app"), ("重启房间应用", "restart-room-app"),
    ("reboot the codec", "reboot-codec"), ("重启编解码器", "reboot-codec"),
    ("reboot the room controller", "reboot-controller"), ("重启控制器", "reboot-controller"),
    ("controller profile", "reset-room-profile"), ("重置房间", "reset-room-profile"),
    ("reboot the ap", "controller-reboot-ap"), ("through the controller", "controller-reboot-ap"),
    ("power-cycle the poe", "poe-cycle"), ("bounce the poe", "poe-cycle"),
]

DEVICE_RE = {
    "printer": r"printer|print job|spooler|13\.\d+|toner|打印",
    "signage": r"signage|player|\bcms\b|标牌|播放器",
    "av": r"zoom|teams room|meeting room|room app|codec|room controller|会议室|编解码|房间应用|面板",
    "wifiap": r"\bap\b|access point|wi-?fi|wireless|\bpoe\b|无线",
}

INJECTION = [
    (r"ignore (all |any |your |the )?(previous |prior )?(rules|instructions|policy)", "override"),
    (r"忽略.{0,6}(规则|指令|限制)", "override"),
    (r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh", "pipe_shell"),
    (r"rm\s+-rf", "destructive"),
    (r"(disable|turn off|skip)\s+(the\s+)?(approval|policy|safety|audit)", "disable_safeguard"),
    (r"(关闭|跳过).{0,4}(审批|权限|审计)", "disable_safeguard"),
    (r"(password|passwd|密码)\s*[:=：]", "credential"),
]

NEG = r"didn'?t work|did not work|still (broken|down|frozen)|no luck|没用|还是不行|没解决|无效"
POS = r"\bworks?\b|worked|fixed|resolved|solved|confirmed|解决了|好了|可以了|搞定|恢复了"
ADVICE = r"restart|reboot|clear|replace|reset|check|move|swap|re-?push|power-?cycle|重启|清|更换|换|检查|重置|移到|重推"


def map_actions(text):
    t = (text or "").lower()
    out = []
    for kw, aid in KEYWORDS:
        if kw in t and aid not in out:
            out.append(aid)
    return out


def detect_device(text):
    t = (text or "").lower()
    best = max(DEVICE_RE, key=lambda k: len(re.findall(DEVICE_RE[k], t)))
    return best if re.search(DEVICE_RE[best], t) else None


def injection_reason(text):
    for pat, code in INJECTION:
        if re.search(pat, text or "", re.I):
            return code
    return None


def norm(text):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", (text or "").lower())[:50]


def fetch_kb(ctx):
    """Live ServiceNow KB when SN_INSTANCE/SN_USER/SN_PASSWORD are set and live mode is on (untested), else the sample."""
    inst, user, pw = os.environ.get("SN_INSTANCE"), os.environ.get("SN_USER"), os.environ.get("SN_PASSWORD")
    if inst and user and pw and ctx.live:
        url = "https://%s/api/now/table/kb_knowledge?sysparm_limit=200&sysparm_fields=number,short_description,text,workflow_state,sys_updated_on,helpful_count&sysparm_query=%s" % (
            inst, urllib.parse.quote("workflow_state=published"))
        req = urllib.request.Request(url, headers={"Accept": "application/json", "Authorization": "Basic " + base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                rows = json.load(r).get("result", [])
            return [{"number": x.get("number"), "short_description": x.get("short_description", ""), "text": re.sub("<[^>]+>", " ", x.get("text", "")),
                     "workflow_state": x.get("workflow_state"), "updated": (x.get("sys_updated_on") or "1970-01-01 00:00:00").replace(" ", "T"),
                     "helpful": int(x.get("helpful_count") or 0)} for x in rows], "servicenow"
        except Exception:
            pass
    return rm.load_json(os.path.join(SRC, "servicenow_kb.json"), []), "sample"


def harvest(ctx):
    now = ctx.clock()
    vis = lambda ts: rm.to_epoch(ts) <= now
    found, rejected, stats = [], [], {}

    def st(name):
        return stats.setdefault(name, {"scanned": 0, "verified": 0, "unverified": 0, "failed": 0, "rejected": 0, "skipped": 0})

    def add(device, text, act, src, verdict, context=""):
        if not device:
            return
        src = dict(src, verdict=verdict, text=text)
        # the symptom comes from the question plus the reply, not the reply alone
        found.append({"device": device, "symptom": rm.symptom_key(device, context + " " + text), "action": act, "text": text, "src": src})

    def reject(kind, where, author, ts, text, code):
        rejected.append({"type": kind, "where": where, "author": author, "ts": ts, "reason": code, "text": text[:180]})
        st(kind)["rejected"] += 1

    # 1. ServiceNow KB
    kb, origin = fetch_kb(ctx)
    for a in kb:
        if not vis(a.get("updated", "1970-01-01T00:00:00")):
            continue
        s = st("servicenow_kb")
        s["scanned"] += 1
        text = "%s. %s" % (a.get("short_description", ""), a.get("text", ""))
        code = injection_reason(text)
        if code:
            reject("servicenow_kb", "ServiceNow KB", a.get("author", ""), a["updated"], text, code)
            continue
        if a.get("workflow_state", "published") != "published":
            s["skipped"] += 1
            continue
        verdict = "verified" if int(a.get("helpful", 0)) >= 3 else "unverified"
        s[verdict] += 1
        src = {"type": "kb", "ref": a["number"], "where": "ServiceNow KB", "author": a.get("author", ""), "ts": a["updated"],
               "how": "%d helpful votes" % int(a.get("helpful", 0))}
        for act in map_actions(text) or [None]:
            add(a.get("device") or detect_device(text), a.get("text", ""), act, src, verdict, a.get("short_description", ""))

    # 2. closed incidents: the sample history plus tickets our engineers resolved
    incs = rm.load_json(os.path.join(SRC, "servicenow_incidents.json"), [])
    for tk in rm.tickets_load(ctx)["tickets"].values():
        if tk.get("close_notes") and tk.get("resolved_by") and tk["resolved_by"] != rm.AUTOMATION and tk.get("device") not in (None, "upstream"):
            incs.append({"number": tk["number"], "short_description": tk.get("short_description", ""), "device": tk["device"],
                         "symptom": tk.get("symptom"), "close_code": tk.get("close_code", ""), "close_notes": tk["close_notes"],
                         "resolved_at": tk.get("resolved_at") or tk["updated_at"], "resolved_by": tk["resolved_by"],
                         "reopened": tk.get("reopen_count", 0) > 0, "own": True})
    for inc in incs:
        if not inc.get("resolved_at") or not vis(inc["resolved_at"]):
            continue
        kind = "own_tickets" if inc.get("own") else "servicenow_incidents"
        s = st(kind)
        s["scanned"] += 1
        text = inc.get("close_notes", "")
        code = injection_reason(text)
        if code:
            reject(kind, "ServiceNow incident", inc.get("resolved_by", ""), inc["resolved_at"], text, code)
            continue
        if inc.get("reopened"):
            verdict, how = "failed", "reopened after close"
        elif inc.get("close_code", "").startswith("Solved (Permanently)"):
            verdict, how = "verified", "closed: Solved (Permanently)"
        else:
            verdict, how = "unverified", "closed: " + (inc.get("close_code") or "no close code")
        s[verdict] += 1
        dev = inc.get("device") or detect_device(inc.get("short_description", "") + " " + text)
        src = {"type": "ticket" if inc.get("own") else "incident", "ref": inc["number"], "where": "ServiceNow incident",
               "author": inc.get("resolved_by", ""), "ts": inc["resolved_at"], "how": how}
        for act in map_actions(text) or [None]:
            item_text = text
            if dev:
                found.append({"device": dev, "symptom": inc.get("symptom") or rm.symptom_key(dev, inc.get("short_description", "") + " " + text),
                              "action": act, "text": item_text, "src": dict(src, verdict=verdict, text=item_text)})

    # 3 + 4. chat groups and email threads
    threads = [(c.get("platform", "chat"), c.get("channel", ""), c.get("messages", []), c.get("device"))
               for c in rm.load_json(os.path.join(SRC, "chat_groups.json"), [])]
    threads += [("email", "Email: " + e.get("subject", ""), [dict(m, author=m.get("from", "")) for m in e.get("messages", [])], e.get("device"))
                for e in rm.load_json(os.path.join(SRC, "email.json"), [])]
    for kind, where, msgs, dev_hint in threads:
        msgs = [m for m in msgs if vis(m["ts"])]
        if not msgs:
            continue
        s = st(kind)
        s["scanned"] += 1
        clean = []
        for m in msgs:
            code = injection_reason(m.get("text", ""))
            if code:
                reject(kind, where, m.get("author", ""), m["ts"], m.get("text", ""), code)
            else:
                clean.append(m)
        if not clean:
            continue
        asker = clean[0]["author"]
        dev = dev_hint or detect_device(" ".join(m.get("text", "") for m in clean))
        for i, m in enumerate(clean[1:], 1):
            if m["author"] == asker:
                continue
            acts = map_actions(m.get("text", ""))
            if not acts and not re.search(ADVICE, m.get("text", ""), re.I):
                continue
            mapped_by = "keywords"
            if not acts and dev:
                import brain
                ans = brain.ask(ctx, "map_fix_text", {"device": dev, "text": m.get("text", ""),
                                "allowed_actions": [a for a, v in ctx.actions.items() if v.get("device") == dev and not v.get("physical")]})
                if ans and ans["actions"]:
                    acts, mapped_by = ans["actions"], ans.get("by") or "ai"
            follow = next((x for x in clean[i + 1:] if x["author"] == asker), None)
            likes = int((m.get("reactions") or {}).get("👍", 0))
            if follow and re.search(NEG, follow.get("text", ""), re.I):
                verdict, how = "failed", "asker: “%s”" % follow["text"][:40]
            elif follow and re.search(POS, follow.get("text", ""), re.I):
                verdict, how = "verified", "asker: “%s”" % follow["text"][:40]
            elif likes >= 3:
                verdict, how = "verified", "%d 👍" % likes
            else:
                verdict, how = "unverified", "no confirmation"
            confirmed = map_actions(follow.get("text", "")) if (follow and verdict == "verified") else []
            src = {"type": "email" if kind == "email" else "chat", "ref": "%s@%s" % (m["author"], m["ts"]), "where": where,
                   "platform": kind, "author": m["author"], "ts": m["ts"], "how": how, "mapped_by": mapped_by}
            for act in acts or [None]:
                v = verdict
                if verdict == "verified" and confirmed and act not in confirmed:
                    v = "unverified"  # the asker confirmed a different step from the same reply
                s[v] += 1
                add(dev, m.get("text", ""), act, src, v, clean[0].get("text", ""))

    return merge(ctx, found, rejected, stats, origin)


def merge(ctx, found, rejected, stats, origin):
    old = rm.load_json(ctx.library_path, {})
    entries = {e["key"]: e for e in old.get("entries", [])}
    seq = old.get("seq", 0)
    new_ids, changed = [], []
    before = {k: e.get("status") for k, e in entries.items()}
    for f in found:
        key = "%s|%s|%s" % (f["device"], f["symptom"], f["action"] or "advice:" + norm(f["text"]))
        e = entries.get(key)
        if not e:
            seq += 1
            phys = bool(ctx.actions.get(f["action"], {}).get("physical")) if f["action"] else True
            e = {"id": "CL-%03d" % seq, "key": key, "device": f["device"], "symptom": f["symptom"], "action": f["action"],
                 "kind": "engineer" if phys else "auto", "text": f["text"], "sources": [], "first_seen": ctx.ts()}
            entries[key] = e
            new_ids.append(e["id"])
        hit = next((s for s in e["sources"] if s["type"] == f["src"]["type"] and s["ref"] == f["src"]["ref"]), None)
        if hit:
            hit.update(f["src"])
        else:
            e["sources"].append(f["src"])
    for k, e in entries.items():
        e["verified"] = sum(1 for s in e["sources"] if s["verdict"] == "verified")
        e["failed"] = sum(1 for s in e["sources"] if s["verdict"] == "failed")
        e["status"] = "verified" if e["verified"] > e["failed"] else ("contradicted" if e["failed"] else "unverified")
        best = next((s for s in e["sources"] if s["verdict"] == "verified"), None)
        if best:
            e["text"] = best.get("text") or e["text"]
        if before.get(k) and before[k] != e["status"]:
            changed.append({"id": e["id"], "from": before[k], "to": e["status"]})
    seen = {(r["where"], r["author"], r["ts"]) for r in old.get("rejected", [])}
    rej_new = [r for r in rejected if (r["where"], r["author"], r["ts"]) not in seen]
    lib = {"updated": ctx.ts(), "seq": seq, "entries": sorted(entries.values(), key=lambda e: e["id"]),
           "rejected": old.get("rejected", []) + rej_new}
    rm.save_json(ctx.library_path, lib)
    return {"ts": ctx.ts(), "origin": origin, "stats": stats, "new": new_ids, "changed": changed, "rejected_new": rej_new,
            "size": len(entries), "verified": sum(1 for e in entries.values() if e["status"] == "verified")}


def main():
    ap = argparse.ArgumentParser(description="Harvest fixes into the case library")
    ap.add_argument("--data-dir", default=os.path.join(HERE, "data"))
    ap.add_argument("--lang", choices=["zh", "en"], default="en")
    a = ap.parse_args()
    ctx = rm.Ctx(a.data_dir, a.lang)
    r = harvest(ctx)
    zh = a.lang == "zh"
    print("\n  %s (%s)" % ("病例库收集" if zh else "Case-library harvest", r["origin"]))
    print("  " + "─" * 60)
    for name, s in r["stats"].items():
        print("  %-22s %s" % (name, ", ".join("%s %d" % (k, v) for k, v in s.items() if v)))
    print("  %s: %d   %s: %d   %s: %d" % ("条目" if zh else "entries", r["size"], "已验证" if zh else "verified", r["verified"],
                                         "本次新增" if zh else "new", len(r["new"])))
    for x in r["rejected_new"]:
        print("  ⛔ %s · %s · %s: %s" % (x["where"], x["author"], x["reason"], x["text"][:70]))
    print()


if __name__ == "__main__":
    main()
