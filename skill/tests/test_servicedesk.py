#!/usr/bin/env python3
"""Tests for app 2, service desk L1 triage, on the shared skeleton.

    python3 skill/tests/test_servicedesk.py
"""
import os, sys, tempfile, unittest
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REM = os.path.join(HERE, "..", "remediation")
APP = os.path.join(HERE, "..", "apps", "servicedesk")
sys.path.insert(0, REM)
sys.path.insert(0, APP)
os.environ["BRAIN"] = "off"
import remediate as rm
import orchestrator as orch
import desk

at = lambda h: datetime.fromisoformat("2026-11-21T%s:00" % h).timestamp()
DIRX = rm.load_json(os.path.join(APP, "data", "directory.json"), {})
REQS = {r["id"]: r for r in rm.load_json(os.path.join(APP, "data", "requests.json"), [])}
STEPS = ["RECEIVE", "TRIAGE", "INVESTIGATE", "MITIGATE", "RESOLVE", "LOG"]


class Base(unittest.TestCase):
    def setUp(self):
        self.t = {"now": at("10:00")}
        clock = lambda: self.t["now"]
        self.office = rm.Ctx(tempfile.mkdtemp(), "en", live=False, clock=clock, ticket_prefix="INC", ticket_start=10000)
        self.ctx = desk.ctx_for(tempfile.mkdtemp(), "en", clock=clock)

    def run_req(self, rid, office=None, **over):
        return desk.handle(self.ctx, office, dict(REQS[rid], **over), DIRX)[0]

    def ticket(self, num):
        return rm.tickets_load(self.ctx)["tickets"][num]


class TestTriage(Base):
    def test_injection_and_admin_rejected_never_run(self):
        rec = self.run_req("REQ-09")
        self.assertEqual(rec["outcome"], "rejected")
        self.assertEqual(rec["group"], "Security Operations")
        self.assertEqual(rec["trace"], [])
        self.assertFalse(os.path.exists(self.ctx.attempts_path))
        rec2 = self.run_req("REQ-01", id="X1", text="Please make me local admin on my laptop")
        self.assertEqual(rec2["outcome"], "rejected")

    def test_locked_account_resolved_at_l1(self):
        rec = self.run_req("REQ-01")
        self.assertEqual(rec["outcome"], "resolved")
        self.assertEqual([s["name"] for s in rec["states"]], STEPS)
        self.assertEqual(self.ticket(rec["ticket"])["state"], "Resolved")
        self.assertTrue(rec["reply"]["zh"])

    def test_mfa_reset_waits_for_approval(self):
        rec = self.run_req("REQ-08")
        self.assertEqual(rec["outcome"], "on_hold")
        tk = self.ticket(rec["ticket"])
        self.assertEqual(tk["state"], "On Hold")
        self.assertIn("reset-mfa", tk["awaiting_approval"])
        self.assertEqual(tk["assignment_group"], "Identity & Access")

    def test_buying_a_license_needs_a_person(self):
        rec = self.run_req("REQ-07")
        self.assertEqual(rec["outcome"], "escalated")
        self.assertTrue(any(t["action"] == "buy-license" and t["decision"] == "needs_human" for t in rec["trace"]))
        self.assertEqual(rec["group"], "End-user Computing")

    def test_dry_run_only(self):
        rec = self.run_req("REQ-05")
        ran = [t for t in rec["trace"] if t["decision"] == "run"]
        self.assertTrue(ran and all(t["output"].startswith("[dry-run]") for t in ran))


class TestLinking(Base):
    def test_report_about_known_device_links_then_closes_with_it(self):
        devs = [{"id": "AV-5F-502", "type": "av"}]
        orch.run_cycle(self.office, devs, {"AV-5F-502": [False] * 3},
                       {"AV-5F-502": {"message": "room panel frozen", "fixes": [],
                                      "evidence": [{"check": "ping", "result": "no reply", "status": "err"}]}})
        parent = rm.tickets_load(self.office)["by_key"]
        parent = next(v for k, v in parent.items() if "AV-5F-502" in k)
        rec = self.run_req("REQ-06", office=self.office)
        self.assertEqual(rec["outcome"], "linked")
        self.assertEqual(rec["link"]["ref"], parent)
        self.assertEqual(rec["trace"], [])  # nobody dispatched twice
        self.assertEqual(self.ticket(rec["ticket"])["state"], "On Hold")
        closed, _ = desk.close_linked(self.ctx, self.office)
        self.assertEqual(closed, [])
        key = next(k for k, v in rm.tickets_load(self.office)["by_key"].items() if v == parent)
        rm.ticket_resolve(self.office, key, "engineer", "engineer_resolved", {})
        closed, msgs = desk.close_linked(self.ctx, self.office)
        self.assertEqual([c["ticket"] for c in closed], [rec["ticket"]])
        self.assertEqual(self.ticket(rec["ticket"])["state"], "Resolved")
        self.assertEqual(msgs[0]["kind"], "hd_linked_closed")


if __name__ == "__main__":
    unittest.main(verbosity=1)
