#!/usr/bin/env python3
"""Remediate: the closed repair loop on top of the Incident Skeleton.

    confirmed fault -> candidate fixes -> permission check -> act -> verify
        -> record (the crew learns)
        -> fixed:      close any open ticket for it
        -> not fixed:  alert that says what was tried, then open / update /
                       reopen a ServiceNow incident for the right support group

Candidate fixes come from the built-in runbooks (runbooks.json), the case
library that harvest.py fills from ServiceNow KB, closed incidents, chat groups
and email, an optional AI advisor, and this site's own history.

Permissions live in policy.json, not in code: risk tier (low: auto, medium:
notify then act, high: approval), a per-device allow-list, an attempt cap, a
cooldown, and physical steps never run automatically. A fix learned from the
library or an AI that has not proven itself here may act alone only at low risk.

Learning is statistics, not model training: every attempt is recorded and
verified; success rates (with the library's verified count as a prior) order
the next attempt; a fix that keeps failing is demoted and skipped.

Safe by default: dry run. Nothing touches a device unless policy.json says
"live" or you pass --live, and only actions with a wired command can run. The
ServiceNow REST calls are written but have not been run against a real instance.

Usage
  python3 remediate.py --demo
  python3 remediate.py --type printer --target 10.0.4.21 --message "PAPER JAM (13.20)" --simulate-fix clear-queue
  python3 remediate.py --report
"""
import argparse, base64, json, os, shlex, subprocess, sys, tempfile, time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import run_incident as ri

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
OPEN_STATES = ("New", "In Progress", "On Hold")
AUTOMATION = "Incident Skeleton (automation)"

S = {
 "zh": {
  "head": "修复闭环", "cands": "候选修法（先软后硬，再按成功率）", "skip_demoted": "跳过：已降级，成功率太低",
  "skip_denied": "跳过：权限不允许", "skip_cool": "跳过：冷却中", "human": "需人工", "approval": "需批准",
  "approved": "已批准", "notify": "先通知再动手", "fixed": "✅ 已恢复", "notfixed": "✗ 没恢复",
  "learned": "已记录结果，成功率会影响下次排序", "alert": "告警：自动修复失败", "dev": "设备", "sym": "症状",
  "tried": "已做", "left": "还没做 / 需人工", "cause": "可能的原因", "ticket": "工单", "group": "派给",
  "ev_created": "新开单", "ev_updated": "已有未关单，追加记录，不重复开单", "ev_reopened": "72 小时内复发，重新打开",
  "ev_resolved": "自动修好，已关单", "none": "（无）", "dry": "（演练：没有真的改动设备）",
  "ai_off": "未配置 AI 顾问（INCIDENT_AI_CMD）；运行本技能的 Kiro 代理会读证据自行推理",
  "report": "修复成绩单", "cols": "设备/症状/修法", "rate": "成功率", "state": "状态",
  "promoted": "已晋升", "demoted": "已降级", "candidate": "候选", "builtin": "内置",
 },
 "en": {
  "head": "Remediation loop", "cands": "Candidate fixes (soft before hard, then by success rate)",
  "skip_demoted": "skipped: demoted, success rate too low", "skip_denied": "skipped: not permitted by policy",
  "skip_cool": "skipped: cooling down", "human": "needs a human", "approval": "needs approval",
  "approved": "approved", "notify": "notify, then act", "fixed": "✅ recovered", "notfixed": "✗ not recovered",
  "learned": "outcome recorded; success rate shapes the next ranking", "alert": "ALERT: automatic repair failed",
  "dev": "Device", "sym": "Symptom", "tried": "What was done", "left": "Not done / needs a human",
  "cause": "Likely cause", "ticket": "Ticket", "group": "Assigned to", "ev_created": "new ticket",
  "ev_updated": "an open ticket exists; note added, no new ticket", "ev_reopened": "came back within 72 h; reopened",
  "ev_resolved": "fixed by automation; ticket resolved", "none": "(none)", "dry": "(dry run: no device was changed)",
  "ai_off": "no AI advisor configured (INCIDENT_AI_CMD); the Kiro agent running this skill reads the evidence and reasons itself",
  "report": "Repair scorecard", "cols": "device/symptom/fix", "rate": "success", "state": "state",
  "promoted": "promoted", "demoted": "demoted", "candidate": "candidate", "builtin": "builtin",
 },
}


