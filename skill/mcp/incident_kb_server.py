#!/usr/bin/env python3
"""Incident KB — a minimal MCP server for Incident Skeleton (Kiroween 2026).

This is a REAL MCP server (Model Context Protocol, stdio JSON-RPC). It exposes
three tools an agent can call while walking the skeleton, foreshadowing the
roadmap's ServiceNow routing, knowledge gathering, and the 病例库:

  - lookup_support_group(device_type) -> the ServiceNow-style assignment group
        (roadmap step 1: auto-route an incident to the right IT group)
  - recall_fix(symptom)               -> known fixes from the local KB
        (roadmap step 4: gather solutions before applying)
  - record_case(device_type, symptom, root_cause, fix, success) -> append to
        the case-history KB  (roadmap step 5: the 病例库)

Register it in Kiro Crew under Customize -> Connections -> MCP Servers:
    command:  python3
    args:     <repo>/skill/mcp/incident_kb_server.py

Then an agent running the incident-skeleton skill can call these tools during
TRIAGE (route), INVESTIGATE/MITIGATE (recall a fix), and LOG (record the case).

Test by piping JSON-RPC lines:
    printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | python3 incident_kb_server.py
"""
import json, sys, os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "kb.json")
CASES = os.path.join(HERE, "case_history.jsonl")

SUPPORT_GROUPS = {
    "printer": "Print Services",
    "signage": "AV / Digital Signage",
    "av": "Meeting Rooms / AV",
    "wifiap": "Network / Wireless",
}

TOOLS = [
    {
        "name": "lookup_support_group",
        "description": "Return the ServiceNow-style assignment group for a device type, used to auto-route an incident.",
        "inputSchema": {
            "type": "object",
            "properties": {"device_type": {"type": "string", "enum": ["printer", "signage", "av", "wifiap"]}},
            "required": ["device_type"],
        },
    },
    {
        "name": "recall_fix",
        "description": "Recall known fixes for a symptom from the local knowledge base (KB). Empty hit means gather from ServiceNow KB / shared drive / chat.",
        "inputSchema": {
            "type": "object",
            "properties": {"symptom": {"type": "string", "description": "free-text symptom, e.g. 'paper jam 13.20' or 'AP offline clients dropping'"}},
            "required": ["symptom"],
        },
    },
    {
        "name": "record_case",
        "description": "Append a resolved case to the case-history KB (病例库). Only call after a fix is confirmed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_type": {"type": "string"},
                "symptom": {"type": "string"},
                "root_cause": {"type": "string"},
                "fix": {"type": "string"},
                "success": {"type": "boolean"},
            },
            "required": ["device_type", "symptom", "fix", "success"],
        },
    },
]


def load_kb():
    if os.path.exists(KB):
        with open(KB, encoding="utf-8") as f:
            return json.load(f)
    return {}


def text(content):
    return {"content": [{"type": "text", "text": content}]}


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params", {}) or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "incident-kb", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        }}
    if method == "notifications/initialized":
        return None  # notification -> no response
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        if name == "lookup_support_group":
            g = SUPPORT_GROUPS.get(args.get("device_type"), "Unknown")
            return {"jsonrpc": "2.0", "id": rid, "result": text(f"assignment_group: {g}")}
        if name == "recall_fix":
            sym = (args.get("symptom") or "").lower()
            kb = load_kb()
            hits = [v for k, v in kb.items() if k in sym] if sym else []
            if not hits and sym:
                hits = list(kb.values())
            msg = json.dumps(hits[:5], ensure_ascii=False) if hits else \
                "no known fix in KB; gather from ServiceNow KB / shared drive / chat history"
            return {"jsonrpc": "2.0", "id": rid, "result": text(msg)}
        if name == "record_case":
            case = dict(args)
            case["_ts"] = datetime.now().isoformat(timespec="seconds")
            with open(CASES, "a", encoding="utf-8") as f:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
            return {"jsonrpc": "2.0", "id": rid, "result": text(f"recorded case to {os.path.basename(CASES)}")}
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown tool: " + str(name)}}

    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: " + str(method)}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = handle(req)
        except Exception as e:  # noqa
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32603, "message": str(e)}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
