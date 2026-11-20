#!/usr/bin/env python3
"""Remediate: the closed loop on top of the Incident Skeleton.

    confirmed fault -> find candidate fixes -> permission check -> act -> verify
        -> record the outcome (the crew learns) -> if still broken: say what
        was tried, and open a ServiceNow incident for the right support group.

Where the fixes come from
  builtin runbooks (runbooks.json), ServiceNow KB articles, an optional AI
  advisor, and the history of what actually worked here (attempts.jsonl).

What it may do (the permission model) lives in policy.json, not in code:
  risk tier  low -> auto | medium -> notify then act | high -> needs approval
  per-device allow-list, attempt cap, cooldown, physical steps never automatic.

How it "evolves" (honest version: statistics, not model training)
  every attempt is recorded with whether verification passed. Success rates
  reorder the next attempt; a fix that keeps failing is demoted and skipped; a
  fix learned from KB/AI is only a candidate (low risk only) until it has
  proven itself, then it is promoted.

Safe by default: mode is dry-run. Nothing touches a device unless policy.json
says "live" or you pass --live, and only actions that have a command wired up
can run. Most actions need an integration (controller API, CMS, MDM); until one
is wired in, live mode reports "no executor" and the step goes to a human.

Usage
  python3 remediate.py --demo                      # scripted, simulated, 5 runs
  python3 remediate.py --type printer --target 10.0.4.21 \
        --message "PAPER JAM (13.20)" --simulate-fix clear-queue
  python3 remediate.py --report                    # what the crew has learned
"""
import argparse, json, os, re, shlex, subprocess, sys, tempfile, time, base64
import urllib.request, urllib.parse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import run_incident as ri  # reuses ping/curl and the per-device INVESTIGATE checks

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

S = {
 "zh": {
  "head": "修复闭环", "evidence": "排查证据", "cands": "候选修法（按 先软后硬、成功率 排序）",
  "skip_demoted": "跳过（已降级：成功率太低）", "skip_denied": "跳过（权限不允许）",
  "skip_cool": "跳过（冷却中）", "human": "需人工", "approval": "需批准", "ran": "已执行",
  "notify": "先通知再动手", "auto": "自动", "fixed": "✅ 已恢复", "notfixed": "✗ 没恢复",
  "learned": "已记录结果，成功率会影响下次排序", "esc": "未能自动修复 → 升级",
  "alert": "告警：自动修复失败", "dev": "设备", "sym": "症状", "tried": "已做",
  "left": "还没做 / 需人工", "cause": "可能的原因", "ticket": "工单", "group": "派给",
  "dup": "已有未关闭的同类工单，追加记录，不重复开单", "none": "（无）",
  "ai_off": "未配置 AI 顾问（INCIDENT_AI_CMD）；运行本技能的 Kiro 代理会读取证据包自行推理",
  "report": "修复成绩单", "cols": "设备/症状/修法", "rate": "成功率", "state": "状态",
  "promoted": "已晋升", "demoted": "已降级", "candidate": "候选", "builtin": "内置",
  "dry": "（演练：没有真的改动设备）", "how": "怎么做的", "src": "来源",
 },
 "en": {
  "head": "Remediation loop", "evidence": "Evidence", "cands": "Candidate fixes (soft before hard, then by success rate)",
  "skip_demoted": "skipped (demoted: success rate too low)", "skip_denied": "skipped (not permitted by policy)",
  "skip_cool": "skipped (cooling down)", "human": "needs a human", "approval": "needs approval", "ran": "ran",
  "notify": "notify, then act", "auto": "auto", "fixed": "✅ recovered", "notfixed": "✗ not recovered",
  "learned": "outcome recorded; success rate will shape the next ranking", "esc": "auto-repair failed → escalating",
  "alert": "ALERT: automatic repair failed", "dev": "Device", "sym": "Symptom", "tried": "What was done",
  "left": "Not done / needs a human", "cause": "Likely cause", "ticket": "Ticket", "group": "Assigned to",
  "dup": "an open ticket for this already exists; appended a note instead of opening a new one", "none": "(none)",
  "ai_off": "no AI advisor configured (INCIDENT_AI_CMD); the Kiro agent running this skill reads the evidence packet and reasons itself",
  "report": "Repair scorecard", "cols": "device/symptom/fix", "rate": "success", "state": "state",
  "promoted": "promoted", "demoted": "demoted", "candidate": "candidate", "builtin": "builtin",
  "dry": "(dry run: no device was changed)", "how": "How", "src": "Source",
 },
}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


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