# ---------------------------------------------------------------- small helpers

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return rows


def to_epoch(s):
    return datetime.fromisoformat(s).timestamp()


def txt(x, lang):
    if isinstance(x, dict):
        return x.get(lang) or x.get("en") or next(iter(x.values()), "")
    return "" if x is None else str(x)


class Ctx:
    def __init__(self, data_dir, lang="en", live=None, clock=None, ticket_prefix="DRYRUN-INC", ticket_start=0):
        self.dir = data_dir
        os.makedirs(self.dir, exist_ok=True)
        self.lang = lang if lang in S else "en"
        self.t = S[self.lang]
        self.actions = load_json(os.path.join(HERE, "actions.json"), {})
        self.runbooks = load_json(os.path.join(HERE, "runbooks.json"), {})
        self.policy = load_json(os.path.join(HERE, "policy.json"), {})
        self.live = bool(live) if live is not None else self.policy.get("mode") == "live"
        self.clock = clock or time.time
        self.ticket_prefix, self.ticket_start = ticket_prefix, ticket_start
        self.attempts_path = os.path.join(self.dir, "attempts.jsonl")
        self.cases_path = os.path.join(self.dir, "case_history.jsonl")
        self.audit_path = os.path.join(self.dir, "audit.jsonl")
        self.alerts_path = os.path.join(self.dir, "alerts.log")
        self.tickets_path = os.path.join(self.dir, "tickets.json")
        self.library_path = os.path.join(self.dir, "case_library.json")

    def ts(self):
        return datetime.fromtimestamp(self.clock()).isoformat(timespec="seconds")

    def desc(self, aid):
        return self.actions.get(aid, {}).get(self.lang, aid)


# ---------------------------------------------------------------- knowledge

SYMPTOMS = {
    "printer": [("jam", ("jam", "13.", "卡纸")), ("offline", ("offline", "unreachable", "离线", "不通"))],
    "signage": [("down", ("black", "offline", "黑屏", "离线", "down", "not updating", "不更新"))],
    "av": [("hung", ("hung", "join", "frozen", "freeze", "卡死", "进不了", "无法", "can't"))],
    "wifiap": [("offline", ("offline", "drop", "down", "掉线", "掉了", "离线"))],
}


def symptom_key(device, message):
    m = (message or "").lower()
    for key, words in SYMPTOMS.get(device, []):
        if any(w in m for w in words):
            return key
    return "generic"


def ensure_library(ctx):
    if not os.path.exists(ctx.library_path):
        import harvest
        harvest.harvest(ctx)


def library_for(ctx, device, skey):
    lib = load_json(ctx.library_path, {}).get("entries", [])
    return [e for e in lib if e.get("device") == device and e.get("symptom") in (skey, "generic")]


def ai_actions(ctx, device, packet):
    cmd = os.environ.get("INCIDENT_AI_CMD")
    if not cmd:
        return [], False
    try:
        p = subprocess.run(shlex.split(cmd), input=json.dumps(packet), capture_output=True, text=True, timeout=60)
        data = json.loads(p.stdout or "{}")
    except Exception:
        return [], True
    # an AI may only pick from the known catalogue; the policy still decides
    return [(s.get("action_id"), "ai") for s in data.get("suggestions", [])
            if ctx.actions.get(s.get("action_id"), {}).get("device") == device], True


# ---------------------------------------------------------------- learning

def stats(ctx):
    st = {}
    for r in read_jsonl(ctx.attempts_path):
        if r.get("outcome") != "ran" or r.get("verified") is None:
            continue
        a = st.setdefault((r["device"], r["symptom"], r["action"]), {"attempts": 0, "successes": 0})
        a["attempts"] += 1
        a["successes"] += 1 if r["verified"] else 0
    return st


def score(st, key, v=0, c=0):
    """Laplace estimate; verified library reports count as prior successes, failed ones as prior failures."""
    a = st.get(key, {"attempts": 0, "successes": 0})
    return (a["successes"] + 1 + v) / (a["attempts"] + 2 + v + c)


