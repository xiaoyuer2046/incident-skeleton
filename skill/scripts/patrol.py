#!/usr/bin/env python3
"""Patrol — four crews watch four device types at the same time.

Each crew probes its own device in parallel. A single failed probe is a blip
and is ignored. Only a device that fails at least --need of --rounds probes is
CONFIRMED, and only then does the skeleton (run_incident.py) walk the alert and
write a postmortem. This is roadmap step 1 (threshold-gated detect & alert).

Read-only: it only pings / curls. Safe public sample targets are built in.

Usage:
  python3 patrol.py                       # 4 sample devices, 3 rounds, need 2 fails
  python3 patrol.py --rounds 5 --need 3
"""
import argparse, os, sys, time, argparse as _ap
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_incident as ri

# one sample device per crew. 192.0.2.1 is a reserved test address: it never answers.
DEVICES = [
    {"type": "printer", "target": "1.1.1.1",          "source": "SNMP 10.0.4.21",       "message": "patrol: printer unreachable"},
    {"type": "signage", "target": "https://example.com", "source": "CMS / 大厅东",       "message": "patrol: signage player offline"},
    {"type": "av",      "target": "192.0.2.1",        "source": "Zoom Rooms / 3F-301", "message": "patrol: meeting room controller offline"},
    {"type": "wifiap",  "target": "1.1.1.1",          "source": "控制器 / 楼层3",        "message": "patrol: AP offline, clients dropping"},
]


def probe_once(dev):
    t = dev["target"]
    if ri.is_url(t):
        ok, txt = ri.curl(t)
        ok = ok and txt.startswith("HTTP") and txt.split()[1][:1] in ("2", "3")
        return ok, txt
    return ri.ping(t)


def watch(dev, rounds, interval):
    history = []
    for i in range(rounds):
        ok, txt = probe_once(dev)
        history.append(ok)
        if i < rounds - 1:
            time.sleep(interval)
    return history


def main():
    ap = _ap.ArgumentParser(description="Four crews patrol at the same time")
    ap.add_argument("--rounds", type=int, default=3, help="probes per device")
    ap.add_argument("--need", type=int, default=2, help="failed probes needed to confirm an alert")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between probes")
    args = ap.parse_args()

    print(f"\n  🔭 四个代理同时巡检：每台探测 {args.rounds} 次，失败 ≥ {args.need} 次才算确认\n")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(DEVICES)) as pool:
        futs = {d["type"]: pool.submit(watch, d, args.rounds, args.interval) for d in DEVICES}
        results = {k: f.result() for k, f in futs.items()}
    elapsed = time.time() - t0

    confirmed = []
    print(f"  {'班底':<10}{'探测':<16}{'失败':<6}结论")
    print("  " + "─" * 50)
    for d in DEVICES:
        h = results[d["type"]]
        fails = h.count(False)
        marks = " ".join("✓" if x else "✗" for x in h)
        label = ri.CREW[d["type"]]["icon"] + " " + ri.CREW[d["type"]]["label"]
        if fails >= args.need:
            verdict = "🔴 确认故障 → 交给骨架"
            confirmed.append(d)
        elif fails > 0:
            verdict = "🟡 偶发抖动，忽略（不开单）"
        else:
            verdict = "🟢 正常"
        print(f"  {label:<12}{marks:<16}{fails:<6}{verdict}")
    print(f"\n  四台并行巡检用时 {elapsed:.1f} 秒\n")

    if not confirmed:
        print("  没有达到阈值的故障，不开单。\n")
        return
    for d in confirmed:
        ns = argparse.Namespace(type=d["type"], target=d["target"], source=d["source"], message=d["message"])
        ri.run_incident(ns, apply_fixes=False)


if __name__ == "__main__":
    main()