def now():
    return datetime.now().isoformat(timespec="seconds")


class Ctx:
    def __init__(self, data_dir, lang, live=None):
        self.dir = data_dir
        os.makedirs(self.dir, exist_ok=True)
        self.lang = lang if lang in S else "en"
        self.t = S[self.lang]
        self.actions = load_json(os.path.join(HERE, "actions.json"), {})
        self.runbooks = load_json(os.path.join(HERE, "runbooks.json"), {})
        self.policy = load_json(os.path.join(HERE, "policy.json"), {})
        self.live = bool(live) if live is not None else self.policy.get("mode") == "live"
        self.attempts_path = os.path.join(self.dir, "attempts.jsonl")
        self.cases_path = os.path.join(self.dir, "case_history.jsonl")
        self.audit_path = os.path.join(self.dir, "audit.jsonl")
        self.alerts_path = os.path.join(self.dir, "alerts.log")
        self.tickets_path = os.path.join(self.dir, "tickets.json")

    def desc(self, aid):
        return self.actions.get(aid, {}).get(self.lang, aid)


# ---------------------------------------------------------------- knowledge

def symptom_key(device, message):
    m = (message or "").lower()
    table = {
        "printer": [("jam", ("jam", "13.", "卡纸")), ("offline", ("offline", "unreachable", "离线", "不通"))],
        "signage": [("down", ("black", "offline", "黑屏", "离线", "down"))],
        "av": [("hung", ("hung", "join", "卡死", "无法", "can't"))],
        "wifiap": [("offline", ("offline", "drop", "掉线", "离线"))],
    }
    for key, words in table.get(device, []):
        if any(w in m for w in words):
            return key
    return "generic"


KB_KEYWORDS = [  # free text -> a known action id. An AI maps better; this is the no-AI floor.
    ("stuck print jobs", "clear-queue"), ("clear the queue", "clear-queue"), ("清空打印", "clear-queue"),
    ("print spooler", "restart-spooler"), ("restart the spooler", "restart-spooler"), ("重启打印后台", "restart-spooler"),
    ("re-add the print", "readd-queue"), ("power-cycle the printer", "power-cycle-printer"),
    ("re-push", "repush-content"), ("reboot the player", "reboot-player"), ("重启播放器", "reboot-player"),
    ("restart the room app", "restart-room-app"), ("重启房间应用", "restart-room-app"),
    ("reboot the codec", "reboot-codec"), ("reboot the controller", "reboot-controller"),
    ("reboot the ap", "controller-reboot-ap"), ("through the controller", "controller-reboot-ap"),
    ("poe port", "poe-cycle"), ("channel", "rf-tune"),
]


def fetch_kb(ctx, text):
    """ServiceNow KB. Live REST when SN_INSTANCE/SN_USER/SN_PASSWORD are set, else the sample file.
    The live path is written to the Table API but has NOT been run against a real instance."""
    inst, user, pw = os.environ.get("SN_INSTANCE"), os.environ.get("SN_USER"), os.environ.get("SN_PASSWORD")
    words = [w for w in re.findall(r"[A-Za-z0-9.]{3,}", text or "")][:3]
    if inst and user and pw and ctx.live and words:
        q = "workflow_state=published^short_descriptionLIKE" + words[0]
        url = "https://%s/api/now/table/kb_knowledge?sysparm_limit=5&sysparm_fields=number,short_description,text&sysparm_query=%s" % (
            inst, urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"Accept": "application/json",
            "Authorization": "Basic " + base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r).get("result", []), "servicenow"
        except Exception:
            pass
    return load_json(os.path.join(HERE, "kb_servicenow_sample.json"), []), "sample"


def kb_actions(ctx, device, message):
    arts, _ = fetch_kb(ctx, message)
    low = (message or "").lower()
    codes = re.findall(r"\d{2}\.\d{1,2}", low)
    out = []
    for a in arts:
        blob = (a.get("short_description", "") + " " + a.get("text", "")).lower()
        if not (any(c in blob for c in codes) or any(w in blob for w in re.findall(r"[a-z]{4,}", low))):
            continue
        for kw, aid in KB_KEYWORDS:
            if kw in blob and ctx.actions.get(aid, {}).get("device") == device:
                out.append((aid, "kb:" + a.get("number", "?")))
    return out