def state_of(ctx, st, key, sources):
    ev = ctx.policy.get("evolution", {})
    a = st.get(key, {"attempts": 0, "successes": 0})
    rate = a["successes"] / a["attempts"] if a["attempts"] else None
    if a["attempts"] >= ev.get("demote_min_attempts", 3) and rate is not None and rate <= ev.get("demote_max_rate", 0.2):
        return "demoted"
    if "builtin" in sources:
        return "builtin"
    if a["successes"] >= ev.get("promote_min_successes", 2) and rate is not None and rate >= ev.get("promote_min_rate", 0.67):
        return "promoted"
    return "candidate"


# ---------------------------------------------------------------- acting

def probe(ns):
    t = ns.target
    if ri.is_url(t):
        ok, out = ri.curl(t)
        return ok and out.startswith("HTTP") and out.split()[1][:1] in ("2", "3")
    return ri.ping(t)[0]


def execute(ctx, action, ns):
    cmd = action.get("command")
    if not ctx.live:
        return True, "[dry-run] " + (" ".join(cmd) if cmd else "via integration")
    if not cmd:
        return False, "no executor integration is configured for this action"
    ok, out = ri.run_cmd([c.replace("{target}", ri.host_of(ns.target)) for c in cmd], timeout=30)
    return ok, out


def decide(ctx, device, aid, state, tried_recently):
    a = ctx.actions[aid]
    if a.get("physical"):
        return "needs_human", None
    if state == "demoted":
        return "demoted", None
    if aid not in ctx.policy.get("allow", {}).get(device, []):
        return "denied", None
    if aid in tried_recently:
        return "cooldown", None
    tier = ctx.policy.get("autonomy", {}).get(a["risk"], "approval")
    if state == "candidate" and a["risk"] != "low":
        tier = "approval"  # learned but unproven here: only low risk may act alone
    return "run", tier


def cooldown_set(ctx, device, target):
    lim = ctx.policy.get("cooldown_minutes", 30) * 60
    now = ctx.clock()
    return {r["action"] for r in read_jsonl(ctx.attempts_path)
            if r.get("device") == device and r.get("target") == target and r.get("outcome") == "ran"
            and now - to_epoch(r["ts"]) < lim}


