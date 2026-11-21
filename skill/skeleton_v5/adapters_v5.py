"""v5 adapters: the v4 adapters with two small additions. App logic only; the six steps stay in skeleton_v4/skeleton.py.

Devices: a fault in a room whose meeting still works is put ON HOLD until the meeting ends when only risky steps are left.
Service desk: passes a person's standing approval (plan["approvals"]) to the v1 repair loop, which already accepts it.
"""
from __future__ import annotations

import argparse

from . import SKILL  # noqa: F401
import remediate as rm  # noqa: E402
from skeleton_v4 import app_devices, app_servicedesk  # noqa: E402


class DevicesAdapterV5(app_devices.DevicesAdapter):
    def mitigate(self, item, crew, plan, ctx):
        result = super().mitigate(item, crew, plan, ctx)
        wait = plan.get("deferred")
        if wait and not result["res"]["resolved"]:
            A = ctx.actions
            names = {l: (", " if l == "en" else "、").join(A[a][l] for a in wait["actions"]) for l in ("en", "zh")}
            result.update(outcome="on_hold", deferred=wait,
                          en="%s; waits until %s: %s" % (result["en"], wait["until"], names["en"]),
                          zh="%s；等到 %s 再做：%s" % (result["zh"], wait["until"], names["zh"]))
        return result

    def resolve(self, item, result, ctx):
        wait = result.get("deferred")
        if wait:
            return {"en": "Scheduled for %s, after the meeting. The organiser is told." % wait["until"],
                    "zh": "安排在 %s 会后处理，已告诉会议组织者。" % wait["until"]}
        return super().resolve(item, result, ctx)

    def log(self, item, result, ctx):
        wait = result.get("deferred")
        num = (result["res"].get("ticket") or {}).get("number")
        if wait and num:
            return {"en": "Ticket %s on hold until %s." % (num, wait["until"]), "zh": "工单 %s 挂起到 %s。" % (num, wait["until"])}
        return super().log(item, result, ctx)


class ServiceDeskAdapterV5(app_servicedesk.ServiceDeskAdapter):
    def mitigate(self, item, crew, plan, ctx):
        ci = self._user(item)["device"]["name"]
        ns = argparse.Namespace(type=crew, target=ci, ci=ci, source=item["channel"], message=item["text"], message_zh=None)
        res = rm.remediate(ns, ctx, scenario=set(item.get("fixes", [])), approvals=plan.get("approvals") or None, quiet=True,
                           evidence=item["_ev"], hints=plan["hints"] or None)
        A = ctx.actions
        ran = [t for t in res["trace"] if t["decision"] == "run"]
        en = "; ".join("%s → %s" % (A[t["action"]]["en"], "recovered" if t.get("recovered") else "not recovered") for t in ran) or "nothing allowed to run"
        zh = "；".join("%s → %s" % (A[t["action"]]["zh"], "已恢复" if t.get("recovered") else "没恢复") for t in ran) or "没有可自动执行的步骤"
        tk = rm.tickets_load(ctx)["tickets"][item["_ticket"]]
        outcome = "resolved" if res["resolved"] else ("on_hold" if tk.get("awaiting_approval") else "escalated")
        return {"en": en, "zh": zh, "outcome": outcome, "res": res, "ran": ran}
