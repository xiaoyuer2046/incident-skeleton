"""Incident Skeleton v4 learning engine: vendor MCP and official sources first, then internal, then the internet.

Order A -> B -> C -> D. A Tier C or D source never creates a usable method on its own; it needs a Tier A or B
source that names the same device, symptom and action. A public report (D) never promotes or demotes anything.
A vendor advisory that calls a method harmful pauses it. Every change appends an immutable 4.0.N version and one
bilingual dry-run notice. Learning only NARROWS permission (a method is paused in memory). Nothing here ever writes
policy.json, actions.json or app.json: they are read only, per app, and stay the one source of permission.

Reuses: v2 `method_key` and labels, v1 `harvest.injection_reason` / `map_actions`, v3 `injection_check`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import SKILL  # noqa: F401  (also puts the v1 modules on sys.path)
from harvest import map_actions  # noqa: E402
from evolution_v2.engine import DEVICE_LABELS, SYMPTOM_LABELS, method_key  # noqa: E402
from external_intelligence_v3.engine import injection_check  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(HERE, "learning_sources.json")
APP_FILES = {
    "devices": (os.path.join(SKILL, "remediation", "actions.json"), os.path.join(SKILL, "remediation", "policy.json")),
    "servicedesk": (os.path.join(SKILL, "apps", "servicedesk", "actions.json"), os.path.join(SKILL, "apps", "servicedesk", "policy.json")),
}
TIERS = ("A", "B", "C", "D")
SOURCE_TIER = {"vendor_mcp": "A", "official_status": "A", "servicenow_kb": "B", "incident": "B", "chat": "B", "email": "B",
               "shared_drive": "B", "trusted_web": "C", "public_report": "D"}
WEIGHT = {"vendor_mcp": 0.45, "official_status": 0.35, "servicenow_kb": 0.30, "incident": 0.30, "chat": 0.20, "email": 0.20,
          "shared_drive": 0.20, "trusted_web": 0.10, "public_report": 0.04}
TIER_LABEL = {
    "A": {"en": "Vendor and official sources", "zh": "厂商与官方来源"},
    "B": {"en": "Company sources", "zh": "公司内部来源"},
    "C": {"en": "Trusted web", "zh": "可信网站"},
    "D": {"en": "Public reports", "zh": "公开传言"},
}
SOURCE_LABEL = {
    "vendor_mcp": {"en": "Vendor MCP server", "zh": "厂商 MCP 服务"}, "official_status": {"en": "Official status page", "zh": "官方状态页"},
    "servicenow_kb": {"en": "ServiceNow KB", "zh": "ServiceNow 知识库"}, "incident": {"en": "Resolved ticket", "zh": "已解决工单"},
    "chat": {"en": "Team chat", "zh": "团队聊天"}, "email": {"en": "Email", "zh": "邮件"}, "shared_drive": {"en": "Shared drive", "zh": "共享盘"},
    "trusted_web": {"en": "Trusted web page", "zh": "可信网页"}, "public_report": {"en": "Public report", "zh": "公开帖子"},
}
STATE = {
    "unseen": {"en": "not seen", "zh": "未见过"}, "held_back": {"en": "held back", "zh": "暂不采信"},
    "candidate": {"en": "needs verification", "zh": "待验证"}, "trial": {"en": "being verified", "zh": "验证中"},
    "promoted": {"en": "adopted", "zh": "已采用"}, "paused": {"en": "paused", "zh": "已暂停"}, "rejected": {"en": "rejected", "zh": "已拦截"},
}
REASON = {
    "source_change": {"en": "new guidance from the source", "zh": "来源给出了新做法"},
    "advisory_harmful": {"en": "the vendor says this method is harmful or deprecated", "zh": "厂商通告说这个做法有害或已弃用"},
    "verified_outcome": {"en": "a confirmed re-check", "zh": "复查已确认"}, "regression": {"en": "it stopped working", "zh": "效果变差"},
    "needs_corroboration": {"en": "only a web or public source says so, nobody official agrees yet", "zh": "只有网页或公开来源这样说，还没有官方或公司来源佐证"},
    "injection": {"en": "the text tries to give orders or ask for access", "zh": "文本试图下命令或索要权限"},
    "unknown_action": {"en": "the action is not in the approved catalogue", "zh": "这个操作不在已批准的清单里"},
    "action_device_mismatch": {"en": "the action belongs to another kind of device", "zh": "这个操作属于另一类设备"},
    "no_known_action": {"en": "no known action named", "zh": "没有提到已知操作"},
    "unsupported_source": {"en": "unknown source", "zh": "未知来源"},
    "unknown_app": {"en": "unknown application", "zh": "未知应用"},
    "still_paused": {"en": "stays paused until a person decides", "zh": "保持暂停，等人来决定"},
}
SYMPTOM_EXTRA = {"stuck": ("stuck or not syncing", "卡住或不同步"), "locked": ("locked out", "账号被锁"), "broken": ("crashes or will not open", "崩溃或打不开"),
                 "connect": ("cannot connect", "连不上"), "full": ("mailbox full", "邮箱已满"), "mfa": ("lost MFA device", "MFA 设备丢失"),
                 "expired": ("password expired", "密码过期"), "install": ("needs an install", "需要安装")}
DEVICE_EXTRA = {"account": ("Account", "账号"), "vpn": ("VPN", "VPN"), "email": ("Email", "邮件"), "software": ("Software", "软件")}
EXTRA_PATTERNS = [(r"\b(run|execute|paste)\s+(this\s+|the\s+|these\s+)?(command|script|code|powershell)", "command_text"),
                  (r"(api[_ -]?key|token|secret|passwd|password)\s*[:=]", "credential"),
                  (r"(give|grant|need|request)\s+(me\s+)?(admin|root|full)?\s*(access|permission|rights)", "permission_request")]
REQUIRED = {"source", "ref", "updated_at", "app", "device", "symptom", "text"}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def unsafe(record: Dict[str, Any]) -> Optional[str]:
    text = " ".join(str(record.get(k) or "") for k in ("text", "ref", "action", "device", "symptom"))
    text += " " + " ".join(str(v) for v in (record.get("source_label") or {}).values())
    for pattern, code in EXTRA_PATTERNS:
        if re.search(pattern, text, re.I):
            return code
    return injection_check(text)


class Learning:
    """One engine for both apps. State is in memory unless `state_path` is given (then a runtime folder, never the repo)."""

    def __init__(self, now: Optional[Callable[[], str]] = None, apps: Optional[Dict[str, tuple]] = None) -> None:
        self._now = now or _utc
        self.catalog: Dict[str, Dict[str, Any]] = {}
        for app, (actions, policy) in (apps or APP_FILES).items():
            with open(actions, encoding="utf-8") as a, open(policy, encoding="utf-8") as p:  # read only
                self.catalog[app] = {"actions": json.load(a), "policy": json.load(p)}
        self.methods: Dict[str, Dict[str, Any]] = {}      # "app|device|symptom|action" -> method
        self._fp: Dict[str, str] = {}
        self._weak: Dict[str, List[Dict[str, Any]]] = {}  # held back (Tier C and D) by method key
        self._versions: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []
        self._notices: List[Dict[str, Any]] = []
        self._seen: set = set()
        self._attempts: set = set()
        self.order_log: List[str] = []                    # tier of every record, in the order it was read

    # ------------------------------------------------------------ read-only views (deep copies: history stays immutable)
    versions = property(lambda s: copy.deepcopy(s._versions))
    events = property(lambda s: copy.deepcopy(s._events))
    notices = property(lambda s: copy.deepcopy(s._notices))

    @property
    def held_back(self) -> List[Dict[str, Any]]:
        return copy.deepcopy([w for ws in self._weak.values() for w in ws if not w.get("promoted")])

    def method(self, app: str, device: str, symptom: str, action: str) -> Optional[Dict[str, Any]]:
        return copy.deepcopy(self.methods.get("%s|%s" % (app, method_key(device, symptom, action))))

    # -------------------------------------------------------------------- labels
    def label(self, app: str, key: str) -> Dict[str, str]:
        device, symptom, action = key.split("|", 2)
        acts = self.catalog[app]["actions"]
        dev = DEVICE_LABELS.get(device) or {"en": DEVICE_EXTRA.get(device, (device,) * 2)[0], "zh": DEVICE_EXTRA.get(device, (device,) * 2)[1]}
        sym = SYMPTOM_LABELS.get(symptom) or {"en": SYMPTOM_EXTRA.get(symptom, (symptom,) * 2)[0], "zh": SYMPTOM_EXTRA.get(symptom, (symptom,) * 2)[1]}
        act = acts.get(action, {"en": action, "zh": action})
        return {l: "%s · %s · %s" % (dev[l], sym[l], act[l]) for l in ("en", "zh")}

    # ------------------------------------------------------------- change recording
    def _change(self, app: str, key: str, rec: Dict[str, Any], old: str, new: str, reason: str, method: Dict[str, Any],
                notify: bool = True) -> None:
        ts = self._now()
        tier = SOURCE_TIER[rec["source"]]
        version = {"version": "4.0.%d" % (len(self._versions) + 1), "ts": ts, "app": app, "method": key, "from": old, "to": new,
                   "reason": reason, "tier": tier, "after": copy.deepcopy(method)}
        self._versions.append(version)
        if notify:
            self._notice(app, key, rec, old, new, reason, ts, version["version"])

    def _notice(self, app: str, key: str, rec: Dict[str, Any], old: str, new: str, reason: str, ts: str, version: str) -> None:
        nid = "N-" + _sha(app, key, rec["source"], rec["ref"], old, new, version)[:12]
        if nid in self._seen:
            return
        self._seen.add(nid)
        m = {"en": "no method (text rejected)", "zh": "无方法（文本被拦截）"} if key.endswith("|none") else self.label(app, key)
        src, why = self._source_label(rec), REASON[reason]
        o, n = STATE[old], STATE[new]
        msg = {"en": "[dry run] Source: %s (tier %s). Method: %s. %s -> %s. Why: %s. Nothing was sent or changed in policy."
                     % (src["en"], SOURCE_TIER[rec["source"]], m["en"], o["en"], n["en"], why["en"]),
               "zh": "[演练] 来源：%s（%s 级）。方法：%s。%s → %s。原因：%s。没有发送任何内容，权限文件未改动。"
                     % (src["zh"], SOURCE_TIER[rec["source"]], m["zh"], o["zh"], n["zh"], why["zh"])}
        self._notices.append({"id": nid, "ts": ts, "app": app, "source_label": src, "tier": SOURCE_TIER[rec["source"]], "method": key, "old_state": old,
                              "new_state": new, "reason": reason, "version": version, "dry_run": True, "message": msg})

    def _source_label(self, rec: Dict[str, Any]) -> Dict[str, str]:
        return rec.get("source_label") or {l: "%s · %s" % (SOURCE_LABEL[rec["source"]][l], rec["ref"]) for l in ("en", "zh")}

    def _event(self, rec: Dict[str, Any], status: str, reason: str, methods: List[str]) -> Dict[str, Any]:
        ev = {"id": "EV-" + _sha(rec["source"], rec["ref"], status, reason, methods)[:12], "ts": self._now(), "tier": SOURCE_TIER.get(rec["source"], "?"),
              "source": rec["source"], "ref": rec["ref"], "app": rec.get("app"), "status": status, "reason": reason, "methods": methods,
              "source_label": self._source_label(rec) if rec.get("source") in SOURCE_LABEL else {"en": str(rec.get("source")), "zh": str(rec.get("source"))}}
        self._events.append(ev)
        return copy.deepcopy(ev)

    # ------------------------------------------------------------------- watch one
    def watch(self, rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """None when nothing changed since the last time this source was read. Never raises on bad source data."""
        missing = REQUIRED - set(rec) if isinstance(rec, dict) else REQUIRED
        if missing or not all(isinstance(rec[k], str) and rec[k].strip() for k in REQUIRED):
            return self._reject({"source": "?", "ref": "?"}, "unsupported_source")
        fp = _sha({k: rec.get(k) for k in sorted(REQUIRED | {"action", "vendor_advisory_harmful"})})
        sk = "%s|%s" % (rec["source"], rec["ref"])
        if self._fp.get(sk) == fp:
            return None
        self._fp[sk] = fp
        if rec["source"] not in SOURCE_TIER:
            return self._reject(rec, "unsupported_source")
        if rec["app"] not in self.catalog:
            return self._reject(rec, "unknown_app")
        tier = SOURCE_TIER[rec["source"]]
        self.order_log.append(tier)
        why = unsafe(rec)
        if why:  # recorded, never executed, and it can never change a method
            ev = self._reject(rec, "injection", notice=True)
            ev["detail"] = why
            return ev
        app, acts = rec["app"], self.catalog[rec["app"]]["actions"]
        actions = [rec["action"]] if rec.get("action") else map_actions(rec["text"])
        bad = [a for a in actions if a not in acts]
        if bad:
            return self._reject(rec, "unknown_action")
        if any(acts[a]["device"] != rec["device"] for a in actions):
            return self._reject(rec, "action_device_mismatch")
        if not actions:
            return self._event(rec, "ignored", "no_known_action", [])
        keys, got = [], set()
        for action in actions:
            key = method_key(rec["device"], rec["symptom"], action)
            keys.append(key)
            got.add(self._apply(app, key, rec, tier))
        status = got.pop() if len(got) == 1 else "accepted"
        reason = {"held_back": "needs_corroboration", "corroborated": "source_change"}.get(status, "source_change")
        return self._event(rec, status, reason, keys)

    def _reject(self, rec: Dict[str, Any], reason: str, notice: bool = False) -> Dict[str, Any]:
        ev = self._event(rec, "rejected", reason, [])
        if notice and rec.get("app") in self.catalog:
            self._notice(rec["app"], "%s|%s|%s" % (rec["device"], rec["symptom"], rec.get("action") or "none"), rec, "unseen", "rejected", reason, self._now(), "-")
        return ev

    def _apply(self, app: str, key: str, rec: Dict[str, Any], tier: str) -> str:
        mk = "%s|%s" % (app, key)
        method = self.methods.get(mk)
        old = method["state"] if method else "unseen"
        src = {"source": rec["source"], "ref": rec["ref"], "tier": tier, "weight": WEIGHT[rec["source"]], "label": self._source_label(rec)}
        if tier in ("C", "D"):
            if method and method["state"] != "held_back":  # corroborated by an A or B record: extra evidence, no state change
                method["sources"].append(src)
                method["corroborated_by"] = sorted({s["tier"] for s in method["sources"]})
                return "corroborated"
            pool = [w for w in self._weak.get(mk, []) if (w["source"], w["ref"]) != (rec["source"], rec["ref"])]
            self._weak[mk] = pool + [dict(rec, tier=tier)]
            self.methods.setdefault(mk, self._new(app, key, rec, "held_back"))
            return "held_back"
        harmful = bool(rec.get("vendor_advisory_harmful")) and tier == "A"
        method = method or self._new(app, key, rec, "unseen")
        method["sources"] = [s for s in method["sources"] if (s["source"], s["ref"]) != (rec["source"], rec["ref"])] + [src]
        for weak in self._weak.pop(mk, []):  # a Tier C or D record waited for this
            method["sources"].append({"source": weak["source"], "ref": weak["ref"], "tier": weak["tier"], "weight": WEIGHT[weak["source"]], "label": self._source_label(weak)})
        method["corroborated_by"] = sorted({s["tier"] for s in method["sources"]})
        if method["state"] == "paused":  # only a person widens permission again; learning never does
            self.methods[mk] = method
            return "accepted"
        new = "paused" if harmful else "candidate"
        if old == new == "candidate":
            method.update(attempts=0, successes=0, failures=0, success_rate=None)
        method["state"] = new
        method["policy_effect"] = self.policy_effect(app, rec["device"], key.split("|")[2])
        self.methods[mk] = method
        self._change(app, key, rec, old, new, "advisory_harmful" if harmful else "source_change", method)
        return "accepted"

    def _new(self, app: str, key: str, rec: Dict[str, Any], state: str) -> Dict[str, Any]:
        device, symptom, action = key.split("|", 2)
        return {"app": app, "key": key, "device": device, "symptom": symptom, "action": action, "state": state, "attempts": 0, "successes": 0,
                "failures": 0, "success_rate": None, "sources": [], "corroborated_by": [], "policy_effect": self.policy_effect(app, device, action)}

    def policy_effect(self, app: str, device: str, action: str) -> Dict[str, Any]:
        cat = self.catalog[app]
        physical = bool(cat["actions"][action].get("physical"))
        allowed = action in cat["policy"].get("allow", {}).get(device, [])
        tier = cat["policy"].get("autonomy", {}).get(cat["actions"][action].get("risk"), "approval")
        return {"permission_source": "policy.json", "allowed": allowed, "physical": physical,
                "automatic": bool(allowed and not physical and tier in ("auto", "notify_then_act"))}

    # ----------------------------------------------------------------- one cycle
    def cycle(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Read vendor and official sources first, then company sources, then the web, then public reports."""
        ordered = sorted(records, key=lambda r: TIERS.index(SOURCE_TIER.get(r.get("source"), "D")) if isinstance(r, dict) else 9)
        return [e for e in (self.watch(r) for r in ordered) if e]

    # ------------------------------------------------------------ confirmed outcomes
    def absorb_attempt(self, app: str, attempt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Learn from a delayed re-check. Provisional results (confirmed is not True/False) change nothing.
        Public reports never reach this path; paused methods stay paused."""
        confirmed = attempt.get("confirmed")
        need = ("ts", "device", "symptom", "action")
        if not isinstance(confirmed, bool) or attempt.get("outcome") != "ran" or any(attempt.get(k) is None for k in need):
            return None
        key = method_key(attempt["device"], attempt["symptom"], attempt["action"])
        method = self.methods.get("%s|%s" % (app, key))
        aid = _sha(app, key, attempt.get("target"), attempt["ts"], confirmed, attempt.get("rechecked_at"))
        if not method or method["state"] in ("held_back", "paused") or aid in self._attempts:
            return None
        self._attempts.add(aid)
        old = method["state"]
        method["attempts"] += 1
        method["successes"] += int(confirmed)
        method["failures"] = method["attempts"] - method["successes"]
        method["success_rate"] = round(method["successes"] / method["attempts"], 4)
        rule = self.catalog[app]["policy"].get("evolution", {})
        if method["attempts"] >= rule.get("demote_min_attempts", 3) and method["success_rate"] <= rule.get("demote_max_rate", 0.2):
            new, reason = "paused", "regression"
        elif method["successes"] >= rule.get("promote_min_successes", 2) and method["success_rate"] >= rule.get("promote_min_rate", 0.67):
            new, reason = "promoted", "verified_outcome"
        else:
            new, reason = ("trial" if old == "candidate" else old), "verified_outcome"
        method["state"] = new
        method["policy_effect"] = self.policy_effect(app, method["device"], method["action"])
        rec = {"source": "incident", "ref": "recheck-" + aid[:6], "source_label": {"en": "Confirmed re-check", "zh": "复查确认"}}
        self._change(app, key, rec, old, new, reason, method, notify=new in ("promoted", "paused") and new != old)
        return {"app": app, "method": key, "old_state": old, "new_state": new, "attempts": method["attempts"], "successes": method["successes"]}

    # ------------------------------------------------------------- what plug-ins read
    def view(self, app: str, device: str, symptom: str) -> Dict[str, Any]:
        """hints: adopted methods (never physical). paused: methods to remove from this call's allow-list copy."""
        hints, paused = {}, []
        for method in self.methods.values():
            if method["app"] == app and method["device"] == device and method["symptom"] == symptom:
                if method["state"] == "promoted" and not method["policy_effect"]["physical"]:
                    hints[method["action"]] = method
                elif method["state"] == "paused":
                    paused.append(method["action"])
        return {"hints": hints, "paused": paused}

    def paused_for(self, app: str, device: str) -> List[str]:
        return sorted({m["action"] for m in self.methods.values() if m["app"] == app and m["device"] == device and m["state"] == "paused"})

    def best_tier(self, method: Dict[str, Any]) -> str:
        return min((s["tier"] for s in method["sources"]), default="B")


def load_sources(path: str = SOURCES_FILE) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
