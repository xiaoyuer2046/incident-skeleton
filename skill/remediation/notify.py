#!/usr/bin/env python3
"""Notify: push what matters to the team's chat, so nobody has to watch the board.

Messages (each bilingual, sent once):
  outage        a mass outage was grouped into one upstream ticket
  board         new news on an outage board (master incident note, outage email, link)
  board_closed  the outage is resolved and our patrol confirms it
  failed        automatic repair failed; ticket opened or reopened, with what was tried
  approval      a risky step is waiting for a person to approve it
  fixed         automation fixed a device that had an open ticket, and closed it
  regressed     a fix did not hold: the fault came back before the delayed re-check
  kill          the kill switch is on, so a device was not repaired

Channels and routing are in policy.json "notify". Dry run by default: messages go to
outbox.jsonl only. When dry_run is false and the webhook URL is in the env var the
channel names (TEAMS_WEBHOOK_URL, SLACK_WEBHOOK_URL), it POSTs {"text": ...}. The live
POST is written but has not been tested against real Teams or Slack webhooks.
"""
import json, os, urllib.request
import remediate as rm


def _state_path(ctx):
    return os.path.join(ctx.dir, "notify_state.json")


def build(ctx, rows, events, results, board, rechecks, last_ts):
    now, A, msgs = ctx.ts(), ctx.actions, []

    def m(kind, en, zh, ref=None):
        msgs.append({"kind": kind, "ts": now, "ref": ref, "text": {"en": en, "zh": zh}})

    for e in events:
        if e["kind"] == "upstream" and e.get("event") == "created":
            m("outage", "🟣 Mass outage: %d devices behind %s are down. One ticket %s; per-device repairs held back." % (len(e["devices"]), e["upstream"], e["ticket"]),
              "🟣 大面积故障：%s 下 %d 台设备掉线。只开一张单 %s，暂停逐台修复。" % (e["upstream"], len(e["devices"]), e["ticket"]), e["ticket"])
    for r in results:
        tk = r.get("ticket") or {}
        num, grp, ci = tk.get("number"), tk.get("group"), r["ci"]
        tried_en = ", ".join(A[a["action"]]["en"] for a in r["attempts"]) or "nothing"
        tried_zh = "、".join(A[a["action"]]["zh"] for a in r["attempts"]) or "没有"
        if tk.get("event") in ("created", "reopened"):
            if r.get("killed"):
                who = r["killed"].get("by", "?")
                m("kill", "⛔ Automation is paused (kill switch, %s). %s was not repaired. Ticket %s → %s." % (who, ci, num, grp),
                  "⛔ 自动修复已暂停（紧急开关，%s）。%s 没有修。工单 %s → %s。" % (who, ci, num, grp), num)
            else:
                again_en, again_zh = ("came back; " if tk["event"] == "reopened" else ""), ("复发；" if tk["event"] == "reopened" else "")
                m("failed", "🔴 %s: %sautomatic repair failed (%s). Tried: %s. Ticket %s → %s." % (ci, again_en, r["message"], tried_en, num, grp),
                  "🔴 %s：%s自动修复失败（%s）。已试：%s。工单 %s → %s。" % (ci, again_zh, r.get("message_zh") or r["message"], tried_zh, num, grp), num)
            for x in r["left"]:
                if x["why"] == "approval" and not r.get("killed"):
                    m("approval", "🟠 Approval needed on %s: “%s” for %s. Approve it and the next patrol acts." % (num, A[x["action"]]["en"], ci),
                      "🟠 %s 需要批准：对 %s 执行“%s”。批准后下一轮巡检会去做。" % (num, ci, A[x["action"]]["zh"]), num)
        elif tk.get("event") == "resolved" and r["resolved"]:
            fx = r["attempts"][-1]["action"]
            m("fixed", "✅ %s fixed by automation: %s. Ticket %s resolved." % (ci, A[fx]["en"], num),
              "✅ %s 已自动修好：%s。工单 %s 已解决。" % (ci, A[fx]["zh"], num), num)
    for x in rechecks:
        if not x["held"]:
            m("regressed", "⚠️ Fix did not hold: “%s” on %s (done %s) — the fault is back. Counted as a failure." % (A[x["action"]]["en"], x["device"], x["fixed_at"][11:16]),
              "⚠️ 修复没稳住：%s 修的“%s”（%s）又坏了。这次记为失败。" % (x["device"], A[x["action"]]["zh"], x["fixed_at"][11:16]))
    for b in (board or {}).values():
        new = [i for i in b["timeline"] if last_ts < i["ts"] <= now and (i["source"] in ("servicenow", "email") or i.get("kind") in ("link", "close"))]
        if any(i.get("kind") == "close" for i in new):
            m("board_closed", "✅ %s outage closed. %s" % (b["upstream"], b["summary"]["en"]), "✅ %s 故障已关闭。%s" % (b["upstream"], b["summary"]["zh"]),
              (b.get("master") or {}).get("number"))
        elif new:
            m("board", "📣 %s outage update: %s" % (b["upstream"], b["summary"]["en"]), "📣 %s 故障进展：%s" % (b["upstream"], b["summary"]["zh"]),
              (b.get("master") or {}).get("number"))
    return msgs


def send(ctx, msgs):
    cfg = ctx.policy.get("notify", {})
    dry = cfg.get("dry_run", True) or not ctx.live
    for msg in msgs:
        msg["channels"] = []
        for ch in cfg.get("channels", []):
            kinds = ch.get("kinds", "*")
            if kinds != "*" and msg["kind"] not in kinds:
                continue
            msg["channels"].append(ch["name"])
            sent, err = False, None
            url = os.environ.get(ch.get("webhook_env", ""), "")
            if not dry and url:
                try:
                    body = json.dumps({"text": msg["text"]["en"] + "\n" + msg["text"]["zh"]}).encode()
                    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=15).close()
                    sent = True
                except Exception as e:
                    err = type(e).__name__
            rm.append_jsonl(os.path.join(ctx.dir, "outbox.jsonl"), {"ts": msg["ts"], "channel": ch["name"], "platform": ch.get("platform"),
                            "kind": msg["kind"], "ref": msg["ref"], "text": msg["text"], "dry_run": dry, "sent": sent, "error": err})
        msg["dry_run"] = dry
    return msgs


def run(ctx, rows, events, results, board, rechecks):
    st = rm.load_json(_state_path(ctx), {"last_ts": ""})
    msgs = send(ctx, build(ctx, rows, events, results, board, rechecks, st["last_ts"]))
    rm.save_json(_state_path(ctx), {"last_ts": ctx.ts()})
    return msgs