def ai_actions(ctx, device, packet):
    cmd = os.environ.get("INCIDENT_AI_CMD")
    if not cmd:
        return [], False
    try:
        p = subprocess.run(shlex.split(cmd), input=json.dumps(packet), capture_output=True, text=True, timeout=60)
        data = json.loads(p.stdout or "{}")
    except Exception:
        return [], True
    out = []
    for s in data.get("suggestions", []):
        aid = s.get("action_id")
        if ctx.actions.get(aid, {}).get("device") == device:  # an AI can only pick from the known catalogue
            out.append((aid, "ai"))
    return out, True


# ---------------------------------------------------------------- learning

def stats(ctx):
    st = {}
    for r in read_jsonl(ctx.attempts_path):
        if r.get("outcome") != "ran" or r.get("verified") is None:
            continue
        k = (r["device"], r["symptom"], r["action"])
        a = st.setdefault(k, {"attempts": 0, "successes": 0})
        a["attempts"] += 1
        a["successes"] += 1 if r["verified"] else 0
    return st


def score(st, key):
    a = st.get(key, {"attempts": 0, "successes": 0})
    return (a["successes"] + 1) / (a["attempts"] + 2)


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
        ok, txt = ri.curl(t)
        return ok and txt.startswith("HTTP") and txt.split()[1][:1] in ("2", "3")
    return ri.ping(t)[0]


def execute(ctx, action, ns):
    cmd = action.get("command")
    if not ctx.live:
        return True, "[dry-run] " + (" ".join(cmd) if cmd else "via integration")
    if not cmd:
        return False, "no executor integration is configured for this action"
    host = ri.host_of(ns.target)
    ok, out = ri.run_cmd([c.replace("{target}", host) for c in cmd], timeout=30)
    return ok, out


def decide(ctx, device, aid, state, sources, tried_recently):
    a = ctx.actions[aid]
    pol = ctx.policy
    if a.get("physical"):
        return "needs_human", None
    if state == "demoted":
        return "demoted", None
    if aid not in pol.get("allow", {}).get(device, []):
        return "denied", None
    if aid in tried_recently:
        return "cooldown", None
    tier = pol.get("autonomy", {}).get(a["risk"], "approval")
    if state == "candidate" and a["risk"] != "low":
        tier = "approval"  # learned from KB/AI but unproven: only low-risk may act alone
    return "run", tier


