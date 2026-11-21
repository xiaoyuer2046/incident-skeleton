"""v5 permission growth: learning may PROPOSE more authority; only a named person grants it.

* Narrowing stays automatic (v4: a paused method is removed from the in-memory allow-list).
* Widening is one step only: an action that needs approval each time may get a STANDING APPROVAL for one app, one crew and
  one symptom, when the learning record shows enough confirmed successes. It expires after `grant_days`.
* Never widened: physical actions, actions in `never_widen` (identity and access), and anything not already in the allow-list.
* The approver must be listed for that crew (policy.json chatops.approvers, or rules_v5.json for an app without one).
* Every proposal, decision and revoke appends a version. Nothing here writes policy.json, actions.json or approvals.json:
  a grant becomes the `approvals` map the v1 repair loop already accepts, for one call.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

STATES = {"pending": {"en": "waiting for a person", "zh": "等人决定"}, "approved": {"en": "approved", "zh": "已批准"},
          "declined": {"en": "declined", "zh": "已拒绝"}, "refused": {"en": "refused by rule", "zh": "规则不允许"},
          "revoked": {"en": "revoked", "zh": "已撤回"}}
WHY = {"never_widen": {"en": "identity and access actions are never widened", "zh": "身份和访问权限类操作永远不放宽"},
       "physical": {"en": "on-site work always goes to a person", "zh": "现场操作永远交给人"},
       "not_an_approver": {"en": "this person is not an approver for this crew", "zh": "这个人不是这个班组的审批人"},
       "not_pending": {"en": "this proposal is not waiting for a decision", "zh": "这条提议不在等待决定"}}


def _sha(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


class PermissionBook:
    def __init__(self, learning: Any, rules: Dict[str, Any], now: Callable[[], str]) -> None:
        self.learning, self.rule, self._now = learning, rules["permission_evolution"], now
        self.proposals: Dict[str, Dict[str, Any]] = {}
        self._versions: List[Dict[str, Any]] = []
        self.attempts: List[Dict[str, Any]] = []  # decisions that were refused (wrong person, wrong state)

    versions = property(lambda s: copy.deepcopy(s._versions))

    def approvers(self, app: str, crew: str) -> List[str]:
        pol = self.learning.catalog[app]["policy"].get("chatops", {}).get("approvers")
        book = pol if pol else self.rule.get("approvers", {}).get(app, {})
        return list(book.get(crew, [])) + list(book.get("*", []))

    def tier(self, app: str, action: str) -> str:
        cat = self.learning.catalog[app]
        return cat["policy"].get("autonomy", {}).get(cat["actions"][action]["risk"], "approval")

    def _version(self, p: Dict[str, Any], change: str, who: Optional[str] = None) -> None:
        self._versions.append({"version": "5.0.%d" % (len(self._versions) + 1), "ts": self._now(), "proposal": p["id"], "change": change,
                               "by": who or "learning", "after": copy.deepcopy(p)})

    def propose(self) -> List[Dict[str, Any]]:
        """Look at adopted methods and propose a standing approval where the evidence is strong enough."""
        out = []
        for m in self.learning.methods.values():
            app, aid = m["app"], m["action"]
            act = self.learning.catalog[app]["actions"][aid]
            if m["state"] != "promoted" or not m["policy_effect"]["allowed"] or self.tier(app, aid) != "approval":
                continue
            pid = "PG-" + _sha(app, m["key"])[:6]
            if pid in self.proposals:
                continue
            blocked = "physical" if act.get("physical") else ("never_widen" if aid in self.rule["never_widen"] else None)
            enough = m["successes"] >= self.rule["min_successes"] and (m["success_rate"] or 0) >= self.rule["min_rate"]
            if not (enough or blocked):
                continue
            p = {"id": pid, "app": app, "crew": m["device"], "symptom": m["symptom"], "action": aid, "label": {"en": act["en"], "zh": act["zh"]},
                 "from": {"en": "approval each time", "zh": "每次都要批准"}, "to": {"en": "standing approval", "zh": "长期授权"}, "evidence": {"successes": m["successes"], "attempts": m["attempts"], "rate": m["success_rate"]},
                 "sources": [s["label"] for s in m["sources"]], "days": self.rule["grant_days"], "state": "refused" if blocked else "pending",
                 "reason": blocked, "approver": None, "decided_at": None, "expires_at": None, "dry_run": True}
            self.proposals[pid] = p
            self._version(p, "refused" if blocked else "proposed")
            out.append(copy.deepcopy(p))
        return out

    def decide(self, pid: str, person: str, approve: bool = True) -> Dict[str, Any]:
        p = self.proposals[pid]
        why = "not_pending" if p["state"] != "pending" else ("not_an_approver" if person not in self.approvers(p["app"], p["crew"]) else None)
        if why:
            self.attempts.append({"ts": self._now(), "proposal": pid, "by": person, "refused": why})
            return {"ok": False, "why": why, "text": dict(WHY[why])}
        now = self._now()
        p.update(state="approved" if approve else "declined", approver=person, decided_at=now)
        if approve:
            p["expires_at"] = (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(days=p["days"])).isoformat().replace("+00:00", "Z")
        self._version(p, p["state"], person)
        return {"ok": True, "state": p["state"]}

    def revoke(self, pid: str, person: str) -> Dict[str, Any]:
        p = self.proposals[pid]
        if person not in self.approvers(p["app"], p["crew"]):
            self.attempts.append({"ts": self._now(), "proposal": pid, "by": person, "refused": "not_an_approver"})
            return {"ok": False, "why": "not_an_approver"}
        p["state"] = "revoked"
        self._version(p, "revoked", person)
        return {"ok": True, "state": "revoked"}

    def standing(self, app: str, crew: str, symptom: str) -> Dict[str, str]:
        """The approvals map for one repair call: only approved, unexpired grants for exactly this app, crew and symptom."""
        now = self._now()
        return {p["action"]: "standing approval %s by %s" % (p["id"], p["approver"]) for p in self.proposals.values()
                if p["state"] == "approved" and (p["app"], p["crew"], p["symptom"]) == (app, crew, symptom) and now < p["expires_at"]}
