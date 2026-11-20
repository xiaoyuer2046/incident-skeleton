#!/usr/bin/env python3
"""Incident Skeleton MCP server (stdio JSON-RPC) — lets a Kiro agent work with the SAME data the crew uses.

It reads the engine's own data directory (skill/remediation/data, or INCIDENT_DATA_DIR):
the case library, the learned success rates, the policy, tickets and the latest patrol.

Tools
  lookup_support_group(device_type)          the ServiceNow assignment group, from policy.json
  recall_fix(device_type, symptom)           ranked candidate fixes: runbook + verified case library
                                             + success rates learned here, with the permission tier
  crew_status(question)                      plain-language status ("what's wrong with 2F-201?"),
                                             answered by chatops.py. Read-only: it refuses approve / stop
  list_open_tickets()                        open tickets with the tracker's latest status summary
  record_case(device_type, symptom, fix, success, root_cause?)
                                             add a resolved case to the case history

Approvals and the kill switch are deliberately NOT exposed here: they need a named person
(chatops.py with the chat platform's sender identity, or the CLI).

Register in Kiro Crew: Customize → Connections → MCP Servers → command `python3`, args <this file>.
Test:  printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | python3 incident_kb_server.py
"""
import json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REM = os.path.join(HERE, "..", "remediation")
sys.path.insert(0, REM)
os.environ.setdefault("BRAIN", "off")
import remediate as rm
import chatops

DATA = os.environ.get("INCIDENT_DATA_DIR") or os.path.join(REM, "data")
TYPES = ["printer", "signage", "av", "wifiap"]

TOOLS = [
    {"name": "lookup_support_group", "description": "ServiceNow assignment group for a device type (from policy.json).",
     "inputSchema": {"type": "object", "properties": {"device_type": {"type": "string", "enum": TYPES}}, "required": ["device_type"]}},
    {"name": "recall_fix", "description": "Ranked candidate fixes for a device type and symptom text: runbook, verified case-library entries and success rates learned here, each with its risk and permission tier. Advisory: the policy still decides.",
     "inputSchema": {"type": "object", "properties": {"device_type": {"type": "string", "enum": TYPES},
                    "symptom": {"type": "string", "description": "free text, e.g. 'paper jam 13.20' or 'panel frozen, cannot join'"}}, "required": ["device_type", "symptom"]}},
    {"name": "crew_status", "description": "Ask the crew in plain words what is going on (a device, a floor's outage, or what is broken). Read-only.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "list_open_tickets", "description": "Open tickets with their latest automatic status summary (who is on it, latest news, ETA, what it waits for).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "record_case", "description": "Add a resolved case to the case history. Call only after a fix is confirmed.",
     "inputSchema": {"type": "object", "properties": {"device_type": {"type": "string", "enum": TYPES}, "symptom": {"type": "string"},
                    "fix": {"type": "string"}, "success": {"type": "boolean"}, "root_cause": {"type": "string"}},
                    "required": ["device_type", "symptom", "fix", "success"]}},
]


def ctx():
    return rm.Ctx(DATA, "en", live=False)


def recall_fix(c, device, symptom):
    rm.ensure_library(c)
    skey = rm.symptom_key(device, symptom)
    st = rm.stats(c)
    book = c.runbooks.get(device, {})
    cands = {a: ["runbook"] for a in book.get(skey, book.get("generic", []))}
    for e in rm.library_for(c, device, skey):
        if e.get("action") and e.get("status") == "verified":
            cands.setdefault(e["action"], []).append("case library %s (%d verified)" % (e["id"], e.get("verified", 0)))
    out = []
    for a, srcs in cands.items():
        act = c.actions.get(a, {})
        h = st.get((device, skey, a), {"attempts": 0, "successes": 0})
        tier = "never automatic (on site)" if act.get("physical") else c.policy.get("autonomy", {}).get(act.get("risk"), "approval")
        out.append({"action": a, "name": act.get("en"), "risk": act.get("risk"), "tier": tier, "sources": srcs,
                    "learned_here": "%d/%d" % (h["successes"], h["attempts"]), "allowed": a in c.policy.get("allow", {}).get(device, [])})
    out.sort(key=lambda x: (x["tier"].startswith("never"), {"low": 0, "medium": 1, "high": 2}.get(x["risk"], 3)))
    advice = [e["text"] for e in rm.library_for(c, device, skey) if e.get("kind") == "engineer" and e.get("status") == "verified"]
    return {"symptom": skey, "candidates": out, "engineer_advice": advice[:5]}


def call(name, args):
    c = ctx()
    if name == "lookup_support_group":
        return {"assignment_group": c.policy.get("escalation", {}).get("groups", {}).get(args.get("device_type"), "Service Desk")}
    if name == "recall_fix":
        return recall_fix(c, args.get("device_type"), args.get("symptom", ""))
    if name == "crew_status":
        q = args.get("question", "")
        r = chatops.handle(c, "mcp-reader", q)
        if r["intent"] != "status":
            return {"refused": "crew_status is read-only. Approvals, stop and resume need a named person in chat or the CLI."}
        return {"answer": r["reply"]["en"], "answer_zh": r["reply"]["zh"], "refs": r["refs"]}
    if name == "list_open_tickets":
        tks = rm.tickets_load(c)["tickets"].values()
        out = []
        for t in tks:
            if t["state"] in rm.OPEN_STATES:
                s = next((n["data"]["summary"]["en"] for n in reversed(t["work_notes"]) if n["kind"] == "status_summary"), None)
                out.append({"number": t["number"], "ci": t["cmdb_ci"], "state": t["state"], "group": t["assignment_group"], "status_summary": s})
        return {"open": out}
    if name == "record_case":
        row = dict(args, device_type=args.get("device_type"), _ts=datetime.now().isoformat(timespec="seconds"), via="mcp")
        rm.append_jsonl(c.cases_path, row)
        return {"recorded": True, "file": os.path.relpath(c.cases_path, os.path.join(HERE, "..", ".."))}
    raise KeyError(name)


def handle(req):
    m, rid, p = req.get("method"), req.get("id"), req.get("params") or {}
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "incident-skeleton", "version": "0.2.0"},
                                                       "capabilities": {"tools": {}}}}
    if m == "notifications/initialized":
        return None
    if m == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if m == "tools/call":
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
        except KeyError:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown tool: %s" % p.get("name")}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: %s" % m}}


def main():
    os.makedirs(DATA, exist_ok=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        try:
            resp = handle(req)
        except Exception as e:  # noqa: keep the server alive
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32603, "message": str(e)}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