def remediate(ns, ctx, scenario=None, approvals=None, use_cooldown=True, quiet=False, evidence=None):
    """Walk one confirmed fault through the loop. `scenario` (set of action ids) replaces real verification
    in simulations; `evidence` replaces the live INVESTIGATE checks; `approvals` maps action id -> approver."""
    t = ctx.t
    out = (lambda *a: None) if quiet else print
    approvals = dict(approvals) if isinstance(approvals, dict) else {a: "approved" for a in (approvals or ())}
    device, target = ns.type, ns.target
    ci = getattr(ns, "ci", None) or target
    skey = symptom_key(device, ns.message)
    if evidence is None:
        evidence = [{"check": c, "result": d, "status": s} for c, d, s in ri.CREW[device]["inv"](ns)]
    ensure_library(ctx)
    lib = library_for(ctx, device, skey)

    prior = {}
    for e in lib:
        if e.get("action"):
            p = prior.setdefault(e["action"], {"v": 0, "c": 0, "ids": []})
            p["v"] += e.get("verified", 0)
            p["c"] += e.get("failed", 0)
            p["ids"].append(e["id"])

    cands = {}

    def add(aid, src):
        if aid in ctx.actions and ctx.actions[aid]["device"] == device and src not in cands.setdefault(aid, []):
            cands[aid].append(src)

    book = ctx.runbooks.get(device, {})
    order = list(book.get(skey, book.get("generic", [])))
    for aid in order:
        add(aid, "builtin")
    for e in lib:
        if e.get("action") and e.get("status") == "verified":
            add(e["action"], "lib")
    packet = {"device": device, "target": target, "symptom": skey, "message": ns.message, "evidence": evidence}
    ai, ai_on = ai_actions(ctx, device, packet)
    for aid, src in ai:
        add(aid, src)
    builtin_first = next((a for a in order if not ctx.actions.get(a, {}).get("physical")), None)

    st = stats(ctx)
    recent = cooldown_set(ctx, device, target) if use_cooldown else set()
    rows = []
    for aid, srcs in cands.items():
        key = (device, skey, aid)
        p = prior.get(aid, {"v": 0, "c": 0, "ids": []})
        sc = score(st, key, min(p["v"], 3), min(p["c"], 3))
        phys = bool(ctx.actions[aid].get("physical"))
        idx = order.index(aid) if aid in order else 99
        rows.append({"id": aid, "sources": srcs, "state": state_of(ctx, st, key, srcs), "score": round(sc, 2),
                     "hist": dict(st.get(key, {"attempts": 0, "successes": 0})), "lib": p["ids"],
                     "rank": (phys, RISK_ORDER[ctx.actions[aid]["risk"]], -sc, idx)})
    rows.sort(key=lambda r: r["rank"])

    out("")
    out("  %s · %s %s / %s  %s" % (t["head"], device, ci, skey, "" if ctx.live else t["dry"]))
    out("  " + "─" * 60)
    for e in evidence:
        out("  %s %s: %s" % ({"ok": "✓", "warn": "·", "err": "✗"}.get(e["status"], "·"), txt(e["check"], ctx.lang), txt(e["result"], ctx.lang)))
    if not ai_on:
        out("  · " + t["ai_off"])
    out("\n  " + t["cands"])

    trace, attempts, left, cooled = [], [], [], []
    resolved, ran = False, 0
    max_n = ctx.policy.get("max_attempts_per_incident", 4)
    for r in rows:
        if resolved:
            break
        aid = r["id"]
        a = ctx.actions[aid]
        d, tier = decide(ctx, device, aid, r["state"], recent)
        tr = {k: r[k] for k in ("sources", "state", "score", "hist", "lib")}
        tr.update({"action": aid, "risk": a["risk"], "decision": d, "tier": tier})
        label = "%s  [%s · %s]" % (ctx.desc(aid), a["risk"], ",".join(r["sources"]))
        if d != "run":
            msg = {"needs_human": t["human"], "demoted": t["skip_demoted"], "denied": t["skip_denied"], "cooldown": t["skip_cool"]}[d]
            out("   · %s  → %s" % (label, msg))
            if d == "cooldown":
                cooled.append(aid)
            else:
                left.append({"action": aid, "why": {"needs_human": "human"}.get(d, d)})
            trace.append(tr)
            continue
        if tier == "approval" and aid not in approvals:
            tr["decision"] = "approval"
            out("   · %s  → %s" % (label, t["approval"]))
            left.append({"action": aid, "why": "approval"})
            append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "device": device, "target": target, "action": aid, "decision": "needs_approval"})
            trace.append(tr)
            continue
        if ran >= max_n:
            tr["decision"] = "cap"
            left.append({"action": aid, "why": "attempt_cap"})
            trace.append(tr)
            continue
        if tier == "notify_then_act":
            out("   → %s: %s" % (t["notify"], ctx.desc(aid)))
            time.sleep(ctx.policy.get("notify_wait_seconds", 0))
        ok, output = execute(ctx, a, ns)
        ran += 1
        verified = (aid in scenario) if scenario is not None else (probe(ns) if ok else False)
        if tier == "approval":
            tr["approved_by"] = approvals.get(aid)
        append_jsonl(ctx.attempts_path, {"ts": ctx.ts(), "device": device, "target": target, "symptom": skey,
                     "action": aid, "risk": a["risk"], "source": ",".join(r["sources"]), "tier": tier,
                     "outcome": "ran" if ok else "failed_to_run", "verified": verified if ok else None,
                     "live": ctx.live, "output": output[:200]})
        append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "device": device, "target": target, "action": aid,
                     "decision": "run", "tier": tier, "approved_by": tr.get("approved_by"), "live": ctx.live})
        tr.update({"ran": ok, "recovered": verified if ok else None, "output": output[:120]})
        trace.append(tr)
        attempts.append({"action": aid, "tier": tier, "ran": ok, "recovered": verified if ok else None, "output": output})
        out("   %s %s  [%s]  %s" % ("→" if ok else "✗", ctx.desc(aid), tier,
                                  (t["fixed"] if verified else t["notfixed"]) if ok else output))
        resolved = bool(ok and verified)
    out("  " + t["learned"])

    append_jsonl(ctx.cases_path, {"device_type": device, "ci": ci, "symptom": ns.message, "success": resolved,
                 "attempts": [x["action"] for x in attempts], "_ts": ctx.ts()})
    key = "%s|%s|%s" % (device, ci, skey)
    result = {"resolved": resolved, "attempts": attempts, "left": left, "cooldown": cooled, "evidence": evidence,
              "symptom": skey, "trace": trace, "key": key, "ci": ci, "device": device, "message": ns.message,
              "builtin_first": builtin_first, "ticket": None}
    if resolved:
        last = attempts[-1]
        num = ticket_resolve(ctx, key, AUTOMATION, "auto_fixed",
                             {"action": last["action"], "tier": last["tier"], "approved_by": trace[-1].get("approved_by")},
                             close_notes="Fixed by automation: " + ctx.actions[last["action"]]["en"])
        if num:
            result["ticket"] = {"number": num, "event": "resolved"}
            out("  %s %s: %s" % (t["ticket"], num, t["ev_resolved"]))
    else:
        result["ticket"] = escalate(ns, ctx, result, quiet)
    return result


