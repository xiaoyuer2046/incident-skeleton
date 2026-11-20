#!/usr/bin/env python3
"""Patrol: four crews watch four device types at the same time.  (--lang zh|en)

Each crew probes its own device in parallel. One failed probe is a blip and is
ignored. A device that fails at least --need of --rounds probes is CONFIRMED.
Then, depending on the flags:

  (default)      the skeleton walks the alert and writes a postmortem (read-only)
  --remediate    the remediation loop tries permitted fixes, learns from the
                 result, and if it cannot fix the fault, says what it did and
                 opens a ServiceNow incident (dry run unless policy.json says live)

Run it on a schedule with Kiro Crew's cron (a no-LLM script job), for example
every 5 minutes:   python3 patrol.py --remediate --lang en

Safe public sample targets are built in. 192.0.2.1 is a reserved test address
that never answers, so the meeting room is always "down" in the samples.

Usage:
  python3 patrol.py
  python3 patrol.py --rounds 5 --need 3 --remediate --simulate-fix none
"""
import argparse, os, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "remediation"))
import run_incident as ri

T = ri.T

DEVICES = [
    {"type": "printer", "target": "1.1.1.1", "source": "SNMP 10.0.4.21", "message": "patrol: printer unreachable"},
    {"type": "signage", "target": "https://example.com", "source": "CMS / lobby east", "message": "patrol: signage player offline"},
    {"type": "av", "target": "192.0.2.1", "source": "Zoom Rooms / 3F-301", "message": "patrol: meeting room controller offline"},
    {"type": "wifiap", "target": "1.1.1.1", "source": "controller / floor 3", "message": "patrol: AP offline, clients dropping"},
]


def probe_once(dev):
    t = dev["target"]
    if ri.is_url(t):
        ok, txt = ri.curl(t)
        return ok and txt.startswith("HTTP") and txt.split()[1][:1] in ("2", "3")
    return ri.ping(t)[0]


def watch(dev, rounds, interval):
    history = []
    for i in range(rounds):
        history.append(probe_once(dev))
        if i < rounds - 1:
            time.sleep(interval)
    return history


def main():
    ap = argparse.ArgumentParser(description="Four crews patrol at the same time")
    ap.add_argument("--rounds", type=int, default=3, help="probes per device")
    ap.add_argument("--need", type=int, default=2, help="failed probes needed to confirm a fault")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between probes")
    ap.add_argument("--lang", choices=["zh", "en"])
    ap.add_argument("--remediate", action="store_true", help="try permitted fixes, then escalate if they fail")
    ap.add_argument("--simulate-fix", help="with --remediate: comma list of action ids that fix it; 'none' = nothing does")
    ap.add_argument("--data-dir", help="where the crew keeps what it learned")
    args = ap.parse_args()
    if args.lang:
        ri.set_lang(args.lang)

    print("\n  🔭 " + T("四个代理同时巡检：每台探测 %d 次，失败 ≥ %d 次才算确认" % (args.rounds, args.need),
                      "Four crews patrol at once: %d probes each, a fault is confirmed at ≥ %d failures" % (args.rounds, args.need)) + "\n")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(DEVICES)) as pool:
        futs = {d["type"]: pool.submit(watch, d, args.rounds, args.interval) for d in DEVICES}
        results = {k: f.result() for k, f in futs.items()}
    elapsed = time.time() - t0

    confirmed = []
    print("  %-18s%-14s%-8s%s" % (T("班底", "crew"), T("探测", "probes"), T("失败", "fails"), T("结论", "verdict")))
    print("  " + "─" * 62)
    for d in DEVICES:
        h = results[d["type"]]
        fails = h.count(False)
        marks = " ".join("✓" if x else "✗" for x in h)
        name = ri.CREW[d["type"]]["icon"] + " " + ri.label(d["type"])
        if fails >= args.need:
            verdict = "🔴 " + T("确认故障", "confirmed fault")
            confirmed.append(d)
        elif fails > 0:
            verdict = "🟡 " + T("偶发抖动，忽略（不开单）", "blip, ignored (no ticket)")
        else:
            verdict = "🟢 " + T("正常", "healthy")
        print("  %-18s%-14s%-8s%s" % (name, marks, fails, verdict))
    print("\n  " + T("四台并行巡检用时 %.1f 秒" % elapsed, "Four devices patrolled in parallel in %.1f s" % elapsed) + "\n")

    if not confirmed:
        print("  " + T("没有达到阈值的故障，不开单。", "No fault reached the threshold. No ticket.") + "\n")
        return
    if args.remediate:
        import remediate as rm
        ctx = rm.Ctx(args.data_dir or os.path.join(HERE, "..", "remediation", "data"), ri.LANG)
        scen = None
        if args.simulate_fix is not None:
            scen = set() if args.simulate_fix == "none" else set(x for x in args.simulate_fix.split(",") if x)
        for d in confirmed:
            ns = argparse.Namespace(type=d["type"], target=d["target"], source=d["source"], message=d["message"])
            rm.remediate(ns, ctx, scenario=scen)
        return
    for d in confirmed:
        ns = argparse.Namespace(type=d["type"], target=d["target"], source=d["source"], message=d["message"])
        ri.run_incident(ns, apply_fixes=False)


if __name__ == "__main__":
    main()
