#!/usr/bin/env python3
"""Incident Skeleton v2 intelligence evolution engine.

The engine is deliberately dry-run only. It learns rankings and lifecycle
state for action ids that already exist; it never adds actions or permissions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REMEDIATION_DIR = os.path.abspath(os.path.join(HERE, "..", "remediation"))
if REMEDIATION_DIR not in sys.path:
    sys.path.insert(0, REMEDIATION_DIR)

# Reuse v1's security and mapping floor instead of maintaining a divergent copy.
from harvest import injection_reason, map_actions  # noqa: E402

SUPPORTED_SOURCES = {
    "servicenow_kb",
    "incident",
    "chat",
    "email",
    "shared_drive",
}
SOURCE_LABELS = {
    "servicenow_kb": {"en": "ServiceNow KB", "zh": "ServiceNow 知识库"},
    "incident": {"en": "resolved incident", "zh": "历史工单"},
    "chat": {"en": "team chat", "zh": "团队聊天"},
    "email": {"en": "email", "zh": "邮件"},
    "shared_drive": {"en": "shared drive", "zh": "共享盘"},
}
DEVICE_LABELS = {
    "printer": {"en": "printer", "zh": "打印机"},
    "signage": {"en": "digital signage", "zh": "数字标牌"},
    "av": {"en": "meeting-room AV", "zh": "会议室音视频"},
    "wifiap": {"en": "wireless AP", "zh": "无线 AP"},
}
SYMPTOM_LABELS = {
    "jam": {"en": "paper jam", "zh": "卡纸"},
    "offline": {"en": "offline", "zh": "离线"},
    "down": {"en": "black or offline", "zh": "黑屏或离线"},
    "hung": {"en": "frozen or cannot join", "zh": "卡死或无法入会"},
    "generic": {"en": "general fault", "zh": "一般故障"},
}
STATE_LABELS = {
    "unseen": {"en": "not seen", "zh": "未见过"},
    "observed": {"en": "observed", "zh": "已发现"},
    "candidate": {"en": "needs verification", "zh": "待验证"},
    "trial": {"en": "being verified", "zh": "验证中"},
    "promoted": {"en": "adopted", "zh": "已采用"},
    "demoted": {"en": "paused", "zh": "已停用"},
    "rejected": {"en": "rejected", "zh": "已拦截"},
}
REQUIRED_SOURCE_FIELDS = {"source", "ref", "updated_at", "device", "symptom", "text"}


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def method_key(device: str, symptom: str, action: str) -> str:
    return "%s|%s|%s" % (device, symptom, action)


class EvolutionEngine:
    """WATCH -> DIFF -> LEARN -> VERIFY -> EVOLVE -> NOTIFY.

    ``state_path`` is optional. When supplied, every accepted change is saved
    as JSON so source fingerprints and notice deduplication survive restarts.
    Public snapshots are deep copies to keep old revisions immutable to callers.
    """

    def __init__(
        self,
        actions_path: Optional[str] = None,
        policy_path: Optional[str] = None,
        state_path: Optional[str] = None,
        now: Optional[Callable[[], str]] = None,
    ) -> None:
        remediation = os.path.abspath(os.path.join(HERE, "..", "remediation"))
        self.actions_path = actions_path or os.path.join(remediation, "actions.json")
        self.policy_path = policy_path or os.path.join(remediation, "policy.json")
        self.actions = _read_json(self.actions_path)
        self.policy = _read_json(self.policy_path)
        self.state_path = state_path
        self._now = now or _utc_now
        self._state = self._blank_state()
        if state_path and os.path.exists(state_path):
            self._load_state(state_path)

    @staticmethod
    def _blank_state() -> Dict[str, Any]:
        return {
            "fingerprints": {},
            "methods": {},
            "versions": [],
            "source_events": [],
            "method_events": [],
            "notices": [],
            "notice_ids": [],
            "attempt_ids": [],
        }

    def _load_state(self, path: str) -> None:
        loaded = _read_json(path)
        state = self._blank_state()
        for name in state:
            if name in loaded and isinstance(loaded[name], type(state[name])):
                state[name] = loaded[name]
        self._state = state

    def _persist(self) -> None:
        if not self.state_path:
            return
        parent = os.path.dirname(os.path.abspath(self.state_path))
        os.makedirs(parent, exist_ok=True)
        temp = self.state_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(temp, self.state_path)

    @property
    def fingerprints(self) -> Dict[str, str]:
        return copy.deepcopy(self._state["fingerprints"])

    @property
    def methods(self) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(self._state["methods"])

    @property
    def versions(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["versions"])

    @property
    def source_events(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["source_events"])

    @property
    def method_events(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["method_events"])

    @property
    def notices(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["notices"])

    @staticmethod
    def fingerprint(record: Dict[str, Any]) -> str:
        material = {key: record.get(key) for key in sorted(REQUIRED_SOURCE_FIELDS)}
        explicit = record.get("action", record.get("action_id"))
        if explicit is not None:
            material["action"] = explicit
        raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_id(*parts: Any) -> str:
        raw = "|".join(str(part) for part in parts)
        return "EV-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _source_key(self, record: Dict[str, Any]) -> str:
        return "%s|%s" % (record["source"], record["ref"])

    def _validate_record(self, record: Dict[str, Any]) -> None:
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(record))
        if missing:
            raise ValueError("source record missing fields: %s" % ", ".join(missing))
        if record["source"] not in SUPPORTED_SOURCES:
            raise ValueError("unsupported source: %s" % record["source"])
        if not all(isinstance(record[name], str) and record[name].strip() for name in REQUIRED_SOURCE_FIELDS):
            raise ValueError("source record fields must be non-empty strings")

    def _policy_effect(self, device: str, action_id: str) -> Dict[str, Any]:
        action = self.actions[action_id]
        allowlisted = action_id in self.policy.get("allow", {}).get(device, [])
        physical = bool(action.get("physical"))
        tier = self.policy.get("autonomy", {}).get(action.get("risk"), "approval")
        automatic = bool(allowlisted and not physical and tier in ("auto", "notify_then_act"))
        if physical:
            en = "Physical action remains human-only; no automatic permission was granted."
            zh = "物理操作仍须人工执行；未授予自动权限。"
        elif not allowlisted:
            en = "Action remains blocked because policy.json does not allow it for this device."
            zh = "policy.json 未允许该设备执行此操作，操作仍被阻止。"
        else:
            tier_zh = {"auto": "可自动执行", "notify_then_act": "先提醒再执行", "approval": "等待人工批准"}.get(tier, tier)
            en = "Existing policy remains at the %s tier; learning granted no permission." % tier
            zh = "权限保持“%s”；学习过程没有增加权限。" % tier_zh
        return {
            "allowed": allowlisted,
            "automatic": automatic,
            "physical": physical,
            "tier": "human" if physical else tier,
            "permission_source": "policy.json",
            "en": en,
            "zh": zh,
        }

    def _append_version(
        self,
        reason: str,
        key: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> Dict[str, Any]:
        revision = {
            "version": "2.0.%d" % (len(self._state["versions"]) + 1),
            "created_at": self._now(),
            "reason": reason,
            "method": key,
            "before": copy.deepcopy(before),
            "after": copy.deepcopy(after),
        }
        self._state["versions"].append(revision)
        return copy.deepcopy(revision)

    def _source_label(self, source: str, lang: str) -> str:
        kind, _, ref = source.partition("|")
        label = SOURCE_LABELS.get(kind, {}).get(lang, kind)
        return "%s · %s" % (label, ref) if ref else label

    def _method_label(self, key: Optional[str], lang: str) -> str:
        if not key:
            return "none" if lang == "en" else "无"
        device, symptom, action = key.split("|", 2)
        action_label = self.actions.get(action, {}).get(lang, action)
        return "%s · %s · %s" % (
            DEVICE_LABELS.get(device, {}).get(lang, device),
            SYMPTOM_LABELS.get(symptom, {}).get(lang, symptom),
            action_label,
        )

    def _notice(
        self,
        event_id: str,
        kind: str,
        source: str,
        key: Optional[str],
        old_state: str,
        new_state: str,
        reason: str,
        policy_effect: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        notice_id = self._event_id("notice", event_id, kind)
        if notice_id in self._state["notice_ids"]:
            return None
        effect = policy_effect or {
            "allowed": False,
            "automatic": False,
            "physical": False,
            "tier": "rejected",
            "permission_source": "policy.json",
            "en": "Rejected source text cannot affect policy or execution.",
            "zh": "被拒绝的来源文本不会影响策略或执行。",
        }
        method_en = self._method_label(key, "en")
        method_zh = self._method_label(key, "zh")
        source_en = self._source_label(source, "en")
        source_zh = self._source_label(source, "zh")
        old_en = STATE_LABELS.get(old_state, {}).get("en", old_state)
        old_zh = STATE_LABELS.get(old_state, {}).get("zh", old_state)
        new_en = STATE_LABELS.get(new_state, {}).get("en", new_state)
        new_zh = STATE_LABELS.get(new_state, {}).get("zh", new_state)
        lead = {
            "candidate_added": {"en": "New method found", "zh": "发现新方法"},
            "candidate_changed": {"en": "Method guidance changed", "zh": "方法内容有更新"},
            "method_promoted": {"en": "Method adopted after verification", "zh": "方法验证通过，已采用"},
            "method_demoted": {"en": "Method paused after regression", "zh": "方法效果变差，已停用"},
            "source_rejected": {"en": "Unsafe source text rejected", "zh": "危险来源内容已拦截"},
        }.get(kind, {"en": kind, "zh": kind})
        en = (
            "[dry run] %s. Source: %s. Method: %s. %s -> %s. %s"
            % (lead["en"], source_en, method_en, old_en, new_en, effect["en"])
        )
        zh = (
            "[演练] %s。来源：%s。方法：%s。%s → %s。%s"
            % (lead["zh"], source_zh, method_zh, old_zh, new_zh, effect["zh"])
        )
        notice = {
            "id": notice_id,
            "event_id": event_id,
            "ts": self._now(),
            "kind": kind,
            "source": source,
            "method": key,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
            "policy_effect": copy.deepcopy(effect),
            "dry_run": True,
            "message": {"en": en, "zh": zh},
        }
        self._state["notice_ids"].append(notice_id)
        self._state["notices"].append(notice)
        return copy.deepcopy(notice)

    def watch(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Watch and learn from one source record.

        Returns ``None`` when its fingerprint has not changed. Rejected source
        text is fingerprinted too, preventing repeated alerts for the same data.
        """
        self._validate_record(record)
        record = copy.deepcopy(record)
        source_key = self._source_key(record)
        fingerprint = self.fingerprint(record)
        previous = self._state["fingerprints"].get(source_key)
        if previous == fingerprint:
            return None

        diff = "discovered" if previous is None else "changed"
        self._state["fingerprints"][source_key] = fingerprint
        event_id = self._event_id("source", source_key, fingerprint)
        base_event = {
            "id": event_id,
            "ts": self._now(),
            "source": record["source"],
            "ref": record["ref"],
            "source_key": source_key,
            "updated_at": record["updated_at"],
            "fingerprint": fingerprint,
            "previous_fingerprint": previous,
            "diff": diff,
        }

        unsafe = injection_reason(record["text"])
        if unsafe:
            event = dict(base_event, status="rejected", reason=unsafe, methods=[])
            self._state["source_events"].append(event)
            self._notice(event_id, "source_rejected", source_key, None, "unseen", "rejected", unsafe, None)
            self._persist()
            return copy.deepcopy(event)

        explicit = record.get("action", record.get("action_id"))
        actions = [explicit] if explicit else map_actions(record["text"])
        unknown = [action for action in actions if action not in self.actions]
        mismatched = [
            action for action in actions
            if action in self.actions and self.actions[action].get("device") != record["device"]
        ]
        if unknown or mismatched:
            reason = "unknown_action" if unknown else "action_device_mismatch"
            event = dict(
                base_event,
                status="rejected",
                reason=reason,
                rejected_actions=unknown + mismatched,
                methods=[],
            )
            self._state["source_events"].append(event)
            self._persist()
            return copy.deepcopy(event)

        known = [action for action in actions if action in self.actions]
        if not known:
            event = dict(base_event, status="ignored", reason="no_known_action", methods=[])
            self._state["source_events"].append(event)
            self._persist()
            return copy.deepcopy(event)

        learned = []
        for action_id in known:
            key = method_key(record["device"], record["symptom"], action_id)
            old = copy.deepcopy(self._state["methods"].get(key, {}))
            old_state = old.get("state", "observed")
            method = copy.deepcopy(old) if old else {
                "key": key,
                "device": record["device"],
                "symptom": record["symptom"],
                "action": action_id,
                "state": "observed",
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "success_rate": None,
                "sources": [],
                "lifecycle": ["observed"],
            }
            source_info = {
                "source": record["source"],
                "ref": record["ref"],
                "updated_at": record["updated_at"],
                "fingerprint": fingerprint,
            }
            method["sources"] = [
                item for item in method["sources"]
                if not (item["source"] == record["source"] and item["ref"] == record["ref"])
            ]
            method["sources"].append(source_info)
            if diff == "changed":
                method.update(attempts=0, successes=0, failures=0, success_rate=None)
            method["state"] = "candidate"
            if not method["lifecycle"] or method["lifecycle"][-1] != "candidate":
                method["lifecycle"].append("candidate")
            method["policy_effect"] = self._policy_effect(record["device"], action_id)
            method["updated_at"] = self._now()
            self._state["methods"][key] = method
            transition = {
                "id": self._event_id("method", event_id, key),
                "ts": self._now(),
                "source_event_id": event_id,
                "source": source_key,
                "method": key,
                "old_state": old_state,
                "new_state": "candidate",
                "reason": "source_change",
            }
            self._state["method_events"].append(transition)
            self._append_version("source_change", key, old, method)
            self._notice(
                event_id,
                "candidate_changed" if diff == "changed" else "candidate_added",
                source_key,
                key,
                old_state,
                "candidate",
                "source_change",
                method["policy_effect"],
            )
            learned.append(key)

        event = dict(base_event, status="accepted", reason="source_change", methods=learned)
        self._state["source_events"].append(event)
        self._persist()
        return copy.deepcopy(event)

    def watch_many(self, records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [event for event in (self.watch(record) for record in records) if event is not None]

    def absorb_attempt(self, attempt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Learn once from a delayed re-check produced by the v1 repair loop.

        Only attempts with an explicit boolean ``confirmed`` value count. A
        provisional result, a self-heal, or an unknown method changes nothing.
        """
        confirmed = attempt.get("confirmed")
        if not isinstance(confirmed, bool) or attempt.get("outcome") != "ran":
            return None
        required = ("ts", "device", "symptom", "action")
        if not all(attempt.get(name) is not None for name in required):
            return None
        key = method_key(attempt["device"], attempt["symptom"], attempt["action"])
        if key not in self._state["methods"]:
            return None
        material = {name: attempt.get(name) for name in required + ("target", "confirmed", "rechecked_at")}
        attempt_id = self._event_id("attempt", json.dumps(material, ensure_ascii=False, sort_keys=True))
        if attempt_id in self._state["attempt_ids"]:
            return None
        self._state["attempt_ids"].append(attempt_id)
        event = self.verify(key, confirmed, source="remediation_recheck")
        event["attempt_id"] = attempt_id
        return event

    def verify(
        self,
        key: str,
        succeeded: bool,
        source: str = "dry_run_verifier",
    ) -> Dict[str, Any]:
        """Record one dry-run outcome, append a revision, and evolve state."""
        if key not in self._state["methods"]:
            raise KeyError("unknown method: %s" % key)
        method = copy.deepcopy(self._state["methods"][key])
        before = copy.deepcopy(method)
        old_state = method["state"]
        method["attempts"] += 1
        method["successes"] += int(bool(succeeded))
        method["failures"] = method["attempts"] - method["successes"]
        method["success_rate"] = round(method["successes"] / method["attempts"], 4)

        evolution = self.policy.get("evolution", {})
        demote = (
            method["attempts"] >= evolution.get("demote_min_attempts", 3)
            and method["success_rate"] <= evolution.get("demote_max_rate", 0.2)
        )
        promote = (
            method["successes"] >= evolution.get("promote_min_successes", 2)
            and method["success_rate"] >= evolution.get("promote_min_rate", 0.67)
        )
        if demote:
            new_state = "demoted"
        elif promote:
            new_state = "promoted"
        elif old_state in ("promoted", "demoted"):
            new_state = old_state
        else:
            new_state = "trial"
        method["state"] = new_state
        if not method["lifecycle"] or method["lifecycle"][-1] != new_state:
            method["lifecycle"].append(new_state)
        method["updated_at"] = self._now()
        # Recompute from actions + policy on every revision. Learned state cannot
        # turn a physical action into an automatic one.
        method["policy_effect"] = self._policy_effect(method["device"], method["action"])
        self._state["methods"][key] = method

        reason = "regression" if new_state == "demoted" and old_state != "demoted" else "verified_outcome"
        event_id = self._event_id("verify", key, method["attempts"], self._now(), succeeded)
        event = {
            "id": event_id,
            "ts": self._now(),
            "source": source,
            "method": key,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
            "succeeded": bool(succeeded),
            "attempts": method["attempts"],
            "successes": method["successes"],
            "success_rate": method["success_rate"],
            "dry_run": True,
        }
        self._state["method_events"].append(event)
        self._append_version(reason, key, before, method)
        if new_state in ("promoted", "demoted") and new_state != old_state:
            self._notice(
                event_id,
                "method_%s" % new_state,
                source,
                key,
                old_state,
                new_state,
                reason,
                method["policy_effect"],
            )
        self._persist()
        return copy.deepcopy(event)

    def current(self) -> Dict[str, Any]:
        methods = list(self._state["methods"].values())
        promoted = sum(method["state"] == "promoted" for method in methods)
        demoted = sum(method["state"] == "demoted" for method in methods)
        pending = sum(method["state"] in ("observed", "candidate", "trial") for method in methods)
        decided = promoted + demoted
        evidenced = sum(method["attempts"] > 0 for method in methods)
        source_coverage = 25.0 * min(1.0, len(self._state["fingerprints"]) / 5.0)
        evidence_coverage = 25.0 * evidenced / len(methods) if methods else 0.0
        decision_coverage = 30.0 * decided / len(methods) if methods else 0.0
        version_depth = 20.0 * min(1.0, len(self._state["versions"]) / 10.0)
        # Intelligence means governed learning progress, not a high raw repair
        # success rate. Discovering and demoting a bad method is useful learning.
        score = round(source_coverage + evidence_coverage + decision_coverage + version_depth)
        return {
            "intelligence_score": max(0, min(100, score)),
            "strategy_version": self._state["versions"][-1]["version"] if self._state["versions"] else "2.0.0",
            "watched_sources": len(self._state["fingerprints"]),
            "known_methods": len(methods),
            "promoted": promoted,
            "demoted": demoted,
            "pending": pending,
        }

    def export_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)