# ---------------------------------------------------------------- ServiceNow tickets

def tickets_load(ctx):
    d = load_json(ctx.tickets_path, None)
    if not isinstance(d, dict) or "tickets" not in d:
        d = {"n": ctx.ticket_start, "tickets": {}, "by_key": {}}
    return d


def _note(ctx, tk, author, ntype, kind, data):
    tk["work_notes"].append({"ts": ctx.ts(), "author": author, "type": ntype, "kind": kind, "data": data, "state": tk["state"]})
    tk["updated_at"] = ctx.ts()


def ticket_upsert(ctx, key, fields, kind, data, knowledge=None, awaiting=None, extra=None):
    """Create, add a note to, or reopen the ticket for this key. Returns (number, event)."""
    d = tickets_load(ctx)
    num = d["by_key"].get(key)
    tk = d["tickets"].get(num) if num else None
    hold = bool(awaiting)
    reopen_s = ctx.policy.get("reopen_hours", 72) * 3600
    if tk and tk["state"] in OPEN_STATES:
        event = "updated"
    elif tk and tk["state"] == "Resolved" and tk.get("resolved_at") and ctx.clock() - to_epoch(tk["resolved_at"]) <= reopen_s:
        event = "reopened"
        tk["reopen_count"] = tk.get("reopen_count", 0) + 1
        tk["resolved_at"], tk["close_code"] = None, ""
    else:
        event = "created"
        d["n"] += 1
        num = "%s%07d" % (ctx.ticket_prefix, d["n"])
        tk = {"number": num, "key": key, "caller": AUTOMATION, "assigned_to": "", "opened_at": ctx.ts(),
              "resolved_at": None, "close_code": "", "close_notes": "", "reopen_count": 0, "work_notes": []}
        tk.update(fields)
        d["tickets"][num] = tk
        d["by_key"][key] = num
    tk.update(extra or {})
    tk["state"] = "On Hold" if hold else ("New" if event == "created" else "In Progress")
    tk["hold_reason"] = "Awaiting approval" if hold else ""
    tk["automation"] = data
    tk["knowledge"] = knowledge or tk.get("knowledge", [])
    tk["awaiting_approval"] = awaiting or []
    _note(ctx, tk, AUTOMATION, event, kind, data)
    save_json(ctx.tickets_path, d)
    sn_sync(ctx, tk, event)
    return num, event


def ticket_update(ctx, key, author, kind, data, **fields):
    d = tickets_load(ctx)
    num = d["by_key"].get(key)
    tk = d["tickets"].get(num) if num else None
    if not tk:
        return None
    tk.update(fields)
    if tk["state"] == "New":
        tk["state"] = "In Progress"
    _note(ctx, tk, author, "comment", kind, data)
    save_json(ctx.tickets_path, d)
    sn_sync(ctx, tk, "comment")
    return num


def ticket_resolve(ctx, key, author, kind, data, close_code="Solved (Permanently)", close_notes=""):
    d = tickets_load(ctx)
    num = d["by_key"].get(key)
    tk = d["tickets"].get(num) if num else None
    if not tk or tk["state"] not in OPEN_STATES:
        return None
    tk.update({"state": "Resolved", "hold_reason": "", "resolved_at": ctx.ts(), "close_code": close_code,
               "close_notes": close_notes, "resolved_by": author, "awaiting_approval": []})
    _note(ctx, tk, author, "resolved", kind, data)
    save_json(ctx.tickets_path, d)
    sn_sync(ctx, tk, "resolved")
    return num


