#!/usr/bin/env python3
"""One patrol cycle, end to end.

    probes -> threshold (one miss is a blip) -> maintenance window (silence)
      -> blast radius (many faults behind one upstream switch = ONE upstream
         ticket, and no per-device reboots)
      -> per-device repair loop (remediate.py)
      -> ticket upkeep (an upstream ticket resolves itself when its devices recover)

Used by simulate.py with a scripted world. A live patrol would pass real probe
results in the same shape.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remediate as rm


def classify(probes, need):
    fails = probes.count(False)
    if fails == 0:
        return "healthy"
    if fails < need:
        return "blip"
    # failed enough to confirm, but the last probe answered: it came back on its own.
    # No repair, and no credit to any fix.
    return "self_healed" if probes[-1] else "confirmed"


def in_maintenance(ctx, dev_id, windows):
    now = ctx.clock()
    for w in windows:
        if w["device"] == dev_id and rm.to_epoch(w["from"]) <= now < rm.to_epoch(w["to"]):
            return w
    return None


def run_cycle(ctx, devices, probes, faults, approvals=None, windows=(), quiet=True):
    """devices: [{id, type, upstream, ...}]; probes: id -> [bool]*rounds;
    faults: id -> {message, message_zh, fixes, evidence}. Returns a structured report."""
    need = ctx.policy.get("patrol", {}).get("need", 2)
    rounds = ctx.policy.get("patrol", {}).get("rounds", 3)
    min_blast = ctx.policy.get("blast_radius", {}).get("min_devices", 3)
    rows = []
    for d in devices:
        p = list(probes.get(d["id"], [True] * rounds))
        status = classify(p, need)
        row = {"id": d["id"], "type": d["type"], "probes": p, "status": status}
        if status != "healthy":
            w = in_maintenance(ctx, d["id"], windows)
            if w:
                row.update(status="maintenance", window=w)
        rows.append(row)
    by_id = {r["id"]: r for r in rows}
    rechecks = rm.recheck(ctx, {r["id"]: r["status"] for r in rows})
    dev_by_id = {d["id"]: d for d in devices}
    events = []

    # blast radius: group confirmed faults by upstream switch
    groups = {}
    for r in rows:
        if r["status"] == "confirmed":
            groups.setdefault(dev_by_id[r["id"]].get("upstream"), []).append(r)
    for up, rs in groups.items():
        if not up or len(rs) < min_blast:
            continue
        ids = [r["id"] for r in rs]
        for r in rs:
            r.update(status="upstream", upstream=up)
        fields = {"short_description": "[Auto] %d devices behind %s down at once - suspected upstream fault" % (len(ids), up),
                  "description": "Devices: %s. Per-device repairs were held back." % ", ".join(ids),
                  "cmdb_ci": up, "assignment_group": ctx.policy.get("escalation", {}).get("groups", {}).get("upstream", "Network"),
                  "device": "upstream", "symptom": "down", "category": "Network", "impact": "1", "urgency": "2",
                  "priority": "2 - High", "kind": "upstream",
                  "message": "%d devices behind %s down at once" % (len(ids), up),
                  "message_zh": "%s 下的 %d 台设备同时掉线" % (up, len(ids))}
        num, ev = rm.ticket_upsert(ctx, "upstream|%s|down" % up, fields, "upstream", {"devices": ids, "upstream": up},
                                   extra={"devices": ids})
        events.append({"kind": "upstream", "upstream": up, "devices": ids, "ticket": num, "event": ev})
        for r in rs:
            r["ticket"] = num

    # active watch: master incident + outage mail for every open outage (see watch.py)
    import watch
    board, hints = watch.poll(ctx)

    results = []
    for r in rows:
        if r["status"] != "confirmed":
            continue
        d, f = dev_by_id[r["id"]], faults.get(r["id"], {})
        ns = argparse.Namespace(type=d["type"], target=d.get("target", d["id"]), ci=d["id"], source=d.get("location", ""),
                                message=f.get("message", "patrol: %s unreachable" % d["id"]), message_zh=f.get("message_zh"))
        scenario = set(f["fixes"]) if "fixes" in f else None  # None = verify with a real probe
        res = rm.remediate(ns, ctx, scenario=scenario, approvals=approvals or {}, quiet=quiet,
                           evidence=f.get("evidence"), hints=hints.get(d["id"]))
        res["message_zh"] = f.get("message_zh")
        r["ticket"] = (res.get("ticket") or {}).get("number")
        r["resolved"] = res["resolved"]
        results.append(res)

    # an open upstream ticket resolves itself once every device behind it is healthy again
    # (healthy on the probe, or fixed by the repair loop in this patrol)
    fixed = {r["ci"] for r in results if r["resolved"]}
    tk_all = rm.tickets_load(ctx)
    for key, num in list(tk_all["by_key"].items()):
        tk = tk_all["tickets"][num]
        if key.startswith("upstream|") and tk["state"] in rm.OPEN_STATES:
            devs = tk.get("devices", [])
            if devs and all(by_id.get(x, {}).get("status") == "healthy" or x in fixed for x in devs):
                needed = [x for x in devs if x in fixed]
                rm.ticket_resolve(ctx, key, rm.AUTOMATION, "upstream_recovered", {"devices": devs, "needed_fix": needed,
                                  "master": tk.get("parent_incident")},
                                  close_notes="All devices behind %s recovered." % tk.get("cmdb_ci"))
                events.append({"kind": "upstream_recovered", "upstream": tk.get("cmdb_ci"), "devices": devs, "ticket": num, "needed_fix": needed})
    board = watch.after(ctx, rows, results)
    import notify
    notes = notify.run(ctx, rows, events, results, board, rechecks)
    return {"rows": rows, "events": events, "results": results, "board": board, "rechecks": rechecks, "notifications": notes}
