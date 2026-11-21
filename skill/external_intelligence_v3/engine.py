#!/usr/bin/env python3
"""Incident Skeleton v3 global outage intelligence engine.

INTERNAL SIGNALS + VENDOR MCP + OFFICIAL STATUS + TRUSTED WEB
  -> CORRELATE -> DECIDE -> HOLD (advice only) -> NOTIFY (dry-run) -> RECHECK

Dry-run and advisory only. The engine never writes policy.json, never changes
permissions and never executes anything taken from internet text.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REMEDIATION_DIR = os.path.abspath(os.path.join(HERE, "..", "remediation"))
if REMEDIATION_DIR not in sys.path:
    sys.path.insert(0, REMEDIATION_DIR)

from harvest import injection_reason  # noqa: E402  (reuse the v1 security floor)

SOURCES = {"internal", "vendor_mcp", "official_status", "trusted_web", "public_report"}
EXTERNAL = SOURCES - {"internal"}
STATUSES = {"healthy", "degraded", "outage", "investigating", "resolved", "report"}
ACTIVE = {"degraded", "outage", "investigating", "report"}
HEALTHY = {"healthy", "resolved"}
STRONG = {"vendor_mcp", "official_status"}
REQUIRED = {"id", "observed_at", "source", "provider", "service", "region", "status", "summary"}

DECISIONS = {
    "vendor_incident_confirmed",
    "global_outage_likely",
    "local_issue_likely",
    "investigating",
    "resolved",
}

# Extra internet-text patterns on top of v1's INJECTION list.
EXTRA_INJECTION = [
    (r"ignore\s+(all\s+|any\s+)?(previous|prior|above)", "ignore_instructions"),
    (r"(system|developer)\s+prompt", "prompt_reference"),
    (r"\b(curl|wget|powershell|cmd\.exe|rm\s+-rf|sudo|invoke-expression|iex)\b", "command_text"),
    (r"(disable|bypass|edit|modify|change)\s+(the\s+)?(policy|guardrail|safety|approval)", "policy_tamper"),
    (r"(grant|elevate|add)\s+(admin|permission|privilege|role)", "permission_request"),
    (r"(auto[- ]?approve|approve\s+all)", "approval_bypass"),
    (r"忽略(之前|以上|所有)", "ignore_instructions"),
]

NAMES = {
    "microsoft": "Microsoft", "cisco": "Cisco", "teams": "Teams", "outlook": "Outlook",
    "exchange": "Exchange", "meraki": "Meraki", "webex": "Webex",
}
ACTION_ZH = {
    "password reset": "批量重置密码",
    "Office reinstall": "重装 Office",
}


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _name(value: str) -> str:
    return NAMES.get(value, value)


def _sha(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def injection_check(text: str) -> Optional[str]:
    reason = injection_reason(text or "")
    if reason:
        return reason
    for pattern, code in EXTRA_INJECTION:
        if re.search(pattern, text or "", re.I):
            return code
    return None


def clean_text(text: Any, limit: int = 240) -> str:
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    return re.sub(r"\s+", " ", value).strip()[:limit]


def fingerprint(signal: Dict[str, Any]) -> str:
    """Content fingerprint. Ignores id and observed_at so a re-poll of the same state is a duplicate."""
    keys = ("source", "provider", "service", "region", "status", "summary", "url", "tenant_impact", "site")
    return _sha([signal.get(k) for k in keys])


def adapt_vendor(connector: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map one raw vendor MCP/API record to the normalized contract using the connector's mapping.

    The result is flagged simulated/unauthenticated unless the caller proves otherwise.
    """
    m = connector["mapping"]
    service = raw.get(m["service_field"])
    status = raw.get(m["status_field"])
    return {
        "id": "%s:%s" % (connector["id"], raw.get(m["id_field"])),
        "observed_at": raw.get(m["time_field"]),
        "source": "vendor_mcp",
        "provider": connector["provider"],
        "service": m.get("service_map", {}).get(service, str(service).lower()),
        "region": "site" if m.get("site_field") else "tenant",
        "status": m.get("status_map", {}).get(status, "investigating"),
        "summary": raw.get(m["summary_field"], ""),
        "tenant_impact": int(raw.get(m.get("impact_field", ""), 0) or 0),
        "site": raw.get(m.get("site_field", ""), "") if m.get("site_field") else "",
        "connector": connector["id"],
        "authenticated": bool(connector.get("authenticated", False)),
        "simulated": connector.get("status") != "live",
    }


