"""v5 access layer: each managed system (ServiceNow, AP controller, room manager, signage CMS, print manager) is a connector.

A connector declares its scopes and the NAME of the environment variable that would hold its secret. A new system is one
more entry in connectors_v5.json; no code changes. Every connector here is SIMULATED: it returns the sample open items
from the JSON file and never calls a network. The dry run never reads a secret.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import HERE
from integration_v31.plugins import LABELS, detect_service  # noqa: E402

CONNECTORS_FILE = os.path.join(HERE, "connectors_v5.json")
HEALTH = {"ok": {"en": "connected", "zh": "已连接"}, "timeout": {"en": "not answering", "zh": "没有响应"},
          "auth_failed": {"en": "sign-in refused", "zh": "认证失败"}}


def _t(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class Connector:
    """One managed system. Simulated: `pull` returns the sample items when the system is healthy."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.id, self.kind, self.label = cfg["id"], cfg["kind"], cfg["label"]

    def health(self) -> Dict[str, Any]:
        status = self.cfg.get("health", "ok")
        return {"id": self.id, "label": self.label, "kind": self.kind, "status": status, "text": HEALTH.get(status, HEALTH["timeout"]),
                "scopes": list(self.cfg.get("scopes", [])), "secret_env": self.cfg.get("secret_env"), "secret_read": False}

    def pull(self) -> List[Dict[str, Any]]:
        if self.cfg.get("health", "ok") != "ok":
            return []
        out = []
        for row in self.cfg.get("open", []):
            found = detect_service(row["text"])
            out.append({"id": row["id"], "system": self.id, "system_label": self.label, "kind": self.kind, "site": row.get("site"),
                        "opened_at": row["opened_at"], "ci": row.get("ci"), "text": row["text"], "text_zh": row.get("text_zh") or row["text"],
                        "service": "%s|%s" % found if found else None})
        return out


class Registry:
    def __init__(self, path: str = CONNECTORS_FILE, extra: Optional[List[Dict[str, Any]]] = None) -> None:
        with open(path, encoding="utf-8") as handle:
            systems = json.load(handle)["systems"]
        self.connectors = [Connector(c) for c in systems + list(extra or [])]

    def health(self) -> List[Dict[str, Any]]:
        return [c.health() for c in self.connectors]

    def sync(self) -> List[Dict[str, Any]]:
        """Every open item from every healthy system, oldest first."""
        return sorted((t for c in self.connectors for t in c.pull()), key=lambda t: t["opened_at"])


def merge(tickets: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Group items about the same service (seen in at least `min_systems` systems) or the same device (any systems)."""
    win, min_sys = timedelta(minutes=rules["merge"]["window_minutes"]), rules["merge"]["min_systems"]
    buckets: Dict[tuple, List[Dict[str, Any]]] = {}
    for t in sorted(tickets, key=lambda t: t["opened_at"]):
        key = ("service", t["service"]) if t["service"] else (("device", t["ci"]) if t.get("ci") else None)
        if key:
            buckets.setdefault(key, []).append(t)
    groups = []
    for (kind, value), rows in buckets.items():
        first = _t(rows[0]["opened_at"])
        rows = [t for t in rows if _t(t["opened_at"]) - first <= win]
        systems = sorted({t["system"] for t in rows})
        if len(rows) < 2 or (kind == "service" and len(systems) < min_sys):
            continue
        label = dict(LABELS[tuple(value.split("|"))]) if kind == "service" else {"en": value, "zh": value}
        pid = "MERGE-" + hashlib.sha256(json.dumps([kind, value, rows[0]["id"]]).encode()).hexdigest()[:8]
        groups.append({"parent": pid, "kind": kind, "key": value, "label": label, "children": [t["id"] for t in rows],
                       "systems": systems, "sites": sorted({t["site"] for t in rows if t.get("site")}), "first_at": rows[0]["opened_at"],
                       "dry_run": True})
    return sorted(groups, key=lambda g: g["first_at"])
