#!/usr/bin/env python3
"""Generate the v3.1 integrated demo (SIMULATED, DRY-RUN) by running the real wrappers.

All run data (tickets, attempts, outbox) lives in a temporary directory that is deleted afterwards.
Nothing is written into v1 data folders, policy.json or app.json.

    python skill/integration_v31/simulate.py [--output demo/data/integrated-v31.js]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from typing import Any, Dict

if __package__ in (None, ""):  # direct run
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    __package__ = "integration_v31"

from integration_v31 import STATES, desk_v31, devices_v31, plugins  # noqa: E402
from integration_v31.plugins import rm, method_key  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUTPUT = os.path.join(ROOT, "demo", "data", "integrated-v31.js")
REQUESTS = os.path.join(HERE, "requests_v31.json")
GENERATED_AT = "2026-11-21T09:42:00Z"

DEVICES = [
    ({"id": "AV-5F-502", "type": "av", "loc": {"en": "Room 5F-502", "zh": "5F-502 会议室"}},
     {"message": "Teams Rooms cannot join the meeting, panel frozen", "message_zh": "Teams Rooms 无法入会，面板卡死",
      "title": {"en": "Room 5F-502: Teams Rooms cannot join", "zh": "5F-502 会议室：Teams Rooms 无法入会"}, "fixes": ["restart-room-app"]}, None),
    ({"id": "AP-4F-07", "type": "wifiap", "loc": {"en": "Floor 4 west", "zh": "四楼西侧"}},
     {"message": "Wi-Fi access point offline, wireless clients on one floor cannot join", "message_zh": "Wi-Fi 接入点离线，一层楼的无线用户连不上",
      "title": {"en": "Floor 4 west: one access point offline", "zh": "四楼西侧：一个无线接入点离线"}, "fixes": ["poe-cycle"]}, "healthy"),
    ({"id": "SIG-LOBBY-E", "type": "signage", "loc": {"en": "Lobby east", "zh": "大厅东侧"}},
     {"message": "Signage black screen, not updating", "message_zh": "数字标牌黑屏，不更新",
      "title": {"en": "Lobby east: signage black screen", "zh": "大厅东侧：数字标牌黑屏"}, "fixes": ["clear-player-cache"]}, "healthy"),
]


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def prime_v2(evo) -> None:
    """Earlier verified outcomes, so v2 already adopts two methods before the story starts."""
    for key in (method_key("signage", "down", "clear-player-cache"), method_key("wifiap", "offline", "poe-cycle")):
        evo.verify(key, True)
        evo.verify(key, True)


def summarize(items, closures) -> Dict[str, Any]:
    return {
        "apps": 2,
        "plugins": ["v2", "v3"],
        "items": len(items),
        "vendor_linked": sum(1 for i in items if i["outcome"] == "linked_vendor"),
        "held_actions": sum(len(i["held_actions"]) for i in items),
        "v2_ranked": sum(1 for i in items if any(s["name"] == "MITIGATE" and s["plugin"] == "v2" for s in i["states"])),
        "rejected": sum(1 for i in items if i["outcome"] == "rejected"),
    }


def validate_demo(data: Dict[str, Any]) -> None:
    """The page contract from SPEC section 8 and the record contract from section 6."""
    assert data["version"] == "3.1" and isinstance(data["generated_at"], str)
    assert data["dry_run"] is True and data["simulated"] is True
    assert set(data["summary"]) == {"apps", "plugins", "items", "vendor_linked", "held_actions", "v2_ranked", "rejected"}
    assert data["skeleton"] == STATES
    assert data["summary"] == summarize(data["items"], data["closures"])
    for item in data["items"]:
        assert set(item) >= {"app", "id", "title", "outcome", "states", "held_actions", "parent", "dry_run"}
        assert item["app"] in ("devices", "servicedesk") and item["dry_run"] is True
        assert item["outcome"] in ("linked_vendor", "linked_known", "resolved", "escalated", "rejected", "on_hold", "local_repair")
        assert [s["name"] for s in item["states"]] == STATES
        for s in item["states"]:
            assert set(s) == {"name", "kind", "plugin", "en", "zh"} and s["plugin"] in (None, "v2", "v3")
            assert s["en"] and s["zh"]
    for c in data["closures"]:
        assert c["dry_run"] is True and c["reply"]["en"] and c["reply"]["zh"] and "DRY-RUN" in c["reply"]["en"] and "演练" in c["reply"]["zh"]


def build() -> Dict[str, Any]:
    box = {"now": _epoch("2026-11-21T09:25:00")}
    clock = lambda: box["now"]  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="v31-") as tmp:
        d2 = desk_v31.ctx_for(os.path.join(tmp, "servicedesk"), "en", clock=clock)
        d1 = devices_v31.ctx_for(os.path.join(tmp, "devices"), "en", clock=clock)
        directory = rm.load_json(os.path.join(plugins.APP, "data", "directory.json"), {})
        gate = plugins.GlobalGate()
        gate.advance(3)  # 09:00, 09:10, 09:20: the Microsoft incident is confirmed, Cisco looks local
        evo = plugins.new_evolution()
        prime_v2(evo)

        reqs = {r["id"]: r for r in rm.load_json(REQUESTS, [])}
        items, msgs = [], []

        def app2(rid):
            rec, m = desk_v31.handle(d2, None, reqs[rid], directory, gate)
            items.append(rec)
            msgs.extend(m)

        for rid in ("V31-01", "V31-02", "V31-03"):
            app2(rid)
        dev_ctx = {}
        for dev, fault, recheck in DEVICES:
            items.append(devices_v31.handle(d1, dev, fault, gate, evo, recheck))
        app2("V31-09")

        # the vendor recovers; internal sign-ins recover; linked items close
        gate.advance(5)
        box["now"] = _epoch("2026-11-21T09:42:00")
        c2, m2 = desk_v31.close_vendor_linked(d2, gate)
        c1, m1 = devices_v31.close_vendor_linked(d1, gate)
        closures = c2 + c1
        desk_v31.send(d2, msgs + m2 + m1)

        data = {
            "version": "3.1", "generated_at": GENERATED_AT, "dry_run": True, "simulated": True,
            "label": {"en": "SIMULATED DATA - DRY-RUN", "zh": "模拟数据 - 演练模式"},
            "summary": summarize(items, closures),
            "skeleton": list(STATES),
            "items": items, "closures": closures,
        }
    validate_demo(data)
    return data


def write_demo(data: Dict[str, Any], path: str = DEFAULT_OUTPUT) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("// Generated by skill/integration_v31/simulate.py. SIMULATED, DRY-RUN.\n")
        handle.write("window.INTEGRATED_V31 = ")
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