class GlobalIntelligenceEngine:
    def __init__(
        self,
        connectors_path: Optional[str] = None,
        policy_path: Optional[str] = None,
        state_path: Optional[str] = None,
        now: Optional[Callable[[], str]] = None,
    ) -> None:
        self.connectors_path = connectors_path or os.path.join(HERE, "connectors.json")
        self.policy_path = policy_path or os.path.join(REMEDIATION_DIR, "policy.json")
        self.config = _read_json(self.connectors_path)
        self.policy = _read_json(self.policy_path)  # read only; never written
        self.weights = dict(self.config["trust_weights"])
        self.th = dict(self.config["thresholds"])
        self.state_path = state_path
        self._now = now or _utc_now
        self._state = self._blank()
        if state_path and os.path.exists(state_path):
            loaded = _read_json(state_path)
            for k, v in self._blank().items():
                if k in loaded and isinstance(loaded[k], type(v)):
                    self._state[k] = loaded[k]
            for src, w in self._state["weights"].items():
                self.weights[src] = w

    @staticmethod
    def _blank() -> Dict[str, Any]:
        return {
            "latest": {}, "fingerprints": {}, "decisions": {}, "active": {}, "resolved": {},
            "notice_ids": [], "notices": [], "patterns": [], "versions": [], "rejected": [],
            "weights": {},
        }

    # ------------------------------------------------------------------ state
    def export_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)

    @property
    def patterns(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["patterns"])

    @property
    def versions(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["versions"])

    def _save(self) -> None:
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.state_path)), exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- ingest
    def _validate(self, signal: Any) -> Optional[str]:
        if not isinstance(signal, dict) or not REQUIRED <= set(signal):
            return "invalid_shape"
        if signal["source"] not in SOURCES:
            return "invalid_source"
        if signal["status"] not in STATUSES:
            return "invalid_status"
        try:
            if int(signal.get("tenant_impact", 0) or 0) < 0:
                return "invalid_impact"
        except (TypeError, ValueError):
            return "invalid_impact"
        url = str(signal.get("url") or "")
        if url and not re.match(r"^https?://", url):
            return "invalid_url"
        for field in ("summary", "url", "site", "service", "provider"):
            reason = injection_check(str(signal.get(field) or ""))
            if reason:
                return "injection:" + reason
        return None

    def ingest(self, signals: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        accepted, duplicates, rejected = [], [], []
        for raw in signals:
            reason = self._validate(raw)
            if reason:
                rec = {"id": str(raw.get("id", "?")) if isinstance(raw, dict) else "?",
                       "source": raw.get("source") if isinstance(raw, dict) else None,
                       "reason": reason, "treated_as": "untrusted data, never executed"}
                rejected.append(rec)
                self._state["rejected"].append(rec)
                continue
            sig = {k: raw.get(k) for k in REQUIRED}
            sig.update({
                "summary": clean_text(raw["summary"]),
                "url": str(raw.get("url") or ""),
                "tenant_impact": int(raw.get("tenant_impact", 0) or 0),
                "site": clean_text(raw.get("site") or "", 60),
            })
            for extra in ("symptom", "authenticated", "simulated", "connector"):
                if extra in raw:
                    sig[extra] = raw[extra]
            key = "|".join([sig["source"], sig["provider"], sig["service"], sig["site"] or sig["region"]])
            fp = fingerprint(sig)
            sig["fingerprint"] = fp
            prior = self._state["latest"].get(key)
            if prior and str(sig["observed_at"]) < str(prior["observed_at"]):
                duplicates.append({"id": sig["id"], "reason": "stale"})
                continue
            if prior and prior["fingerprint"] == fp:
                self._state["latest"][key]["observed_at"] = max(sig["observed_at"], prior["observed_at"])
                duplicates.append({"id": sig["id"], "reason": "unchanged"})
                continue
            self._state["latest"][key] = sig
            self._state["fingerprints"][fp] = sig["observed_at"]
            accepted.append(copy.deepcopy(sig))
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    # ------------------------------------------------------------- weighting
    def set_source_weight(self, source: str, weight: float, ts: Optional[str] = None, why: str = "") -> Dict[str, Any]:
        """Source reliability changes append a new version; they never rewrite history."""
        if source not in SOURCES or not 0 <= weight <= 1:
            raise ValueError("bad source or weight")
        old = self.weights.get(source)
        self.weights[source] = weight
        self._state["weights"][source] = weight
        entry = {"kind": "source_reliability", "source": source, "from": old, "to": weight,
                 "why": clean_text(why, 120), "ts": ts or self._now(),
                 "version": "3.0.%d" % (len(self._state["patterns"]) + len(self._state["versions"]) + 1)}
        self._state["versions"].append(entry)
        self._save()
        return copy.deepcopy(entry)

    # ------------------------------------------------------------- correlate
    def _signals_for(self, provider: str, service: str) -> List[Dict[str, Any]]:
        return [s for s in self._state["latest"].values() if s["provider"] == provider and s["service"] == service]

    def _known_keys(self) -> List[tuple]:
        return sorted({(s["provider"], s["service"]) for s in self._state["latest"].values()})

    def _evidence(self, sig: Dict[str, Any], stance: str) -> Dict[str, Any]:
        return {
            "source": sig["source"], "status": sig["status"], "stance": stance,
            "weight": self.weights[sig["source"]], "summary": sig["summary"], "url": sig["url"],
            "site": sig["site"], "users": sig["tenant_impact"], "observed_at": sig["observed_at"],
            "authenticated": bool(sig.get("authenticated", False)),
            "simulated": bool(sig.get("simulated", True)),
        }

    def evaluate(self, provider: str, service: str, ts: Optional[str] = None) -> Dict[str, Any]:
        ts = ts or self._now()
        key = "%s|%s" % (provider, service)
        sigs = self._signals_for(provider, service)
        internal = [s for s in sigs if s["source"] == "internal"]
        external = [s for s in sigs if s["source"] in EXTERNAL]
        int_active = [s for s in internal if s["status"] in ACTIVE and s["tenant_impact"] > 0]
        users = sum(s["tenant_impact"] for s in int_active)
        sites = sorted({s["site"] for s in int_active if s["site"]})
        multi = users >= self.th["min_users"] and len(sites) >= self.th["min_sites"]
        single = bool(int_active) and len(sites) <= 1
        ext_active = [s for s in external if s["status"] in ACTIVE]
        ext_ok = [s for s in external if s["status"] in HEALTHY]
        strong_active = [s for s in ext_active if s["source"] in STRONG]
        strong_ok = [s for s in ext_ok if s["source"] in STRONG]
        was_active = bool(self._state["active"].get(key))
        core_active = [s for s in ext_active if s["source"] != "public_report"]  # weak reports never block recovery

        support: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        decision, reason = "investigating", "incomplete_evidence"

        # Support / conflict evidence relative to "this is a vendor-wide incident".
        for s in ext_active:
            support.append(self._evidence(s, "supports"))
        for s in ext_ok:
            conflicts.append(self._evidence(s, "conflicts"))
        for s in int_active:
            (support if multi else conflicts).append(self._evidence(s, "supports" if multi else "conflicts"))
        for s in internal:
            if s not in int_active and s["status"] in HEALTHY:
                conflicts.append(self._evidence(s, "conflicts"))

        active_sources = {s["source"] for s in ext_active}
        decisive = active_sources & (STRONG | {"trusted_web"})

        if was_active and not core_active and ext_ok and not int_active:
            decision, reason = "resolved", "vendor_and_internal_recovered"
        elif was_active and (bool(core_active) != bool(int_active)):
            decision, reason = "investigating", "recovery_pending"
        elif strong_active and strong_ok:
            decision, reason = "investigating", "conflicting_vendor_evidence"
        elif strong_active and multi:
            decision, reason = "vendor_incident_confirmed", "official_evidence_matches_internal_pattern"
        elif multi and len(active_sources) >= 2 and decisive and not strong_ok:
            decision, reason = "global_outage_likely", "multiple_independent_sources_match_internal_pattern"
        elif multi and strong_ok and not ext_active:
            decision, reason = "investigating", "internal_pattern_vs_healthy_vendor"
        elif single and strong_ok and not ext_active:
            decision, reason = "local_issue_likely", "one_site_affected_vendor_healthy"
        elif ext_active and not int_active:
            decision, reason = "investigating", "no_matching_internal_impact"
        elif active_sources == {"public_report"} or (ext_active and not decisive):
            decision, reason = "investigating", "weak_sources_only"
        elif was_active is False and self._state["resolved"].get(key) and not int_active and not ext_active:
            decision, reason = "resolved", "vendor_and_internal_recovered"

        confidence = self._confidence(decision, support, conflicts)
        provider_cfg = self.config["providers"].get(provider, {})
        holding = decision in ("vendor_incident_confirmed", "global_outage_likely") or (
            decision == "investigating" and reason == "recovery_pending")
        hold = list(provider_cfg.get("held_actions", [])) if holding else []
        recommendation = {
            "mode": "advisory_dry_run",
            "hold": hold,
            "keep_running": ["read-only health checks", "vendor status recheck", "ticket grouping"],
            "route": "local network crew" if decision == "local_issue_likely" else (
                "vendor incident watch" if holding else "triage"),
            "permission_changes": [],
            "policy_modified": False,
            "policy_mode": self.policy.get("mode"),
        }
        group = "GINC-" + _sha(key)[:8] if holding else ""
        return {
            "key": key, "provider": provider, "service": service, "decision": decision,
            "reason": reason, "confidence": confidence, "support": support, "conflicts": conflicts,
            "users": users, "sites": sites, "multi_user_pattern": multi,
            "parent_incident": group, "grouped_signals": len(int_active) if holding else 0,
            "recommendation": recommendation,
            "next_check": self._plus(ts, self.th["recheck_minutes"]) if decision != "resolved" else None,
            "dry_run": True,
        }

    def _confidence(self, decision: str, support: List[Dict], conflicts: List[Dict]) -> float:
        if decision == "resolved":
            return 0.9
        sup = {e["source"]: e["weight"] for e in support if e["source"] != "public_report"}
        pub = 0.04 if any(e["source"] == "public_report" for e in support) else 0.0
        con = sum({e["source"]: e["weight"] for e in conflicts}.values())
        score = sum(sup.values()) + pub
        if decision == "local_issue_likely":
            score = sum(e["weight"] for e in conflicts if e["source"] in STRONG) + 0.25
            con = 0
        score -= 0.8 * con if decision not in ("local_issue_likely",) else 0
        return round(max(0.05, min(0.99, score)), 2)

    @staticmethod
    def _plus(ts: str, minutes: int) -> str:
        try:
            base = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (base + timedelta(minutes=minutes)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return ts

    # ----------------------------------------------------------------- notice
    def _notice(self, d: Dict[str, Any], ts: str) -> Optional[Dict[str, Any]]:
        if d["decision"] == "investigating":
            return None
        nid = _sha(d["key"], d["decision"])[:16]
        if nid in self._state["notice_ids"]:
            return None
        p, s = _name(d["provider"]), _name(d["service"])
        pct = int(round(d["confidence"] * 100))
        hold_en = ", ".join(d["recommendation"]["hold"]) or "nothing"
        hold_zh = "、".join(ACTION_ZH.get(action, action) for action in d["recommendation"]["hold"]) or "无"
        nxt = d["next_check"] or "n/a"
        nxt_zh = nxt.replace("T", " ").replace("Z", " UTC")
        tpl = {
            "vendor_incident_confirmed": (
                ("%s %s vendor incident confirmed" % (p, s),
                 "Official evidence matches %d affected users across %d sites (confidence %d%%). Duplicate tickets are grouped under one parent. Recommend holding: %s. Users do not need to report again. Next check: %s."
                 % (d["users"], len(d["sites"]), pct, hold_en, nxt)),
                ("%s %s 厂商故障已确认" % (p, s),
                 "官方证据与 %d 名受影响用户（%d 个站点）吻合，置信度 %d%%。重复工单已合并为一个父事件。建议暂停：%s。用户无需重复报障。下次复查：%s。"
                 % (d["users"], len(d["sites"]), pct, hold_zh, nxt_zh))),
            "global_outage_likely": (
                ("%s %s global outage likely" % (p, s),
                 "Several independent sources match %d affected users (confidence %d%%). Recommend holding: %s. Next check: %s."
                 % (d["users"], pct, hold_en, nxt)),
                ("%s %s 很可能是全局故障" % (p, s),
                 "多个独立来源与 %d 名受影响用户吻合，置信度 %d%%。建议暂停：%s。下次复查：%s。"
                 % (d["users"], pct, hold_zh, nxt))),
            "local_issue_likely": (
                ("%s %s looks local" % (p, s),
                 "Only one site is affected and vendor status is healthy (confidence %d%%). Keep the local repair path."
                 % pct),
                ("%s %s 更像本地故障" % (p, s),
                 "仅一个站点受影响，厂商状态正常，置信度 %d%%。保持本地维修流程。" % pct)),
            "resolved": (
                ("%s %s recovered" % (p, s),
                 "Vendor reports resolution and internal checks have recovered. Held actions can return to normal policy review."),
                ("%s %s 已恢复" % (p, s),
                 "厂商已报告恢复，内部检查也已恢复。暂停的动作可回到正常策略审批流程。")),
        }[d["decision"]]
        notice = {
            "id": nid, "ts": ts, "key": d["key"], "decision": d["decision"], "dry_run": True,
            "channels": ["IT on-call", "Service desk"],
            "en": {"title": tpl[0][0], "body": tpl[0][1] + " [DRY-RUN: nothing was sent]"},
            "zh": {"title": tpl[1][0], "body": tpl[1][1] + " [演练模式：未实际发送]"},
        }
        self._state["notice_ids"].append(nid)
        self._state["notices"].append(notice)
        return notice

    # ---------------------------------------------------------------- pattern
    def _pattern(self, d: Dict[str, Any], ts: str) -> Dict[str, Any]:
        prev = self._state["decisions"].get(d["key"], {})
        symptoms = sorted({s["symptom"] for s in self._signals_for(d["provider"], d["service"]) if s.get("symptom")})
        last = prev.get("last_active", {})
        symptoms += [x for x in ("many users", "multiple sites") if last.get("multi")]
        pattern = {
            "provider": d["provider"], "service": d["service"],
            "symptoms": symptoms,
            "best_sources": last.get("best_sources", []),
            "decision": last.get("decision", "vendor_incident_confirmed"),
            "held_actions": last.get("hold", []),
            "version": "3.0.%d" % (len(self._state["patterns"]) + 1),
            "resolved_at": ts,
        }
        self._state["patterns"].append(pattern)
        self._state["versions"].append({"kind": "pattern", "key": d["key"], "version": pattern["version"], "ts": ts})
        return copy.deepcopy(pattern)

    # ------------------------------------------------------------------ cycle
    def run_cycle(self, signals: List[Dict[str, Any]], ts: Optional[str] = None) -> Dict[str, Any]:
        ts = ts or self._now()
        res = self.ingest(signals)
        v_before = len(self._state["versions"])
        decisions, notices, patterns, correlations = [], [], [], []
        for provider, service in self._known_keys():
            d = self.evaluate(provider, service, ts)
            key = d["key"]
            rec = self._state["decisions"].setdefault(key, {})
            if d["decision"] in ("vendor_incident_confirmed", "global_outage_likely"):
                self._state["active"][key] = True
                self._state["resolved"][key] = False
                rec["last_active"] = {
                    "decision": d["decision"], "hold": d["recommendation"]["hold"], "multi": d["multi_user_pattern"],
                    "best_sources": sorted({e["source"] for e in d["support"] if e["source"] in EXTERNAL - {"public_report"}}),
                }
            elif d["decision"] == "resolved" and self._state["active"].get(key):
                patterns.append(self._pattern(d, ts))
                self._state["active"][key] = False
                self._state["resolved"][key] = True
            elif d["decision"] == "resolved":
                pass
            notice = self._notice(d, ts)
            if notice:
                notices.append(notice)
            rec["decision"] = d["decision"]
            decisions.append(d)
            correlations.append({
                "key": key, "supporting": len(d["support"]), "conflicting": len(d["conflicts"]),
                "sources": sorted({e["source"] for e in d["support"]}), "users": d["users"], "sites": len(d["sites"]),
            })
        self._save()
        return {
            "ts": ts, "signals": res["accepted"], "duplicates": res["duplicates"], "rejected": res["rejected"],
            "correlations": correlations, "decisions": decisions, "notices": notices,
            "patterns": patterns, "versions": copy.deepcopy(self._state["versions"][v_before:]),
        }
