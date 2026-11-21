"""App 2 adapter: service desk L1. People ask for help with account, VPN, email and software.

Only intake, crew selection, INVESTIGATE and MITIGATE are app logic. Checks come from v1 desk.py (app.json), repairs from the
shared v1 repair loop. Teams and Outlook requests are recognised here even though v1 app.json has no Teams keyword.
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from . import SKILL  # noqa: F401
import remediate as rm  # noqa: E402
import harvest as hv  # noqa: E402
import desk  # noqa: E402

from .plugins import hold_ticket  # noqa: E402
from .skeleton import Stop  # noqa: E402

CREWS = {k: dict(c["label"]) for k, c in desk.CFG["crews"].items()}
SERVICE_CREW = {"teams": "account", "outlook": "email"}  # service named in the text -> crew, when app.json keywords miss
TEAMS_WORDS, OUTLOOK_WORDS = ("teams", "微软会议"), ("outlook", "邮件", "邮箱", "exchange")


def make_ctx(data_dir: str, lang: str = "en", clock=None):
    return desk.ctx_for(data_dir, lang, clock=clock)


def crew_for(text: str) -> Optional[str]:
    t = (text or "").lower()
    found = desk.classify(text)
    if found:
        return found
    return SERVICE_CREW["teams"] if any(w in t for w in TEAMS_WORDS) else (SERVICE_CREW["outlook"] if any(w in t for w in OUTLOOK_WORDS) else None)


class ServiceDeskAdapter:
    app = "servicedesk"
    crews = CREWS

    def __init__(self, directory: Dict[str, Any], office=None) -> None:
        self.directory, self.office, self.msgs = directory, office, []

    def _user(self, item):
        return self.directory.get(item["user"], {"name": {"en": item["user"], "zh": item["user"]}, "device": {"name": item["user"]}})

    def _base(self, item) -> Dict[str, Any]:
        user, text = self._user(item), item["text"]
        return {"short_description": text[:120], "description": text, "caller": user["name"]["en"], "cmdb_ci": user["device"]["name"], "message": text,
                "category": "Request", "impact": "3", "urgency": "3", "priority": "4 - Low", "kind": "request", "channel": item["channel"]}

    def _say(self, ctx, kind, ref, name, en, zh):
        self.msgs.append(desk._msg(ctx, kind, ref, "To %s: %s" % (name["en"], en), "致 %s：%s" % (name["zh"], zh)))

    def receive(self, item, ctx):
        n = self._user(item)["name"]
        return {"en": "%s request from %s" % (item["channel"], n["en"]), "zh": "来自 %s 的 %s 请求" % (n["zh"], item["channel"])}

    def safety(self, item, ctx):
        text = item["text"]
        code = hv.injection_reason(text)
        admin = next((w for w in desk.CFG.get("never_automate", []) if w in text.lower()), None)
        if not (code or admin):
            return None
        why = {"override": ("tries to override the rules", "试图改写规则"), "credential": ("contains a password", "含有密码")}.get(code, ("asks for admin rights", "申请管理员权限"))
        group = ctx.policy["escalation"]["groups"]["security"]
        return Stop("rejected", "Rejected: it %s. Never automated." % why[0], "拒绝：它%s。永不自动处理。" % why[1],
                    notes={"INVESTIGATE": {"en": "Skipped: nothing is checked for a rejected request.", "zh": "已跳过：被拒绝的请求不做任何检查。"},
                           "MITIGATE": {"en": "Nothing run.", "zh": "什么都没做。"},
                           "RESOLVE": {"en": "Routed to %s for review." % group, "zh": "转给 %s 审查。" % group},
                           "LOG": {"en": "Ticket and audit entry written.", "zh": "已建工单并记入审计。"}},
                    code=code or "admin", why=why, group=group)

    def known_link(self, item, ctx):
        known = desk._known(self.office, item["text"])
        if not known:
            return None
        kind, ref, ans, extra = known
        what = ({"en": "the %s outage" % extra["upstream"], "zh": "%s 大面积故障" % extra["upstream"]} if kind == "outage"
                else {"en": "the device already under repair", "zh": "已在维修的设备"})
        return Stop("linked_known", "Known incident: linked to %s. No new work." % what["en"], "已知故障：挂到%s下，不重复派人。" % what["zh"],
                    parent={"en": "Known incident: %s" % what["en"], "zh": "已知故障：%s" % what["zh"]},
                    notes={"INVESTIGATE": {"en": "Skipped: the patrol is already on it.", "zh": "已跳过：巡检已经在处理。"},
                           "MITIGATE": {"en": "Skipped: repairs run on the known incident.", "zh": "已跳过：修复在已知故障上进行。"},
                           "RESOLVE": {"en": "Waiting; this request closes when the known incident closes.", "zh": "等待；已知故障关闭时一起关闭。"},
                           "LOG": {"en": "Ticket kept on hold as a child of the known incident.", "zh": "工单保持挂起，挂在已知故障下。"}},
                    ref=ref, kind=kind, answer=ans)

    def select_crew(self, item, ctx):
        crew = crew_for(item["text"])
        if crew:
            return crew
        return Stop("escalated", "No crew matches; a person reads it.", "没有匹配的班底，交给人看。")

    def investigate(self, item, crew, ctx):
        user = self._user(item)
        item.setdefault("target", user["device"]["name"])
        item["_ev"] = desk.investigate(crew, user)
        item["_skey"] = rm.symptom_key(crew, item["text"])
        item["_key"] = "%s|%s|%s" % (crew, user["device"]["name"], item["_skey"])
        num, _ = rm.ticket_upsert(ctx, item["_key"], dict(self._base(item), assignment_group=desk.CFG["intake_group"], device=crew, symptom=item["_skey"]),
                                  "request_received", {"crew": crew})
        item["_ticket"] = num
        ev = item["_ev"]
        return {"en": "; ".join("%s: %s" % (e["check"]["en"], e["result"]["en"]) for e in ev),
                "zh": "；".join("%s：%s" % (e["check"]["zh"], e["result"]["zh"]) for e in ev)}

    def mitigate(self, item, crew, plan, ctx):
        ci = self._user(item)["device"]["name"]
        ns = argparse.Namespace(type=crew, target=ci, ci=ci, source=item["channel"], message=item["text"], message_zh=None)
        res = rm.remediate(ns, ctx, scenario=set(item.get("fixes", [])), quiet=True, evidence=item["_ev"], hints=plan["hints"] or None)
        A = ctx.actions
        ran = [t for t in res["trace"] if t["decision"] == "run"]
        en = "; ".join("%s → %s" % (A[t["action"]]["en"], "recovered" if t.get("recovered") else "not recovered") for t in ran) or "nothing allowed to run"
        zh = "；".join("%s → %s" % (A[t["action"]]["zh"], "已恢复" if t.get("recovered") else "没恢复") for t in ran) or "没有可自动执行的步骤"
        tk = rm.tickets_load(ctx)["tickets"][item["_ticket"]]
        outcome = "resolved" if res["resolved"] else ("on_hold" if tk.get("awaiting_approval") else "escalated")
        return {"en": en, "zh": zh, "outcome": outcome, "res": res, "ran": ran}

    def resolve(self, item, result, ctx):
        res, A, user = result["res"], ctx.actions, self._user(item)
        first = user["name"]["en"].split(" (")[0].split()[0]
        first_zh = user["name"]["zh"].split("（")[0]
        if res["resolved"]:
            fx = result["ran"][-1]["action"]
            reply = {"en": "Hi %s, I did this for you: %s. Tell me if it is still broken." % (first, A[fx]["en"].lower()),
                     "zh": "%s 你好，已经帮你%s。如果还有问题告诉我。" % (first_zh, A[fx]["zh"])}
            self._say(ctx, "hd_resolved", item["_ticket"], user["name"], reply["en"], reply["zh"])
            if item.get("confirm"):
                return {"en": "%s confirmed: “%s”" % (first, item["confirm"]), "zh": "%s 确认：“%s”" % (first_zh, item["confirm"])}
            return {"en": "Fixed; %s is asked to confirm." % first, "zh": "已修好，请 %s 确认。" % first_zh}
        crew = item["_key"].split("|")[0]
        group = ctx.policy["escalation"]["groups"].get(crew, desk.CFG["intake_group"])
        rm.ticket_update(ctx, item["_key"], rm.AUTOMATION, "routed_l2", {"group": group}, keep_state=True, assignment_group=group)
        tk = rm.tickets_load(ctx)["tickets"][item["_ticket"]]
        waiting = tk.get("awaiting_approval") or []
        left = [x for x in res["left"] if x["why"] == "human"]
        if waiting:
            how = ("needs approval for “%s”" % ", ".join(A[a]["en"] for a in waiting), "“%s”需要批准" % "、".join(A[a]["zh"] for a in waiting))
        elif left:
            how = ("needs a person: %s" % ", ".join(A[x["action"]]["en"] for x in left), "需要人来做：%s" % "、".join(A[x["action"]]["zh"] for x in left))
        else:
            how = ("automatic steps did not fix it", "自动步骤没能解决")
        reply = {"en": "Hi %s, I couldn't finish this myself: it %s. %s has it now with everything I checked." % (first, how[0], group),
                 "zh": "%s 你好，这个我没法自己完成：%s。已转给 %s，我查过的都附上了。" % (first_zh, how[1], group)}
        self._say(ctx, "hd_escalated", item["_ticket"], user["name"], reply["en"], reply["zh"])
        return {"en": "Sent to %s: %s. Everything tried is on the ticket." % (group, how[0]), "zh": "转给 %s：%s。做过的都写在工单上。" % (group, how[1])}

    def log(self, item, result, ctx):
        tk = rm.tickets_load(ctx)["tickets"][item["_ticket"]]
        state_zh = desk.STATE_ZH.get(tk["state"], tk["state"])
        return {"en": "Ticket %s is %s." % (item["_ticket"], tk["state"]), "zh": "工单 %s 状态：%s。" % (item["_ticket"], state_zh)}

    def on_stop(self, item, stop, ctx):
        user, key = self._user(item), "request|%s" % item["id"]
        name, base, groups = user["name"], self._base(item), ctx.policy["escalation"]["groups"]
        if stop.outcome == "rejected":
            num, _ = rm.ticket_upsert(ctx, key, dict(base, assignment_group=groups["security"], device="security", priority="2 - High"),
                                      "request_rejected", {"reason": stop.meta["code"], "text": item["text"]})
            rm.append_jsonl(ctx.audit_path, {"ts": ctx.ts(), "decision": "request_rejected", "request": item["id"], "reason": stop.meta["code"]})
            why = stop.meta["why"]
            self.msgs.append(desk._msg(ctx, "hd_rejected", num, "A request was rejected (%s) and sent to %s. No automation." % (why[0], stop.meta["group"]),
                                       "一条请求已拒绝（%s），转给 %s，未做任何自动操作。" % (why[1], stop.meta["group"])))
        elif stop.outcome == "linked_known":
            num, _ = rm.ticket_upsert(ctx, key, dict(base, assignment_group=desk.CFG["intake_group"], device="linked"), "linked_known",
                                      {"parent": stop.meta["ref"], "kind": stop.meta["kind"]}, extra={"parent_incident": stop.meta["ref"], "caller_zh": name["zh"]})
            rm.ticket_update(ctx, key, rm.AUTOMATION, "linked_known", {"parent": stop.meta["ref"]}, keep_state=True, state="On Hold",
                             hold_reason="Linked to %s" % stop.meta["ref"])
            ans = stop.meta["answer"]
            first = name["en"].split(" (")[0].split()[0]
            self._say(ctx, "hd_reply", num, name, "Thanks %s, we already know. %s We'll tell you when it's fixed." % (first, ans["en"]),
                      "谢谢，我们已经知道了。%s修好后会通知你。" % ans["zh"])
        elif stop.outcome == "linked_vendor":
            svc = stop.meta["svc"]
            num = hold_ticket(ctx, key, dict(base, assignment_group=desk.CFG["intake_group"], symptom="vendor"), stop, self.app, name)
            first = name["en"].split(" (")[0].split()[0]
            self._say(ctx, "hd_reply", num, name,
                      "Hi %s, %s is down for many people and the vendor is on it (confidence %d%%). You do not need to report again. We will tell you when it is fixed."
                      % (first, svc["label"]["en"], stop.meta["pct"]),
                      "%s 目前有多人受影响，厂商正在处理（置信度 %d%%）。你不用重复报障，修复后会通知你。" % (svc["label"]["zh"], stop.meta["pct"]))
        else:  # no crew matches
            rm.ticket_upsert(ctx, key, dict(base, assignment_group=desk.CFG["intake_group"], device="unknown"), "request_received", {})