def sn_sync(ctx, tk, event):
    """Mirror to a real ServiceNow (Table API). Written, NOT exercised against a real instance."""
    inst, user, pw = os.environ.get("SN_INSTANCE"), os.environ.get("SN_USER"), os.environ.get("SN_PASSWORD")
    if not (ctx.live and not ctx.policy.get("escalation", {}).get("dry_run", True) and inst and user and pw):
        return
    auth = "Basic " + base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()
    hdr = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": auth}
    last = tk["work_notes"][-1]
    note = "[%s] %s: %s" % (last["kind"], last["author"], json.dumps(last["data"], ensure_ascii=False)[:3000])
    try:
        if event == "created":
            body = {k: tk.get(k) for k in ("short_description", "description", "assignment_group", "cmdb_ci", "urgency", "impact", "category")}
            req = urllib.request.Request("https://%s/api/now/table/incident" % inst, data=json.dumps(body).encode(), method="POST", headers=hdr)
            with urllib.request.urlopen(req, timeout=20) as r:
                tk["sys_id"] = json.load(r)["result"]["sys_id"]
        if tk.get("sys_id"):
            body = {"work_notes": note}
            if event == "resolved":
                body.update({"state": "6", "close_code": tk.get("close_code"), "close_notes": tk.get("close_notes")})
            req = urllib.request.Request("https://%s/api/now/table/incident/%s" % (inst, tk["sys_id"]),
                                         data=json.dumps(body).encode(), method="PATCH", headers=hdr)
            urllib.request.urlopen(req, timeout=20).close()
    except Exception as e:
        tk["sync_error"] = str(e)[:200]


def explain(ctx, evidence):
    bad = [e for e in evidence if e.get("status") == "err"]
    return "; ".join("%s: %s" % (txt(e["check"], ctx.lang), txt(e["result"], ctx.lang)) for e in bad) or ctx.t["none"]


def escalate(ns, ctx, result, quiet=False):
    t = ctx.t
    out = (lambda *a: None) if quiet else print
    group = ctx.policy.get("escalation", {}).get("groups", {}).get(ns.type, "Service Desk")
    left_actions = [x["action"] for x in result["left"]]
    knowledge = []
    for e in library_for(ctx, ns.type, result["symptom"]):
        if e.get("kind") == "engineer" or e.get("action") in left_actions:
            knowledge.append({"id": e["id"], "action": e.get("action"), "kind": e.get("kind"), "status": e.get("status"),
                              "text": e.get("text", ""), "verified": e.get("verified", 0), "failed": e.get("failed", 0),
                              "sources": [{k: s.get(k) for k in ("type", "ref", "where", "author", "verdict", "how")} for s in e.get("sources", [])][:4]})
    awaiting = [x["action"] for x in result["left"] if x["why"] == "approval"]
    data = {"tried": [{k: a[k] for k in ("action", "tier", "ran", "recovered")} for a in result["attempts"]],
            "left": result["left"], "cooldown": result["cooldown"], "evidence": result["evidence"],
            "awaiting": awaiting, "knowledge": [k["id"] for k in knowledge]}
    desc = "Symptom: %s\nLikely cause: %s\nTried: %s\nNot done: %s" % (
        ns.message, explain(ctx, result["evidence"]),
        ", ".join("%s (%s)" % (ctx.actions[a["action"]]["en"], "recovered" if a["recovered"] else "not recovered") for a in result["attempts"]) or "-",
        ", ".join("%s (%s)" % (ctx.actions[x["action"]]["en"], x["why"]) for x in result["left"]) or "-")
    fields = {"short_description": "[Auto] %s: automatic repair failed - %s" % (result["ci"], ns.message),
              "description": desc, "cmdb_ci": result["ci"], "assignment_group": group, "device": ns.type,
              "symptom": result["symptom"], "message": ns.message, "message_zh": getattr(ns, "message_zh", None),
              "category": "Network" if ns.type == "wifiap" else "Hardware", "impact": "2", "urgency": "2",
              "priority": "3 - Moderate", "kind": "device"}
    num, event = ticket_upsert(ctx, result["key"], fields, "auto_failed", data, knowledge, awaiting)
    lines = ["", "  🔴 " + t["alert"], "  " + "─" * 60,
             "  %s: %s (%s)" % (t["dev"], ns.type, result["ci"]), "  %s: %s" % (t["sym"], ns.message),
             "  %s: %s" % (t["cause"], explain(ctx, result["evidence"])), "  %s:" % t["tried"]]
    lines += ["    - %s → %s" % (ctx.desc(a["action"]), t["fixed"] if a["recovered"] else t["notfixed"]) for a in result["attempts"]] or ["    - " + t["none"]]
    lines += ["  %s:" % t["left"]] + (["    - %s (%s)" % (ctx.desc(x["action"]), x["why"]) for x in result["left"]] or ["    - " + t["none"]])
    lines += ["  %s: %s  ·  %s: %s  ·  %s" % (t["ticket"], num, t["group"], group, t["ev_" + event])]
    alert = "\n".join(lines)
    out(alert)
    with open(ctx.alerts_path, "a", encoding="utf-8") as f:
        f.write("[%s]%s\n" % (ctx.ts(), alert))
    return {"number": num, "event": event, "group": group}


