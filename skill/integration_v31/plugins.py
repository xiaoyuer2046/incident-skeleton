"""v3.1 plug-ins: the v3 global gate (TRIAGE) and the v2 ranking / learning helpers (MITIGATE, LOG).

Invariant: learning may narrow permission, never widen it. Nothing here writes policy.json or app.json;
the only permission change is an in-memory copy of an allow-list with entries removed, for one call.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
REM = os.path.join(SKILL, "remediation")
APP = os.path.join(SKILL, "apps", "servicedesk")
for _p in (APP, REM, SKILL):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("BRAIN", "off")

import remediate as rm  # noqa: E402
from evolution_v2.engine import EvolutionEngine, method_key  # noqa: E402
from external_intelligence_v3.engine import GlobalIntelligenceEngine, STRONG  # noqa: E402

from . import STATES  # noqa: E402

SIGNALS = os.path.join(SKILL, "external_intelligence_v3", "signals.json")
SOURCES_V2 = os.path.join(SKILL, "evolution_v2", "sources.json")

# v3.1 service detection (app.json has no Teams keyword). First match wins.
SERVICES = [
    ("microsoft", "teams", ("teams", "会议软件")),
    ("microsoft", "outlook", ("outlook", "邮件", "邮箱", "exchange")),
    ("cisco", "meraki", ("wi-fi", "wifi", "无线", "meraki")),
]
LABELS = {
    ("microsoft", "teams"): {"en": "Microsoft Teams", "zh": "Microsoft Teams"},
    ("microsoft", "outlook"): {"en": "Microsoft Outlook", "zh": "Microsoft Outlook"},
    ("cisco", "meraki"): {"en": "Cisco Meraki Wi-Fi", "zh": "Cisco Meraki 无线网络"},
}
# v3 held action (display name) -> app 2 action ids held while the vendor incident is active
HELD_MAP = {
    "password reset": ["send-reset-link", "unlock-account", "reset-mfa"],
    "Office reinstall": ["repair-app-install", "send-outlook-steps"],
}
VERDICT_EN = {"local_issue_likely": "one site affected and the vendor is healthy, so it is local",
              "investigating": "vendor not confirmed down, normal path", "resolved": "vendor recovered, normal path"}
LINKING = ("vendor_incident_confirmed", "global_outage_likely")


def detect_service(text: str) -> Optional[tuple]:
    t = (text or "").lower()
    for provider, service, words in SERVICES:
        if any(w in t for w in words):
            return provider, service
    return None


def _next_check_zh(ts: Optional[str]) -> str:
    return (ts or "n/a").replace("T", " ").replace("Z", " UTC")


class GlobalGate:
    """Wraps the v3 engine (in memory, no state file) and answers one question per request."""

    def __init__(self, signals_path: str = SIGNALS) -> None:
        with open(signals_path, encoding="utf-8") as handle:
            self.cycles = json.load(handle)["cycles"]
        self.engine = GlobalIntelligenceEngine()  # no state_path: nothing is saved
        self.index = 0
        self.ts = self.cycles[0]["ts"]
        self.notices: List[Dict[str, Any]] = []
        self.decisions: Dict[str, Dict[str, Any]] = {}  # latest decision per 'provider|service', as v3 decided it in its cycle
        self.resolved: set = set()
        self.calls = 0

    def advance(self, upto: int) -> List[Dict[str, Any]]:
        """Run v3 cycles until `upto` cycles have been processed."""
        out = []
        while self.index < min(upto, len(self.cycles)):
            cyc = self.cycles[self.index]
            res = self.engine.run_cycle(cyc["signals"], cyc["ts"])
            self.ts = cyc["ts"]
            self.notices += res["notices"]
            for d in res["decisions"]:
                self.decisions[d["key"]] = d
                if d["decision"] == "resolved":
                    self.resolved.add(d["key"])
                elif d["decision"] in LINKING:
                    self.resolved.discard(d["key"])
            out.append(res)
            self.index += 1
        return out

    def decision_for(self, provider: str, service: str) -> Dict[str, Any]:
        """The decision v3 reached in its latest cycle (re-evaluating later can differ once the incident is archived)."""
        return self.decisions.get("%s|%s" % (provider, service)) or self.engine.evaluate(provider, service, self.ts)

    def is_resolved(self, provider: str, service: str) -> bool:
        """True once v3 reported `resolved` and the vendor incident has not come back since."""
        return "%s|%s" % (provider, service) in self.resolved

    def check(self, text: str) -> Optional[Dict[str, Any]]:
        """None when the text names no covered service. Otherwise the gate verdict for that service."""
        self.calls += 1
        found = detect_service(text)
        if not found:
            return None
        provider, service = found
        d = self.decision_for(provider, service)
        hold = list(d["recommendation"]["hold"])
        link = d["decision"] in LINKING
        strong = [e for e in d["support"] if e["source"] in STRONG]
        held_ids: List[str] = []
        for name in hold:
            for aid in HELD_MAP.get(name, []):
                if aid not in held_ids:
                    held_ids.append(aid)
        return {
            "provider": provider, "service": service, "key": d["key"],
            "decision": d["decision"], "reason": d["reason"], "confidence": d["confidence"],
            "link": link, "hold": hold, "held_ids": held_ids,
            "label": dict(LABELS[(provider, service)]),
            "parent_id": d["parent_incident"],
            "next_check": d["next_check"],
            "users": d["users"], "sites": list(d["sites"]),
            "vendor_summary": strong[0]["summary"] if strong else "",
            "evidence": bool(d["support"] or d["conflicts"]),
        }


# ------------------------------------------------------------------ v2 plug-ins

def new_evolution(now: str = "2026-11-21T09:00:00Z", sources_path: str = SOURCES_V2) -> EvolutionEngine:
    """In-memory v2 engine fed with the existing v2 sample sources (no state file)."""
    clock = {"v": now}
    engine = EvolutionEngine(now=lambda: clock["v"])
    with open(sources_path, encoding="utf-8") as handle:
        records = json.load(handle)
    engine.watch_many(records)
    return engine


def v2_view(evo: Optional[EvolutionEngine], device: str, symptom: str):
    """(hints, paused) for one device fault. promoted -> hint, demoted -> paused, others unchanged."""
    hints: Dict[str, str] = {}
    paused: List[str] = []
    if evo is None:
        return hints, paused
    for method in evo.methods.values():
        if method["device"] == device and method["symptom"] == symptom:
            if method["state"] == "promoted":
                hints[method["action"]] = "v2 adopted %d/%d" % (method["successes"], method["attempts"])
            elif method["state"] == "demoted":
                paused.append(method["action"])
    return hints, paused


@contextmanager
def narrowed_allow(ctx, remove_by_device: Dict[str, List[str]]):
    """Remove action ids from an in-memory copy of ctx.policy['allow'] for the duration of one call.
    Key '*' applies to every device. Can only remove: the result is always a subset of the original."""
    original = ctx.policy
    pol = copy.deepcopy(original)
    allow = pol.setdefault("allow", {})
    for device, base in list(original.get("allow", {}).items()):
        gone = set(remove_by_device.get(device, [])) | set(remove_by_device.get("*", []))
        allow[device] = [a for a in base if a not in gone]
        assert set(allow[device]) <= set(base)
    ctx.policy = pol
    try:
        yield pol["allow"]
    finally:
        ctx.policy = original


def learn_from_recheck(ctx, evo: Optional[EvolutionEngine], statuses: Dict[str, str]) -> List[Dict[str, Any]]:
    """LOG: run the delayed re-check (clock moved past recheck_due for this call) and teach v2.
    Provisional attempts have confirmed=None and are ignored by absorb_attempt."""
    if evo is None:
        return []
    original = ctx.clock
    wait = ctx.policy.get("recheck_minutes", 10) * 60 + 60
    ctx.clock = lambda: original() + wait
    try:
        rm.recheck(ctx, statuses)
    finally:
        ctx.clock = original
    events = []
    for row in rm.read_jsonl(ctx.attempts_path):
        if isinstance(row.get("confirmed"), bool):
            event = evo.absorb_attempt(row)
            if event:
                events.append(event)
    return events


# ------------------------------------------------------------------ skeleton record

KINDS = {"RECEIVE": "shared", "TRIAGE": "shared", "INVESTIGATE": "crew", "MITIGATE": "crew", "RESOLVE": "shared", "LOG": "shared"}


def skeleton(app: str, rid: str, title: Dict[str, str], outcome: str, states: Dict[str, Dict[str, Any]],
             held: Optional[List[str]] = None, parent: Any = None) -> Dict[str, Any]:
    """Build the section-6 record. `states` maps a state name to {'en','zh','plugin'}; order is fixed here."""
    rows = []
    for name in STATES:
        s = states[name]
        rows.append({"name": name, "kind": KINDS[name], "plugin": s.get("plugin"), "en": s["en"], "zh": s["zh"]})
    return {"app": app, "id": rid, "title": title, "outcome": outcome, "states": rows,
            "held_actions": list(held or []), "parent": parent, "dry_run": True}