def cooldown_set(ctx, device, target):
    lim = ctx.policy.get("cooldown_minutes", 30) * 60
    out = set()
    for r in read_jsonl(ctx.attempts_path):
        if r.get("device") == device and r.get("target") == target and r.get("outcome") == "ran":
            try:
                if time.time() - time.mktime(time.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S")) < lim:
                    out.add(r["action"])
            except (KeyError, ValueError):
                pass
    return out


def remediate(ns, ctx, scenario=None, approvals=(), use_cooldown=True, quiet=False):
    t = ctx.t
    out = (lambda *a: None) if quiet else print
    device, target = ns.type, ns.target
    skey = symptom_key(device, ns.message)
    evidence = [{"check": c, "result": d, "status": s} for c, d, s in ri.CREW[device]["inv"](ns)]
    packet = {"device": device, "target": target, "symptom": skey, "message": ns.message, "evidence": evidence}

    cands = {}
    def add(aid, src):
        if aid in ctx.actions and ctx.actions[aid]["device"] == device:
            cands.setdefault(aid, []).append(src)
    book = ctx.runbooks.get(device, {})
    order = list(book.get(skey, book.get("generic", [])))
    for aid in order:
        add(aid, "builtin")
    for aid, src in kb_actions(ctx, device, ns.message):
        add(aid, src)
    ai, ai_on = ai_actions(ctx, device, packet)
    for aid, src in ai:
        add(aid, src)

    st = stats(ctx)
    tried_recently = cooldown_set(ctx, device, target) if use_cooldown else set()
    rows = []
    for aid, srcs in cands.items():
        key = (device, skey, aid)
        state = state_of(ctx, st, key, srcs)
        phys = bool(ctx.actions[aid].get("physical"))
        idx = order.index(aid) if aid in order else 99
        rows.append({"id": aid, "sources": srcs, "state": state, "physical": phys,
                     "rank": (phys, RISK_ORDER[ctx.actions[aid]["risk"]], -score(st, key), idx)})
    rows.sort(key=lambda r: r["rank"])

    out("")
    out("  %s · %s / %s  %s" % (t["head"], device, skey, "" if ctx.live else t["dry"]))
    out("  " + "─" * 60)
    for e in evidence:
        out("  %s %s: %s" % ({"ok": "✓", "warn": "·", "err": "✗"}[e["status"]], e["check"], e["result"]))
    if not ai_on:
        out("  · " + t["ai_off"])
    out("")
    out("  " + t["cands"])

    attempts, left, resolved = [], [], False
    max_n = ctx.policy.get("max_attempts_per_incident", 4)
    ran = 0
    for r in rows:
        aid = r["id"]
        a = ctx.actions[aid]
        d, tier = decide(ctx, device, aid, r["state"], r["sources"], tried_recently)
        label = "%s  [%s · %s]" % (ctx.desc(aid), a["risk"], ",".join(r["sources"]))
        if resolved:
            break
        if d == "needs_human":
            out("   · %s  → %s" % (label, t["human"])); left.append({"action": aid, "why": "human"}); continue
        if d == "demoted":
            out("   · %s  → %s" % (label, t["skip_demoted"])); left.append({"action": aid, "why": "demoted"}); continue
        if d == "denied":
            out("   · %s  → %s" % (label, t["skip_denied"])); left.append({"action": aid, "why": "denied"}); continue
        if d == "cooldown":
            out("   · %s  → %s" % (label, t["skip_cool"])); continue
        if tier == "approval" and aid not in approvals:
            out("   · %s  → %s" % (label, t["approval"])); left.append({"action": aid, "why": "approval"})
            append_jsonl(ctx.audit_path, {"ts": now(), "device": device, "target": target, "action": aid, "decision": "needs_approval"})
            continue
        if ran >= max_n:
            left.append({"action": aid, "why": "attempt_cap"}); continue
        if tier == "notify_then_act":
            out("   → %s: %s" % (t["notify"], ctx.desc(aid)))
            time.sleep(ctx.policy.get("notify_wait_seconds", 0))
        ok, output = execute(ctx, a, ns)
        ran += 1
        if scenario is not None:
            verified = aid in scenario
        else:
            verified = probe(ns) if ok else False
        row = {"ts": now(), "device": device, "target": target, "symptom": skey, "action": aid, "risk": a["risk"],
               "source": ",".join(r["sources"]), "tier": tier, "outcome": "ran" if ok else "failed_to_run",
               "verified": verified if ok else None, "live": ctx.live, "output": output[:200]}
        append_jsonl(ctx.attempts_path, row)
        append_jsonl(ctx.audit_path, {"ts": now(), "device": device, "target": target, "action": aid, "decision": "run", "tier": tier, "live": ctx.live})
        attempts.append({"action": aid, "tier": tier, "ran": ok, "recovered": verified if ok else None, "output": output})
        out("   %s %s  [%s]  %s" % ("→" if ok else "✗", ctx.desc(aid), tier,
                                  (t["fixed"] if verified else t["notfixed"]) if ok else output))
        if ok and verified:
            resolved = True
    out("  " + t["learned"])

    case = {"device_type": device, "symptom": ns.message, "root_cause": evidence[0]["result"] if evidence else "",
            "fix": ctx.desc(attempts[-1]["action"]) if resolved and attempts else "",
            "success": resolved, "attempts": [a["action"] for a in attempts], "_ts": now()}
    append_jsonl(ctx.cases_path, case)
    result = {"resolved": resolved, "attempts": attempts, "left": left, "evidence": evidence, "symptom": skey, "ticket": None}
    if not resolved:
        result["ticket"] = escalate(ns, ctx, result, quiet)
    return result


# ---------------------------------------------------------------- escalate

def explain(ctx, result):
    ev = [e for e in result["evidence"] if e["status"] == "err"]
    base = "; ".join("%s: %s" % (e["check"], e["result"]) for e in ev) or ctx.t["none"]
    return base


def escalate(ns, ctx, result, quiet=False):
    t, pol = ctx.t, ctx.policy.get("escalation", {})
    out = (lambda *a: None) if quiet else print
    group = pol.get("groups", {}).get(ns.type, "Service Desk")
    tried = ["%s → %s" % (ctx.desc(a["action"]), (t["fixed"] if a["recovered"] else t["notfixed"]) if a["ran"] else a["output"])
             for a in result["attempts"]] or [t["none"]]
    left = [ctx.desc(x["action"]) + " (" + x["why"] + ")" for x in result["left"]] or [t["none"]]
    cause = explain(ctx, result)
    body = "\n".join(["%s: %s (%s)" % (t["dev"], ns.type, ns.target), "%s: %s" % (t["sym"], ns.message),
                      "%s: %s" % (t["cause"], cause), "", t["tried"] + ":"] + ["  - " + x for x in tried] +
                     ["", t["left"] + ":"] + ["  - " + x for x in left])
    payload = {"short_description": "[Auto] %s %s: automatic repair failed" % (ns.type, ns.target),
               "description": body, "assignment_group": group, "urgency": "2", "impact": "2",
               "category": "hardware" if ns.type != "wifiap" else "network"}
    tickets = load_json(ctx.tickets_path, {"n": 0, "open": {}})
    key = "%s|%s|%s" % (ns.type, ns.target, result["symptom"])
    dup = key in tickets["open"]
    if dup:
        number = tickets["open"][key]
    else:
        tickets["n"] += 1
        number = "DRYRUN-INC%04d" % tickets["n"]
        tickets["open"][key] = number
    live = ctx.live and not pol.get("dry_run", True) and os.environ.get("SN_INSTANCE")
    if live and not dup:  # written to the Table API; not exercised against a real instance
        try:
            req = urllib.request.Request("https://%s/api/now/table/incident" % os.environ["SN_INSTANCE"],
                data=json.dumps(payload).encode(), method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json",
                         "Authorization": "Basic " + base64.b64encode(("%s:%s" % (os.environ["SN_USER"], os.environ["SN_PASSWORD"])).encode()).decode()})
            with urllib.request.urlopen(req, timeout=20) as r:
                number = json.load(r)["result"]["number"]
                tickets["open"][key] = number
        except Exception as e:
            number += " (live create failed: %s)" % e
    with open(ctx.tickets_path, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)
    alert = "\n".join(["", "  🔴 " + t["alert"], "  " + "─" * 60,
                       "  %s: %s (%s)" % (t["dev"], ns.type, ns.target), "  %s: %s" % (t["sym"], ns.message),
                       "  %s: %s" % (t["cause"], cause), "  %s:" % t["tried"]] + ["    - " + x for x in tried] +
                      ["  %s:" % t["left"]] + ["    - " + x for x in left] +
                      ["  %s: %s  ·  %s: %s%s" % (t["ticket"], number, t["group"], group,
                                                 "" if not dup else "\n  " + t["dup"])])
    out(alert)
    with open(ctx.alerts_path, "a", encoding="utf-8") as f:
        f.write("[%s]%s\n" % (now(), alert))
    return {"number": number, "group": group, "duplicate": dup, "payload": payload}