# ---------------------------------------------------------------- report / demo / cli

def scoreboard(ctx):
    st = stats(ctx)
    rows = []
    for (dev, sym, aid), a in sorted(st.items()):
        book = ctx.runbooks.get(dev, {})
        srcs = ["builtin"] if aid in book.get(sym, []) + book.get("generic", []) else ["lib"]
        rows.append({"device": dev, "symptom": sym, "action": aid, "successes": a["successes"],
                     "attempts": a["attempts"], "state": state_of(ctx, st, (dev, sym, aid), srcs)})
    return rows


def report(ctx):
    t = ctx.t
    rows = scoreboard(ctx)
    print("\n  %s\n  %s" % (t["report"], "─" * 60))
    if not rows:
        print("  " + t["none"])
        return
    print("  %-38s %-9s %-10s" % (t["cols"], t["rate"], t["state"]))
    for r in rows:
        print("  %-38s %-9s %-10s" % ("%s/%s/%s" % (r["device"], r["symptom"], r["action"]),
                                     "%d/%d" % (r["successes"], r["attempts"]), t[r["state"]]))
    print()


def demo(lang):
    d = tempfile.mkdtemp(prefix="remediation-demo-")
    ctx = Ctx(d, lang, live=False)
    print("\n  demo data dir: %s  (simulated: no device is touched)" % d)
    mk = lambda ty, tg, msg: argparse.Namespace(type=ty, target=tg, source="demo", message=msg)
    ev = lambda: [{"check": "ping", "result": "simulated", "status": "warn"}]
    for i in (1, 2, 3):
        print("\n  ═══ run %d: printer jam ═══" % i)
        remediate(mk("printer", "PRN-%d" % i, "PAPER JAM (13.20)"), ctx, scenario={"clear-queue"}, evidence=ev())
    print("\n  ═══ run 4: wireless AP, nothing we may do fixes it ═══")
    remediate(mk("wifiap", "AP-1", "AP offline, clients dropping"), ctx, scenario=set(), evidence=ev())
    report(ctx)
    print("  files: %s" % ", ".join(sorted(os.listdir(d))))
    print("  for the full scripted morning run: python3 simulate.py")


def main():
    ap = argparse.ArgumentParser(description="Remediation loop for Incident Skeleton")
    ap.add_argument("--type", choices=list(ri.CREW))
    ap.add_argument("--target", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--message", default="")
    ap.add_argument("--lang", choices=["zh", "en"], default="en")
    ap.add_argument("--data-dir", default=os.path.join(HERE, "data"))
    ap.add_argument("--live", action="store_true", help="really act (default is dry-run)")
    ap.add_argument("--simulate-fix", help="comma list of action ids that would fix it; empty = nothing fixes it")
    ap.add_argument("--approve", default="", help="comma list of action ids a human approved")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        demo(a.lang)
        return
    ctx = Ctx(a.data_dir, a.lang, live=a.live or None)
    if a.report:
        report(ctx)
        return
    if not a.type or not a.message:
        ap.error("--type and --message are required (or use --demo / --report)")
    scen = None if a.simulate_fix is None else set(x for x in a.simulate_fix.split(",") if x)
    res = remediate(a, ctx, scenario=scen, approvals=[x for x in a.approve.split(",") if x])
    sys.exit(0 if res["resolved"] else 2)


if __name__ == "__main__":
    main()
