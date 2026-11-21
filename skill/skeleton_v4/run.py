"""One integrated, dry-run cycle for both apps on the shared runtime (SIMULATED data, nothing is sent).

All run data (tickets, attempts, outbox) lives in a temporary folder that is deleted afterwards.
"""
from __future__ import annotations

import copy
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List

import sys

if __package__ in (None, ""):  # direct run: python skill/skeleton_v4/run.py
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    __package__ = "skeleton_v4"

from skeleton_v4 import SKILL  # noqa: E402
import remediate as rm  # noqa: E402
import desk  # noqa: E402

from skeleton_v4 import app_devices, app_servicedesk, learning as L, plugins, skeleton  # noqa: E402
from integration_v31.plugins import GlobalGate  # noqa: E402

REQUESTS_V31 = os.path.join(SKILL, "integration_v31", "requests_v31.json")
DESK_REQUESTS = os.path.join(SKILL, "apps", "servicedesk", "data", "requests.json")
DIRECTORY = os.path.join(SKILL, "apps", "servicedesk", "data", "directory.json")

AV = {"id": "AV-5F-502", "type": "av", "loc": {"en": "Room 5F-502", "zh": "5F-502 会议室"}}
AV_FAULT = {"message": "Teams Rooms cannot join the meeting, panel frozen", "message_zh": "Teams Rooms 无法入会，面板卡死",
            "title": {"en": "Room 5F-502: Teams Rooms cannot join", "zh": "5F-502 会议室：Teams Rooms 无法入会"}, "fixes": ["restart-room-app"]}
AP = {"id": "AP-4F-07", "type": "wifiap", "loc": {"en": "Floor 4 west", "zh": "四楼西侧"}}
AP_FAULT = {"message": "Wi-Fi access point offline, wireless clients on one floor cannot join", "message_zh": "Wi-Fi 接入点离线，一层楼的无线用户连不上",
            "title": {"en": "Floor 4 west: one access point offline", "zh": "四楼西侧：一个无线接入点离线"}, "fixes": ["controller-reboot-ap"]}
OUTLOOK = {"id": "V4-OUTLOOK", "ts": "2026-11-21T09:45:00", "user": "wang", "channel": "Teams", "text": "Outlook is stuck and not syncing my new mail",
           "title": {"en": "Outlook is stuck and not syncing", "zh": "Outlook 卡住，邮件不同步"}, "fixes": ["send-outlook-steps"],
           "confirm": "Mail is syncing again.", "recheck": "healthy"}
FLOOR4 = {"id": "V4-FLOOR4", "ts": "2026-11-21T09:44:00", "user": "lena", "channel": "Teams", "text": "No Wi-Fi on floor 4! Customers arrive soon.",
          "title": {"en": "No Wi-Fi on floor 4", "zh": "四楼没有 Wi-Fi"}}
