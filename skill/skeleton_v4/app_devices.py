"""App 1 adapter: office devices. Patrol-confirmed faults for printer, signage, meeting-room AV and wireless AP.

Only intake, crew selection, INVESTIGATE and MITIGATE are app logic. Repair uses v1 remediate.py through its public functions.
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, Optional

from . import SKILL  # noqa: F401
import remediate as rm  # noqa: E402
import harvest as hv  # noqa: E402

from .plugins import hold_ticket  # noqa: E402
from .skeleton import Stop  # noqa: E402

CREWS = {"printer": {"en": "Printer", "zh": "打印机"}, "signage": {"en": "Digital signage", "zh": "数字标牌"},
         "av": {"en": "Meeting-room AV", "zh": "会议室音视频"}, "wifiap": {"en": "Wireless AP", "zh": "无线 AP"}}
EVIDENCE = [{"check": {"en": "patrol probe", "zh": "巡检探测"}, "result": {"en": "no answer in 3 of 3 probes", "zh": "3 次探测都没有回应"}, "status": "err"}]


def make_ctx(data_dir: str, lang: str = "en", clock=None):
    return rm.Ctx(data_dir, lang, live=False, clock=clock, ticket_prefix="INC", ticket_start=30000)


def item_from(dev: Dict[str, Any], fault: Dict[str, Any], recheck: Optional[str] = None) -> Dict[str, Any]:
    """One patrol-confirmed fault as a skeleton item. `recheck` ('healthy' | 'confirmed') is the simulated delayed re-check."""
    msg = fault["message"]
    return {"id": dev["id"], "type": dev["type"], "loc": dev.get("loc", {"en": dev["id"], "zh": dev["id"]}), "target": dev.get("target", dev["id"]),
            "text": msg, "message_zh": fault.get("message_zh") or msg, "fixes": list(fault.get("fixes", [])), "evidence": fault.get("evidence") or EVIDENCE,
            "title": fault.get("title") or {"en": msg, "zh": fault.get("message_zh") or msg}, "recheck": recheck}


class DevicesAdapter:
    app = "devices"
    crews = CREWS

    def receive(self, item, ctx):
        loc = item["loc"]
        return {"en": "Patrol confirmed a fault at %s: %s" % (loc["en"], item["text"]), "zh": "巡检确认 %s 故障：%s" % (loc["zh"], item["message_zh"])}

    def safety(self, item, ctx):
        code = hv.injection_reason(item["text"])
        if not code:
            return None
        rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "fault_text_rejected", "item": item["id"], "reason": code})
        return Stop("rejected", "Rejected: the fault text tries to give orders. Nothing runs.", "拒绝：故障文本试图下命令，什么都不会执行。")

    def known_link(self, item, ctx):
        return None  # upstream grouping stays in v1 orchestrator.py; the global link is a plug-in slot

    def select_crew(self, item, ctx):
        if item["type"] in CREWS:
            return item["type"]
        return Stop("escalated", "No crew for this device type; a person reads it.", "没有对应的班底，交给人处理。")

    def investigate(self, item, crew, ctx):
        ev = item["evidence"]
        return {"en": "; ".join("%s: %s" % (e["check"]["en"], e["result"]["en"]) for e in ev),
                "zh": "；".join("%s：%s" % (e["check"]["zh"], e["result"]["zh"]) for e in ev)}

    def mitigate(self, item, crew, plan, ctx):
        ns = argparse.Namespace(type=crew, target=item["target"], ci=item["id"], source=item["loc"]["en"], message=item["text"], message_zh=item["message_zh"])
        res = rm.remediate(ns, ctx, scenario=set(item["fixes"]), quiet=True, evidence=item["evidence"], hints=plan["hints"] or None)
        A = ctx.actions
        ran = [t for t in res["trace"] if t["decision"] == "run"]
        en = "; ".join("%s → %s" % (A[t["action"]]["en"], "recovered" if t.get("recovered") else "not recovered") for t in ran) or "nothing allowed to run"
        zh = "；".join("%s → %s" % (A[t["action"]]["zh"], "已恢复" if t.get("recovered") else "没恢复") for t in ran) or "没有可自动执行的步骤"
        return {"en": en, "zh": zh, "outcome": "local_repair" if res["resolved"] else "escalated", "res": res, "ran": ran}

    def resolve(self, item, result, ctx):
        res, A = result["res"], ctx.actions
        if res["resolved"]:
            fx, mins = result["ran"][-1]["action"], ctx.policy.get("recheck_minutes", 10)
            return {"en": "Recovered by “%s”; re-check due in %d minutes." % (A[fx]["en"], mins), "zh": "已用“%s”恢复，%d 分钟后复查。" % (A[fx]["zh"], mins)}
        group = (res.get("ticket") or {}).get("group", "Service Desk")
        return {"en": "Sent to %s with everything tried." % group, "zh": "已转给 %s，做过的步骤都附上了。" % group}

    def log(self, item, result, ctx):
        num = (result["res"].get("ticket") or {}).get("number")
        if result["res"]["resolved"]:
            if not num:
                return {"en": "Resolved by automation with no ticket needed; fix recorded as provisional until the re-check.",
                        "zh": "由自动化解决，无需开单；修复先记为暂定，复查后才算数。"}
            return {"en": "Ticket %s resolved by automation; fix recorded as provisional until the re-check." % num,
                    "zh": "工单 %s 由自动化解决；修复先记为暂定，复查后才算数。" % num}
        if not num:
            return {"en": "Escalated to a person.", "zh": "已升级给人工处理。"}
        return {"en": "Ticket %s escalated." % num, "zh": "工单 %s 已升级。" % num}

    def on_stop(self, item, stop, ctx):
        if stop.outcome != "linked_vendor":
            return
        loc, dtype = item["loc"], item["type"]
        fields = {"short_description": "[Auto] %s: linked to vendor incident - %s" % (item["id"], item["text"]), "description": item["text"],
                  "cmdb_ci": item["id"], "assignment_group": ctx.policy.get("escalation", {}).get("groups", {}).get(dtype, "Service Desk"),
                  "symptom": "vendor", "message": item["text"], "category": "Hardware", "impact": "2", "urgency": "2", "priority": "3 - Moderate",
                  "kind": "device", "caller": rm.AUTOMATION}
        hold_ticket(ctx, "vendor|%s" % item["id"], fields, stop, self.app,
                    {"en": "the organisers of %s" % loc["en"], "zh": "%s 的会议组织者" % loc["zh"]})