# ---------------------------------------------------------------- report / demo

def report(ctx):
    t = ctx.t
    st = stats(ctx)
    print("\n  %s\n  %s" % (t["report"], "─" * 60))
    if not st:
        print("  " + t["none"]); return
    print("  %-34s %-9s %-10s" % (t["cols"], t["rate"], t["state"]))
    for (dev, sym, aid), a in sorted(st.items()):
        srcs = ["builtin"] if aid in (ctx.runbooks.get(dev, {}).get(sym, []) + ctx.runbooks.get(dev, {}).get("generic", [])) else ["kb/ai"]
        s = state_of(ctx, st, (dev, sym, aid), srcs)
        print("  %-34s %-9s %-10s" % ("%s/%s/%s" % (dev, sym, aid), "%d/%d" % (a["successes"], a["attempts"]), t[s]))
    print()


def demo(lang):
    d = tempfile.mkdtemp(prefix="remediation-demo-")
    ctx = Ctx(d, lang, live=False)
    print("\n  demo data dir: %s  (simulated: no device is touched)" % d)
    mk = lambda ty, tg, msg: argparse.Namespace(type=ty, target=tg, source="demo", message=msg)
    # In this simulated site, the spooler restart never fixes a 13.20 jam but clearing the queue does.
    for i in (1, 2, 3, 4):
        print("\n  ═══ run %d: printer jam ═══" % i)
        remediate(mk("printer", "1.1.1.1", "PAPER JAM (13.20)"), ctx, scenario={"clear-queue"}, use_cooldown=False)
    print("\n  ═══ run 5: wireless AP, nothing we may do fixes it ═══")
    remediate(mk("wifiap", "192.0.2.50", "AP offline, clients dropping"), ctx, scenario=set(), use_cooldown=False)
    report(ctx)
    print("  files: %s" % ", ".join(sorted(os.listdir(d))))


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
        demo(a.lang); return
    ctx = Ctx(a.data_dir, a.lang, live=a.live or None)
    if a.report:
        report(ctx); return
    if not a.type or not a.message:
        ap.error("--type and --message are required (or use --demo / --report)")
    scen = None if a.simulate_fix is None else set(x for x in a.simulate_fix.split(",") if x)
    res = remediate(a, ctx, scenario=scen, approvals=set(x for x in a.approve.split(",") if x))
    sys.exit(0 if res["resolved"] else 2)


if __name__ == "__main__":
    main()