BOARD = {"sw4": {"upstream": "SW-4F", "status": "open", "our_ticket": "INC0030001", "master": {"number": "INC0030001"},
                 "summary": {"en": "The floor 4 network switch is down; the network team is on it.", "zh": "四楼网络交换机故障，网络组正在处理。"}}}


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def fake_clock(start: str = "2026-11-21T08:30:00"):
    state = {"n": 0}

    def now() -> str:
        state["n"] += 1
        minute = state["n"]
        return "2026-11-21T%02d:%02d:00Z" % (8 + (30 + minute) // 60, (30 + minute) % 60)
    return now


def prime(learning: L.Learning) -> List[Dict[str, Any]]:
    """Earlier confirmed re-checks (simulated), so two vendor-learned methods are adopted before the story starts."""
    out = []
    for app, device, symptom, action in (("servicedesk", "email", "stuck", "send-outlook-steps"), ("devices", "wifiap", "offline", "controller-reboot-ap")):
        for i in (1, 2):
            e = learning.absorb_attempt(app, {"ts": "2026-11-20T10:0%d:00" % i, "device": device, "symptom": symptom, "action": action, "target": "t%d" % i,
                                              "confirmed": True, "outcome": "ran", "rechecked_at": "2026-11-20T10:2%d:00" % i})
            if e:
                out.append(e)
    return out


def build(tmp_root: str = None) -> Dict[str, Any]:
    """Run the whole story. Returns every raw object the tests and the demo writer need."""
    box = {"now": _epoch("2026-11-21T09:25:00")}
    clock = lambda: box["now"]  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="skeleton-v4-", dir=tmp_root) as tmp:
        d1 = app_devices.make_ctx(os.path.join(tmp, "devices"), "en", clock)
        d2 = app_servicedesk.make_ctx(os.path.join(tmp, "servicedesk"), "en", clock)
        office = rm.Ctx(os.path.join(tmp, "office"), "en", live=False, clock=clock, ticket_prefix="INC", ticket_start=10000)
        os.makedirs(office.dir, exist_ok=True)
        rm.save_json(os.path.join(office.dir, "board.json"), BOARD)
        directory = rm.load_json(DIRECTORY, {})
        reqs = {r["id"]: r for r in rm.load_json(REQUESTS_V31, [])}

        learning = L.Learning(now=fake_clock())
        learn_events = learning.cycle(L.load_sources())
        primed = prime(learning)
        gate = GlobalGate()
        gate.advance(3)  # Microsoft Teams confirmed, Cisco looks local

        a1, a2 = app_devices.DevicesAdapter(), app_servicedesk.ServiceDeskAdapter(directory, office)
        p1, p2 = plugins.build(gate, learning, "devices"), plugins.build(gate, learning, "servicedesk")
        rows: List[Dict[str, Any]] = []

        def go(item, adapter, slots, ctx):
            rec = skeleton.run(item, adapter, slots, ctx)
            rows.append({"item": item, "record": rec})
            return rec

        def desk_item(src):
            return dict(copy.deepcopy(src))

        go(desk_item(reqs["V31-01"]), a2, p2, d2)
        go(desk_item(reqs["V31-02"]), a2, p2, d2)
        go(app_devices.item_from(AV, AV_FAULT), a1, p1, d1)
        go(app_devices.item_from(AP, AP_FAULT, "healthy"), a1, p1, d1)
        go(desk_item(reqs["V31-09"]), a2, p2, d2)
        go(desk_item(FLOOR4), a2, p2, d2)

        gate.advance(5)  # the vendor recovers, then the internal sign-ins recover
        box["now"] = _epoch("2026-11-21T09:42:00")
        from integration_v31 import desk_v31
        closures = []
        for ctx in (d2, d1):
            got, msgs = desk_v31.close_vendor_linked(ctx, gate, app="servicedesk" if ctx is d2 else "devices")
            closures += got
            a2.msgs += msgs
        go(desk_item(OUTLOOK), a2, p2, d2)
        sent = desk_v31.send(d2, a2.msgs)

        titles = {r["item"]["id"]: r["record"]["label"] for r in rows}
        for c in closures:
            c["label"] = titles.get(c["id"]) or titles.get(c["id"].split("|")[-1], {"en": c["id"], "zh": c["id"]})
        return {"rows": rows, "items": [r["record"] for r in rows], "closures": closures, "learning": learning, "learn_events": learn_events,
                "primed": primed, "gate": gate, "notifications": sent, "ctx": {"devices": d1, "servicedesk": d2}}


def main() -> None:
    """Print each item's six steps. Dry run on simulated data."""
    import argparse

    parser = argparse.ArgumentParser(description="One dry-run cycle of both apps on the shared six-step runtime.")
    parser.add_argument("--lang", choices=("zh", "en"), default="en")
    args = parser.parse_args()
    out = build()
    print("Incident Skeleton v4 · dry run · simulated data")
    for rec in out["items"]:
        app = "App 1 devices" if rec["app"] == "devices" else "App 2 service desk"
        print("\n[%s] %s -> %s" % (app, rec["label"][args.lang], rec["outcome"]))
        for step in rec["steps"]:
            mark = "-" if step["status"] == "skipped" else ">"
            slot = " [%s]" % step["slot"] if step["slot"] else ""
            print("  %s %-11s%s %s" % (mark, step["name"], slot, step[args.lang]))


if __name__ == "__main__":
    main()
