#!/usr/bin/env python3
"""Write demo/data/skeleton-v4.js (window.SKELETON_V4) from one real run of the shared runtime. SIMULATED, DRY-RUN.

    python skill/skeleton_v4/simulate.py [--output demo/data/skeleton-v4.js]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

if __package__ in (None, ""):  # direct run
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    __package__ = "skeleton_v4"

from skeleton_v4 import ROOT, learning as L, run, skeleton  # noqa: E402
from skeleton_v4.app_devices import CREWS as DEVICE_CREWS  # noqa: E402
from skeleton_v4.app_servicedesk import CREWS as DESK_CREWS  # noqa: E402

DEFAULT_OUTPUT = os.path.join(ROOT, "demo", "data", "skeleton-v4.js")
RUNTIME_FILE = "skill/skeleton_v4/skeleton.py"
GENERATED_AT = "2026-11-21T09:50:00Z"
TIER_SOURCES = {t: [L.SOURCE_LABEL[s] for s, tier in L.SOURCE_TIER.items() if tier == t] for t in L.TIERS}
REASON_OK = {k: v for k, v in L.REASON.items()}


def runtime_lines() -> int:
    with open(skeleton.__file__, encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _method_label(lg: L.Learning, app: str, key: str) -> Dict[str, str]:
    return {"en": "no method", "zh": "无方法"} if key.endswith("|none") else lg.label(app, key)


def learning_block(lg: L.Learning) -> Dict[str, Any]:
    events = [{"ts": n["ts"], "tier": n["tier"], "source_label": n["source_label"], "method_label": _method_label(lg, n["app"], n["method"]),
               "from": L.STATE[n["old_state"]], "to": L.STATE[n["new_state"]], "reason_label": L.REASON[n["reason"]],
               "en": n["message"]["en"], "zh": n["message"]["zh"]} for n in lg.notices]
    versions = [{"version": v["version"], "ts": v["ts"], "method_label": lg.label(v["app"], v["method"]), "from": L.STATE[v["from"]], "to": L.STATE[v["to"]]}
                for v in lg.versions]
    rejected = [{"tier": e["tier"], "source_label": e["source_label"], "reason_label": L.REASON[e["reason"]]} for e in lg.events if e["status"] == "rejected"]
    held = [{"tier": w["tier"], "source_label": w["source_label"], "method_label": lg.label(w["app"], "%s|%s|%s" % (w["device"], w["symptom"], w["action"]))}
            for w in lg.held_back]
    tiers = [{"tier": t, "label": L.TIER_LABEL[t], "sources": TIER_SOURCES[t],
              "weight": max(w for s, w in L.WEIGHT.items() if L.SOURCE_TIER[s] == t)} for t in L.TIERS]
    return {"order": list(L.TIERS), "tiers": tiers, "events": events, "versions": versions, "rejected": rejected, "held_back": held}


def summarize(items: List[Dict[str, Any]], learning: Dict[str, Any], lg: L.Learning) -> Dict[str, Any]:
    states = [m["state"] for m in lg.methods.values()]
    return {"items": len(items), "apps": 2, "slots": len(skeleton.SLOTS),
            "vendor_linked": sum(1 for i in items if i["outcome"] == "linked_vendor"),
            "held_actions": sum(len(i["held_actions"]) for i in items),
            "learned": sum(1 for s in states if s in ("candidate", "trial", "promoted")), "paused": states.count("paused"),
            "rejected": len(learning["rejected"]), "held_back": len(learning["held_back"])}


def build() -> Dict[str, Any]:
    out = run.build()
    lg = out["learning"]
    block = learning_block(lg)
    items = out["items"]
    for item in items:
        for s in item["steps"]:
            s["en"] = re.sub(r"INC\d+", "the ticket", re.sub(r"Ticket INC\d+", "The ticket", s["en"]))
            s["zh"] = re.sub(r"INC\d+", "该工单", re.sub(r"工单 INC\d+", "该工单", s["zh"]))
    data = {
        "version": "4.0", "generated_at": GENERATED_AT, "dry_run": True, "simulated": True,
        "label": {"en": "SIMULATED DATA - DRY-RUN", "zh": "模拟数据 - 演练模式"},
        "runtime": {"file": RUNTIME_FILE, "steps": list(skeleton.STEPS), "slots": list(skeleton.SLOTS), "lines": runtime_lines()},
        "apps": [{"id": "devices", "label": {"en": "Office devices", "zh": "办公设备"}, "crews": [{"id": k, **v} for k, v in DEVICE_CREWS.items()]},
                 {"id": "servicedesk", "label": {"en": "Service desk", "zh": "服务台"}, "crews": [{"id": k, **v} for k, v in DESK_CREWS.items()]}],
        "learning": block,
        "items": items,
        "closures": [{"label": c["label"], "parent": c["parent"], "en": re.sub(r"INC\d+", "the request", c["reply"]["en"]), "zh": re.sub(r"INC\d+", "该请求", c["reply"]["zh"])} for c in out["closures"]],
        "summary": summarize(items, block, lg),
    }
    validate(data)
    return data


def validate(data: Dict[str, Any]) -> None:
    """The page contract from design section 6 and the record contract from section 3."""
    assert data["version"] == "4.0" and data["dry_run"] is True and data["simulated"] is True
    assert data["runtime"]["steps"] == list(skeleton.STEPS) and data["runtime"]["slots"] == list(skeleton.SLOTS)
    assert set(data["summary"]) == {"items", "apps", "slots", "vendor_linked", "held_actions", "learned", "paused", "rejected", "held_back"}
    assert data["learning"]["order"] == ["A", "B", "C", "D"]
    for item in data["items"]:
        assert set(item) == {"app", "label", "outcome", "crew", "steps", "held_actions", "parent", "learning_used", "dry_run"}
        assert item["app"] in ("devices", "servicedesk") and item["dry_run"] is True and item["outcome"] in skeleton.OUTCOMES
        assert [s["name"] for s in item["steps"]] == list(skeleton.STEPS)
        for s in item["steps"]:
            assert set(s) == {"name", "kind", "status", "slot", "en", "zh"} and s["status"] in ("done", "skipped") and s["slot"] in (None,) + skeleton.SLOTS
            assert s["en"] and s["zh"]
    for c in data["closures"]:
        assert "DRY-RUN" in c["en"] and "演练" in c["zh"]


def write_demo(data: Dict[str, Any], path: str = DEFAULT_OUTPUT) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("// Generated by skill/skeleton_v4/simulate.py. SIMULATED, DRY-RUN.\n")
        handle.write("window.SKELETON_V4 = ")
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write(";\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    data = build()
    write_demo(data, args.output)
    print("wrote %s (%d items, %d closures)" % (args.output, len(data["items"]), len(data["closures"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
