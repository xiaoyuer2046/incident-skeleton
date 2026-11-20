#!/usr/bin/env python3
"""Safety tests: kill switch, daily limit, delayed re-check, self-heal, notifications.

    python3 skill/tests/test_safety.py
"""
import argparse, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "remediation"))
os.environ["BRAIN"] = "off"
import remediate as rm
import orchestrator as orch
import notify

EVID = [{"check": "ping", "result": "no reply", "status": "err"}]


def ns(target="PRN-T"):
    return argparse.Namespace(type="printer", target=target, ci=target, source="t", message="PAPER JAM (13.20)", message_zh=None)


class Safety(unittest.TestCase):
    def setUp(self):
        self.t = {"now": 1795000000.0}
        self.ctx = rm.Ctx(tempfile.mkdtemp(), "en", live=False, clock=lambda: self.t["now"])
        rm.save_json(self.ctx.library_path, {"entries": [], "rejected": []})

    def run_one(self, fixes, target="PRN-T"):
        return rm.remediate(ns(target), self.ctx, scenario=set(fixes), evidence=EVID, quiet=True)

    def test_kill_switch_blocks_every_action(self):
        rm.save_json(os.path.join(self.ctx.dir, "STOP"), {"by": "tester"})
        res = self.run_one(["restart-spooler"])
        self.assertFalse(res["attempts"], "nothing may run while the kill switch is on")
        self.assertTrue(any(t["decision"] == "killed" for t in res["trace"]))
        self.assertEqual(res["ticket"]["event"], "created", "it still escalates to a person")

    def test_daily_limit(self):
        for i in range(6):
            rm.append_jsonl(self.ctx.attempts_path, {"ts": self.ctx.ts(), "target": "PRN-T", "outcome": "ran", "device": "printer",
                                                     "symptom": "jam", "action": "x", "verified": False})
        res = self.run_one(["restart-spooler"])
        self.assertFalse(res["attempts"])
        self.assertTrue(any(t["decision"] == "rate_limited" for t in res["trace"]))

    def test_recheck_turns_a_fix_that_did_not_hold_into_a_failure(self):
        res = self.run_one(["restart-spooler"])
        self.assertTrue(res["resolved"])
        self.assertEqual(rm.stats(self.ctx)[("printer", "jam", "restart-spooler")]["successes"], 1)
        self.t["now"] += 5 * 60
        self.assertEqual(rm.recheck(self.ctx, {"PRN-T": "confirmed"}), [], "not due yet")
        self.t["now"] += 6 * 60
        out = rm.recheck(self.ctx, {"PRN-T": "confirmed"})
        self.assertEqual(out[0]["held"], False)
        self.assertEqual(rm.stats(self.ctx)[("printer", "jam", "restart-spooler")]["successes"], 0)

    def test_recheck_confirms_a_fix_that_held(self):
        self.run_one(["restart-spooler"])
        self.t["now"] += 11 * 60
        self.assertEqual(rm.recheck(self.ctx, {"PRN-T": "healthy"})[0]["held"], True)
        self.assertEqual(rm.recheck(self.ctx, {"PRN-T": "confirmed"}), [], "a confirmed fix is not checked twice")

    def test_self_heal_is_not_repaired(self):
        self.assertEqual(orch.classify([False, False, True], 2), "self_healed")
        self.assertEqual(orch.classify([False, False, False], 2), "confirmed")
        self.assertEqual(orch.classify([True, False, True], 2), "blip")

    def test_notifications_are_sent_once_and_routed(self):
        devs = [{"id": "PRN-T", "type": "printer"}]
        faults = {"PRN-T": {"message": "PAPER JAM (13.20)", "fixes": [], "evidence": EVID}}
        rep = orch.run_cycle(self.ctx, devs, {"PRN-T": [False] * 3}, faults)
        kinds = [n["kind"] for n in rep["notifications"]]
        self.assertIn("failed", kinds)
        failed = next(n for n in rep["notifications"] if n["kind"] == "failed")
        self.assertEqual(failed["channels"], ["Teams · IT on-call"], "Slack only gets outage news")
        self.assertTrue(failed["dry_run"])
        self.t["now"] += 10 * 60
        rep2 = orch.run_cycle(self.ctx, devs, {"PRN-T": [False] * 3}, faults)
        self.assertNotIn("failed", [n["kind"] for n in rep2["notifications"]], "an open ticket is not announced twice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
