#!/usr/bin/env python3
"""Tests for the pre-meeting check, KB drafts and chat.

    python3 skill/tests/test_meetings_kb_chat.py
"""
import argparse, os, sys, tempfile, unittest
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "remediation"))
os.environ["BRAIN"] = "off"
import remediate as rm
import orchestrator as orch
import premeeting, kbdraft, chatops

DEVS = [{"id": "AV-3F-301", "type": "av"}, {"id": "AV-5F-502", "type": "av"}, {"id": "AV-2F-201", "type": "av"}]
EVID = [{"check": "codec", "result": "hung", "status": "err"}]


def at(hhmm):
    return datetime.fromisoformat("2026-11-21T%s:00" % hhmm).timestamp()


class Base(unittest.TestCase):
    def setUp(self):
        self.t = {"now": at("10:10")}
        self.ctx = rm.Ctx(tempfile.mkdtemp(), "en", live=False, clock=lambda: self.t["now"])
        rm.save_json(self.ctx.library_path, {"entries": [], "rejected": []})

    def cycle(self, faults):
        probes = {d["id"]: ([False] * 3 if d["id"] in faults else [True] * 3) for d in DEVS}
        f = {k: {"message": "can't join meeting, panel frozen", "fixes": v, "evidence": EVID} for k, v in faults.items()}
        return orch.run_cycle(self.ctx, DEVS, probes, f)


class Meetings(Base):
    def test_at_risk_room_raises_priority_and_names_a_free_room(self):
        rep = self.cycle({"AV-5F-502": []})  # QBR in 5F-502 at 10:30, 20 min away
        m = next(x for x in rep["meetings"] if x["id"] == "MTG-2")
        self.assertEqual(m["state"], "at_risk")
        self.assertEqual(m["action"], "watch", "20 min out: warn, do not move yet")
        self.assertEqual(m["alternative"], "AV-3F-301", "2F-201 is booked at 11:00, so it is not offered")
        tk = rm.tickets_load(self.ctx)["tickets"][m["ticket"]]
        self.assertEqual(tk["priority"], "2 - High")
        self.assertIn("meeting_risk", [n["kind"] for n in rep["notifications"]])

    def test_close_to_start_it_recommends_moving(self):
        self.t["now"] = at("10:50")
        rep = self.cycle({"AV-2F-201": []})
        m = next(x for x in rep["meetings"] if x["id"] == "MTG-3")
        self.assertEqual((m["state"], m["action"]), ("at_risk", "move"))
        self.assertIn("room_move", [n["kind"] for n in rep["notifications"]])

    def test_fixed_before_the_meeting(self):
        rep = self.cycle({"AV-5F-502": ["restart-room-app"]})
        m = next(x for x in rep["meetings"] if x["id"] == "MTG-2")
        self.assertEqual(m["state"], "fixed")


class KbDrafts(Base):
    def _attempt(self, target, ok, held):
        rm.append_jsonl(self.ctx.attempts_path, {"ts": self.ctx.ts(), "target": target, "device": "av", "symptom": "hung", "action": "reboot-codec",
                                                 "outcome": "ran", "verified": ok, "confirmed": held})

    def test_needs_two_fixes_that_held(self):
        self._attempt("AV-1", True, True)
        self.assertEqual(kbdraft.run(self.ctx)[0], [])
        self._attempt("AV-2", True, None)
        self.assertEqual(kbdraft.run(self.ctx)[0], [], "not yet re-checked does not count")
        self._attempt("AV-3", True, True)
        new, msgs = kbdraft.run(self.ctx)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["status"], "draft")
        self.assertEqual(kbdraft.run(self.ctx)[0], [], "written once")


class Chat(Base):
    def test_non_approver_cannot_approve(self):
        self.cycle({"AV-5F-502": []})
        r = chatops.handle(self.ctx, "Marco Ruiz (AV)", "approve the profile reset on 5F-502")
        self.assertFalse(r["ok"])
        self.assertEqual(rm.load_json(os.path.join(self.ctx.dir, "approvals.json"), {}), {})

    def test_approval_is_for_one_device_and_used_once(self):
        # a fix learned from email, not yet proven here: medium risk, so it needs approval
        rm.save_json(self.ctx.library_path, {"rejected": [], "entries": [{"id": "CL-1", "device": "av", "symptom": "hung", "action": "reset-room-profile",
                     "status": "verified", "verified": 1, "failed": 0, "kind": "auto", "text": "reset the profile", "sources": []}]})
        self.cycle({"AV-5F-502": [], "AV-2F-201": []})
        r = chatops.handle(self.ctx, "Chen Wei (AV lead)", "批准 5F-502 重置配置")
        self.assertTrue(r["ok"])
        self.t["now"] = at("10:50")
        rep = self.cycle({"AV-5F-502": ["reset-room-profile"], "AV-2F-201": ["reset-room-profile"]})
        r5 = next(x for x in rep["results"] if x["ci"] == "AV-5F-502")
        r2 = next(x for x in rep["results"] if x["ci"] == "AV-2F-201")
        self.assertTrue(r5["resolved"])
        self.assertFalse(any(t["action"] == "reset-room-profile" and t["decision"] == "run" for t in r2["trace"]), "not approved for 2F-201")
        self.assertEqual(rm.load_json(os.path.join(self.ctx.dir, "approvals.json"), {}), {}, "used up")

    def test_status_and_kill_switch(self):
        self.cycle({"AV-5F-502": []})
        r = chatops.handle(self.ctx, "Anyone", "what's wrong with 5F-502?")
        self.assertIn("AV-5F-502", r["reply"]["en"])
        self.assertFalse(chatops.handle(self.ctx, "Anyone", "stop automatic repairs")["ok"])
        self.assertTrue(chatops.handle(self.ctx, "Chen Wei (AV lead)", "stop automatic repairs")["ok"])
        self.assertIsNotNone(rm.kill_state(self.ctx))
        chatops.handle(self.ctx, "Chen Wei (AV lead)", "resume automatic repairs")
        self.assertIsNone(rm.kill_state(self.ctx))


if __name__ == "__main__":
    unittest.main(verbosity=2)
