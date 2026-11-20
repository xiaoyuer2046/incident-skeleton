#!/usr/bin/env python3
"""Guardrail tests: a badly behaved AI must not be able to change what the engine does.

    python3 skill/tests/test_brain_guardrails.py
"""
import argparse, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REM = os.path.join(HERE, "..", "remediation")
sys.path.insert(0, REM)

FAKE = r'''
import json, sys, os
req = json.load(sys.stdin)
mode = os.environ["FAKE_MODE"]
if mode == "garbage":
    print("sure! here is what I think: reboot everything")
elif mode == "bad_ids":
    print(json.dumps({"suggestions": [{"action_id": "rm -rf /", "why": "x"}, {"action_id": "format-disk", "why": "y"},
                                      {"action_id": "add-ap", "why": "physical"}, {"action_id": "rf-tune", "why": "ok" * 500}]}))
elif mode == "not_allowed":
    print(json.dumps({"suggestions": [{"action_id": "add-ap", "why": "physical step"}]}))
elif mode == "boom":
    raise SystemExit(3)
'''


def ns(**kw):
    d = dict(type="wifiap", target="AP-T", ci="AP-T", source="test", message="AP offline", message_zh=None)
    d.update(kw)
    return argparse.Namespace(**d)


EVID = [{"check": "ping", "result": "no reply", "status": "err"}]


class Guardrails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fake = os.path.join(self.tmp, "fake_ai.py")
        open(fake, "w").write(FAKE)
        os.environ["BRAIN"] = "cmd"
        os.environ["INCIDENT_AI_CMD"] = "%s %s" % (sys.executable, fake)
        import importlib, brain, remediate
        importlib.reload(brain)
        self.brain, self.rm = brain, importlib.reload(remediate)
        self.ctx = self.rm.Ctx(os.path.join(self.tmp, "data"), "en", live=False)
        self.rm.save_json(self.ctx.library_path, {"entries": [], "rejected": []})

    def ask(self, mode):
        os.environ["FAKE_MODE"] = mode
        self.brain._cache.clear()
        return self.brain.ask(self.ctx, "suggest_actions", {"allowed_actions": ["controller-reboot-ap", "poe-cycle", "rf-tune", "add-ap"], "evidence": EVID})

    def test_non_json_is_dropped(self):
        self.assertIsNone(self.ask("garbage"))

    def test_unknown_ids_are_dropped_and_text_capped(self):
        out = self.ask("bad_ids")
        ids = [s["action_id"] for s in out["suggestions"]]
        self.assertNotIn("rm -rf /", ids)
        self.assertNotIn("format-disk", ids)
        self.assertTrue(all(len(s["why"]) <= self.brain.MAX_TEXT for s in out["suggestions"]))

    def test_crash_falls_back_to_rules(self):
        self.assertIsNone(self.ask("boom"))
        os.environ["FAKE_MODE"] = "boom"
        res = self.rm.remediate(ns(), self.ctx, scenario=set(), evidence=EVID, quiet=True)
        self.assertTrue(res["attempts"], "the rules still ran the builtin runbook")

    def test_ai_cannot_make_a_physical_step_automatic(self):
        os.environ["FAKE_MODE"] = "not_allowed"
        self.brain._cache.clear()
        res = self.rm.remediate(ns(), self.ctx, scenario=set(), evidence=EVID, quiet=True)
        step = next(t for t in res["trace"] if t["action"] == "add-ap")
        self.assertIn("ai", step["sources"])
        self.assertEqual(step["decision"], "needs_human")

    def test_every_call_is_audited_without_payload_text(self):
        self.ask("bad_ids")
        rows = [json.loads(l) for l in open(os.path.join(self.ctx.dir, "brain_audit.jsonl"))]
        self.assertTrue(rows)
        self.assertNotIn("no reply", json.dumps(rows))

    def test_budget_cap(self):
        os.environ["BRAIN_MAX_CALLS"] = "0"
        self.brain._calls["n"] = 0
        try:
            self.assertIsNone(self.ask("bad_ids"))
        finally:
            del os.environ["BRAIN_MAX_CALLS"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
