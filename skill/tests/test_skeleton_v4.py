#!/usr/bin/env python3
"""Acceptance tests for the v4 shared runtime and both apps (requirements 1, 2, 3, 5, 6, 8, 9).

    python skill/tests/test_skeleton_v4.py
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(SKILL, ".."))
sys.path.insert(0, SKILL)
os.environ["BRAIN"] = "off"

from skeleton_v4 import app_devices, app_servicedesk, plugins, run, simulate, skeleton  # noqa: E402
from skeleton_v4.learning import Learning, load_sources  # noqa: E402
from integration_v31.plugins import GlobalGate  # noqa: E402
import remediate as rm  # noqa: E402
import desk  # noqa: E402

RUNTIME = os.path.join(SKILL, "skeleton_v4", "skeleton.py")
GUARDED = [os.path.join(SKILL, "remediation", n) for n in ("policy.json", "actions.json", "runbooks.json")] + \
          [os.path.join(SKILL, "apps", "servicedesk", n) for n in ("policy.json", "app.json", "actions.json", "runbooks.json")]
DIRX = rm.load_json(os.path.join(SKILL, "apps", "servicedesk", "data", "directory.json"), {})
REQS = {r["id"]: r for r in rm.load_json(os.path.join(SKILL, "integration_v31", "requests_v31.json"), [])}
REQS.update({r["id"]: r for r in rm.load_json(os.path.join(SKILL, "apps", "servicedesk", "data", "requests.json"), [])})
STEPS = ["RECEIVE", "TRIAGE", "INVESTIGATE", "MITIGATE", "RESOLVE", "LOG"]
at = lambda ts: datetime.fromisoformat(ts).timestamp()  # noqa: E731


def digest(paths):
    out = {}
    for p in paths:
        with open(p, "rb") as handle:
            out[p] = hashlib.sha256(handle.read()).hexdigest()
    return out


class SpyGate(GlobalGate):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.asked = []

    def check(self, text):
        self.asked.append(text)
        return super().check(text)


class Base(unittest.TestCase):
    cycles = 3

    def setUp(self):
        self.box = {"now": at("2026-11-21T09:25:00")}
        clock = lambda: self.box["now"]  # noqa: E731
        self.tmp = tempfile.TemporaryDirectory(prefix="v4test-")
        self.addCleanup(self.tmp.cleanup)
        self.d1 = app_devices.make_ctx(os.path.join(self.tmp.name, "dev"), "en", clock)
        self.d2 = app_servicedesk.make_ctx(os.path.join(self.tmp.name, "desk"), "en", clock)
        self.office = rm.Ctx(os.path.join(self.tmp.name, "office"), "en", live=False, clock=clock, ticket_prefix="INC", ticket_start=10000)
        os.makedirs(self.office.dir, exist_ok=True)
        rm.save_json(os.path.join(self.office.dir, "board.json"), run.BOARD)
        self.gate = SpyGate()
        self.gate.advance(self.cycles)
        self.learning = Learning()
        self.a1 = app_devices.DevicesAdapter()
        self.a2 = app_servicedesk.ServiceDeskAdapter(DIRX, self.office)

    def desk(self, req, gate=True, learn=False, **over):
        item = dict(REQS[req] if isinstance(req, str) else req, **over)
        slots = plugins.build(self.gate if gate else None, self.learning if learn else None, "servicedesk")
        return skeleton.run(item, self.a2, slots, self.d2)

    def dev(self, dev, fault, gate=True, learn=False, recheck=None):
        slots = plugins.build(self.gate if gate else None, self.learning if learn else None, "devices")
        return skeleton.run(app_devices.item_from(dev, fault, recheck), self.a1, slots, self.d1)

    @staticmethod
    def step(rec, name):
        return next(s for s in rec["steps"] if s["name"] == name)


class TestRuntime(Base):
    """Requirement 1"""

    def test_1_1_both_apps_run_through_the_one_runtime(self):
        with mock.patch.object(skeleton, "run", wraps=skeleton.run) as spy:
            data = run.build()
        self.assertEqual(len(data["rows"]), 7)
        self.assertEqual({r["app"] for r in data["items"]}, {"devices", "servicedesk"})
        # the real call path of both apps: each record was produced by skeleton.run (patched name is the one run.py calls)
        self.assertEqual(spy.call_count, 7)

    def test_1_2_exactly_six_steps_in_order_for_every_outcome(self):
        recs = [self.desk("V31-01"), self.desk("V31-09"), self.desk("V31-04"), self.dev(run.AP, run.AP_FAULT),
                self.dev(run.AV, run.AV_FAULT), self.desk("REQ-03")]
        for rec in recs:
            self.assertEqual([s["name"] for s in rec["steps"]], STEPS)
            self.assertEqual([s["kind"] for s in rec["steps"]], [skeleton.KIND[n] for n in STEPS])
        self.assertEqual(skeleton.STEPS, tuple(STEPS))

    def test_1_3_adapter_supplies_only_intake_crew_investigate_mitigate(self):
        for ad in (self.a1, self.a2):
            for name in ("receive", "safety", "known_link", "select_crew", "investigate", "mitigate", "resolve", "log"):
                self.assertTrue(callable(getattr(ad, name)))
        # the adapters hold no step list and no plug-in logic
        for mod in (app_devices, app_servicedesk):
            src = open(mod.__file__, encoding="utf-8").read()
            self.assertNotIn("triage_gate", src)
            self.assertNotIn("GlobalGate", src)

    def test_1_4_plugins_attach_only_to_named_slots(self):
        self.assertEqual(skeleton.SLOTS, ("triage_gate", "mitigate_rank", "log_learn"))
        with self.assertRaises(ValueError):
            skeleton.run(app_devices.item_from(run.AP, run.AP_FAULT), self.a1, {"extra_step": lambda *a: None}, self.d1)

    def test_1_5_plugins_cannot_add_remove_or_reorder_steps(self):
        evil = {"triage_gate": lambda item, ctx: {"en": "gate note", "zh": "闸门备注", "steps": ["LOG"]},
                "mitigate_rank": lambda item, crew, ctx: {"steps": [], "order": ["LOG", "RECEIVE"], "hints": {}, "narrow": {}, "notes": []},
                "log_learn": lambda item, result, ctx: {"en": "learned", "zh": "已学习", "steps": []}}
        rec = skeleton.run(app_devices.item_from(run.AP, run.AP_FAULT), self.a1, evil, self.d1)
        self.assertEqual([s["name"] for s in rec["steps"]], STEPS)
        self.assertEqual({s["name"]: s["slot"] for s in rec["steps"] if s["slot"]}, {"TRIAGE": "triage_gate", "LOG": "log_learn"})

    def test_1_6_short_circuits_still_record_six_steps_with_reasons(self):
        for rec, outcome in ((self.desk("V31-09"), "rejected"), (self.desk("V31-01"), "linked_vendor"), (self.desk("REQ-03"), "linked_known")):
            self.assertEqual(rec["outcome"], outcome)
            self.assertEqual([s["name"] for s in rec["steps"]], STEPS)
            late = rec["steps"][2:]
            self.assertTrue(all(s["status"] == "skipped" and s["en"] and s["zh"] for s in late), outcome)
            self.assertEqual(rec["steps"][1]["status"], "done")
        self.assertEqual(self.step(self.desk("V31-04", gate=False), "INVESTIGATE")["status"], "done")

    def test_1_7_a_third_app_needs_only_an_adapter(self):
        before = digest([RUNTIME])

        class NotesAdapter:  # the whole third app: no runtime change, no other file
            app = "notes"
            crews = {"memo": {"en": "Memo", "zh": "备忘"}}

            def receive(self, item, ctx): return {"en": "A note arrived", "zh": "收到一条笔记"}
            def safety(self, item, ctx): return skeleton.Stop("rejected", "Rejected: empty.", "拒绝：为空。") if not item["text"] else None
            def known_link(self, item, ctx): return None
            def select_crew(self, item, ctx): return "memo"
            def investigate(self, item, crew, ctx): return {"en": "Read the note", "zh": "读了笔记"}

            def mitigate(self, item, crew, plan, ctx):
                self.seen = list(ctx.policy["allow"]["memo"])
                return {"en": "Wrote a copy", "zh": "写了副本", "outcome": "resolved"}

            def resolve(self, item, result, ctx): return {"en": "Done", "zh": "完成"}
            def log(self, item, result, ctx): return {"en": "Logged", "zh": "已记录"}

        ad = NotesAdapter()
        ctx = SimpleNamespace(policy={"allow": {"memo": ["write-note", "delete-note"]}})
        slots = {"mitigate_rank": lambda item, crew, c: {"narrow": {"memo": ["delete-note"]}, "hints": {}, "notes": []}}
        rec = skeleton.run({"id": "N1", "text": "hello", "title": {"en": "Note", "zh": "笔记"}}, ad, slots, ctx)
        self.assertEqual((rec["app"], rec["outcome"], rec["crew"]), ("notes", "resolved", "memo"))
        self.assertEqual([s["name"] for s in rec["steps"]], STEPS)
        self.assertEqual(ad.seen, ["write-note"])  # narrowed for the call
        self.assertEqual(ctx.policy["allow"]["memo"], ["write-note", "delete-note"])  # restored afterwards
        self.assertEqual(skeleton.run({"id": "N2", "text": ""}, ad, {}, ctx)["outcome"], "rejected")
        self.assertEqual(before, digest([RUNTIME]))

    def test_1_runtime_is_small_and_knows_no_app(self):
        src = open(RUNTIME, encoding="utf-8").read().replace("linked_vendor", "")  # an outcome name from the record contract
        self.assertLess(len(src.splitlines()), 150)
        for word in ("printer", "signage", "wifi", "teams", "meraki", "servicenow", "microsoft", "cisco", "outlook", "vendor", "ticket"):
            self.assertNotIn(word, src.lower(), word)


class TestApps(Base):
    """Requirement 2"""

    def test_2_1_devices_four_crews_reuse_v1_repair(self):
        self.assertEqual(set(app_devices.CREWS), {"printer", "signage", "av", "wifiap"})
        rec = self.dev({"id": "PRN-1", "type": "printer", "loc": {"en": "Floor 2", "zh": "二楼"}}, {"message": "Printer paper jam, jobs stuck", "fixes": ["clear-queue"]}, gate=False)
        self.assertEqual((rec["outcome"], rec["crew"]), ("local_repair", "printer"))
        self.assertTrue(os.path.exists(self.d1.attempts_path))
        ran = [r["action"] for r in rm.read_jsonl(self.d1.attempts_path)]
        self.assertTrue(ran and all(a in self.d1.actions for a in ran))
        for dev, msg, fix in (("signage", "Signage black screen", "clear-player-cache"), ("wifiap", "Wi-Fi access point offline", "controller-reboot-ap"),
                              ("av", "Room panel frozen", "reboot-codec")):
            r = self.dev({"id": dev.upper() + "-9", "type": dev}, {"message": msg, "fixes": [fix]}, gate=False)
            self.assertEqual(r["crew"], dev)

    def test_2_2_servicedesk_four_crews(self):
        self.assertEqual(set(app_servicedesk.CREWS), {"account", "vpn", "email", "software"})
        for rid, crew in (("REQ-01", "account"), ("REQ-02", "vpn"), ("REQ-05", "email"), ("REQ-07", "software")):
            self.assertEqual(self.desk(rid, gate=False)["crew"], crew)

    def test_2_3_v1_behaviour_holds(self):
        self.assertEqual(self.desk("REQ-09")["outcome"], "rejected")
        self.assertEqual(self.desk("V31-09")["outcome"], "rejected")
        self.assertEqual(self.desk("REQ-01", id="X9", text="Please make me local admin on my laptop")["outcome"], "rejected")
        self.assertEqual(self.desk("REQ-03")["outcome"], "linked_known")
        self.assertEqual(self.desk("REQ-01", gate=False)["outcome"], "resolved")
        mfa = self.desk("REQ-08", gate=False)
        self.assertEqual(mfa["outcome"], "on_hold")
        tk = rm.tickets_load(self.d2)["tickets"]
        self.assertTrue(any("reset-mfa" in (t.get("awaiting_approval") or []) for t in tk.values()))
        self.assertEqual(self.desk("REQ-07", gate=False)["outcome"], "escalated")

    def test_2_4_teams_and_outlook_are_recognised(self):
        self.assertEqual(app_servicedesk.crew_for("Teams keeps spinning"), "account")
        self.assertEqual(app_servicedesk.crew_for("My Outlook says disconnected"), "email")
        self.assertIsNone(app_servicedesk.crew_for("hello there"))
        self.assertNotIn("teams", json.dumps(desk.CFG["crews"]).lower())  # v1 app.json really has no Teams keyword
        self.assertEqual(self.desk("V31-04", gate=False)["crew"], "account")


class TestSafetyOrder(Base):
    """Requirement 3"""

    def test_3_1_safety_runs_first_the_gate_is_never_asked(self):
        rec = self.desk("V31-09")  # names Teams, but it is an injection
        self.assertEqual(rec["outcome"], "rejected")
        self.assertEqual(self.gate.asked, [])
        self.assertIsNone(self.step(rec, "TRIAGE")["slot"])
        self.assertFalse(os.path.exists(self.d2.attempts_path))

    def test_3_2_and_3_3_gate_second_known_link_third_crew_last(self):
        calls = []
        real_known, real_crew = self.a2.known_link, self.a2.select_crew
        self.a2.known_link = lambda i, c: (calls.append("known"), real_known(i, c))[1]
        self.a2.select_crew = lambda i, c: (calls.append("crew"), real_crew(i, c))[1]
        orig = self.gate.check
        self.gate.check = lambda text: (calls.append("gate"), orig(text))[1]
        self.desk("V31-04", text="I can't sign in, my account is locked.")
        self.assertEqual(calls, ["gate", "known", "crew"])
        calls.clear()
        self.desk("V31-01")  # the gate links first: no known-link check, no crew
        self.assertEqual(calls, ["gate"])
        calls.clear()
        self.desk("REQ-03")  # known link wins before a crew is chosen
        self.assertEqual(calls, ["gate", "known"])


class TestPermission(Base):
    """Requirement 5 and 9"""

    def test_5_narrowing_only_removes_and_restores(self):
        ctx = self.d1
        before = json.dumps(ctx.policy, sort_keys=True)
        with skeleton.narrowed(ctx, {"wifiap": ["poe-cycle"], "*": ["no-such-action"], "nowhere": ["x"]}) as pol:
            for crew, allowed in pol["allow"].items():
                self.assertTrue(set(allowed) <= set(rm.load_json(os.path.join(SKILL, "remediation", "policy.json"), {})["allow"][crew]))
            self.assertNotIn("poe-cycle", pol["allow"]["wifiap"])
        self.assertEqual(before, json.dumps(ctx.policy, sort_keys=True))

    def test_5_full_run_leaves_permission_files_byte_identical(self):
        before = digest(GUARDED)
        simulate.build()
        self.assertEqual(before, digest(GUARDED))

    def test_5_paused_method_is_out_of_the_allow_list_during_the_repair(self):
        self.learning.cycle(load_sources())
        rec = self.dev(run.AP, dict(run.AP_FAULT, fixes=[]), learn=True)  # nothing works: every allowed action is tried
        tried = [r["action"] for r in rm.read_jsonl(self.d1.attempts_path)]
        self.assertNotIn("poe-cycle", tried)
        self.assertIn("rf-tune", tried)
        self.assertIn("poe-cycle", self.d1.policy["allow"]["wifiap"], "restored after the call")
        self.assertTrue(any("Paused" in n["en"] for n in rec["learning_used"]))

    def test_5_physical_actions_never_become_automatic(self):
        lg = Learning()
        lg.watch({"source": "vendor_mcp", "ref": "P1", "updated_at": "2026-11-21T08:00:00Z", "app": "devices", "device": "printer", "symptom": "jam",
                  "action": "clear-jam", "text": "Clear the jam by hand."})
        m = lg.method("devices", "printer", "jam", "clear-jam")
        self.assertTrue(m["policy_effect"]["physical"])
        self.assertFalse(m["policy_effect"]["automatic"])
        for i in range(3):
            lg.absorb_attempt("devices", {"ts": "t%d" % i, "device": "printer", "symptom": "jam", "action": "clear-jam", "confirmed": True, "outcome": "ran"})
        self.assertEqual(lg.method("devices", "printer", "jam", "clear-jam")["state"], "promoted")
        self.assertEqual(lg.view("devices", "printer", "jam")["hints"], {})  # never a hint, never automatic

    def test_9_everything_is_dry_run(self):
        data = run.build()
        self.assertTrue(all(r["dry_run"] for r in data["items"]))
        self.assertTrue(all(c["dry_run"] and "DRY-RUN" in c["reply"]["en"] and "演练" in c["reply"]["zh"] for c in data["closures"]))
        self.assertTrue(all(n.get("dry_run", True) for n in data["learning"].notices))
        self.assertTrue(data["notifications"] is not None)
        for ctx in (self.d1, self.d2):
            self.assertEqual(ctx.policy.get("mode"), "dry-run")


class TestGateAndStory(Base):
    """Requirement 6 and the demo story"""

    def test_6_1_gate_reuses_the_v3_engine(self):
        from external_intelligence_v3.engine import GlobalIntelligenceEngine
        self.assertIsInstance(self.gate.engine, GlobalIntelligenceEngine)

    def test_6_2_teams_requests_and_room_share_one_parent_and_hold_actions(self):
        a, b = self.desk("V31-01"), self.desk("V31-02")
        room = self.dev(run.AV, run.AV_FAULT)
        self.assertEqual([r["outcome"] for r in (a, b, room)], ["linked_vendor"] * 3)
        self.assertEqual(a["parent"], b["parent"])
        self.assertEqual(a["parent"], room["parent"])
        held = " ".join(h["en"].lower() for h in a["held_actions"])
        self.assertIn("password reset", held)
        self.assertTrue(any("room app" in h["en"].lower() for h in room["held_actions"]))
        self.assertFalse(os.path.exists(self.d1.attempts_path) or os.path.exists(self.d2.attempts_path), "no useless repair ran")
        self.assertTrue(all(s["slot"] is None for s in a["steps"][2:]))

    def test_6_3_cisco_single_site_stays_local(self):
        rec = self.dev(run.AP, run.AP_FAULT)
        self.assertEqual(rec["outcome"], "local_repair")
        self.assertEqual(self.step(rec, "TRIAGE")["slot"], "triage_gate")
        self.assertEqual(rec["held_actions"], [])

    def test_6_4_vendor_and_internal_recovery_close_linked_items_with_dry_run_notice(self):
        self.desk("V31-01")
        self.dev(run.AV, run.AV_FAULT)
        self.gate.advance(5)
        from integration_v31 import desk_v31
        c2, _ = desk_v31.close_vendor_linked(self.d2, self.gate, app="servicedesk")
        c1, _ = desk_v31.close_vendor_linked(self.d1, self.gate, app="devices")
        self.assertEqual((len(c2), len(c1)), (1, 1))
        for c in c1 + c2:
            self.assertIn("DRY-RUN", c["reply"]["en"])
            self.assertIn("演练", c["reply"]["zh"])

    def test_story_runs_in_one_pass(self):
        data = run.build()
        outcomes = [r["outcome"] for r in data["items"]]
        self.assertEqual(outcomes, ["linked_vendor", "linked_vendor", "linked_vendor", "local_repair", "rejected", "linked_known", "resolved"])
        self.assertEqual(len(data["closures"]), 3)
        ap, outlook = data["items"][3], data["items"][6]
        self.assertTrue(any("tried first" in n["en"] for n in ap["learning_used"]))
        self.assertTrue(any("tried first" in n["en"] for n in outlook["learning_used"]))
        self.assertEqual(self.step(outlook, "LOG")["slot"], "log_learn")


class TestHook(unittest.TestCase):
    """Requirement 8.2"""

    def run_hook(self, payload):
        import subprocess
        home = tempfile.mkdtemp(prefix="v4hook-")
        proc = subprocess.run([sys.executable, os.path.join(SKILL, "hooks", "audit_incident.py")], input=payload, text=True, capture_output=True,
                              env=dict(os.environ, KIROCREW_HOME=home))
        log = os.path.join(home, "incident-audit.log")
        return proc.returncode, (open(log, encoding="utf-8").read() if os.path.exists(log) else "")

    def test_logs_a_postmortem_and_never_blocks(self):
        code, log = self.run_hook('{"tool_name":"shell","tool_input":{"command":"cat postmortem-printer-1.md"}}')
        self.assertEqual(code, 0)
        self.assertIn("postmortem written", log)
        self.assertEqual(self.run_hook('{"tool_name":"shell"}'), (0, ""))
        self.assertEqual(self.run_hook("\x00 not json")[0], 0)


class TestDemoData(unittest.TestCase):
    """Design section 6"""

    @classmethod
    def setUpClass(cls):
        cls.data = simulate.build()

    def test_contract(self):
        d = self.data
        simulate.validate(d)
        self.assertEqual(d["runtime"]["lines"], len(open(RUNTIME, encoding="utf-8").read().splitlines()))
        self.assertEqual([a["id"] for a in d["apps"]], ["devices", "servicedesk"])
        self.assertEqual(d["summary"]["items"], len(d["items"]))
        self.assertEqual(d["summary"]["held_actions"], sum(len(i["held_actions"]) for i in d["items"]))
        for key in ("tiers", "events", "versions", "rejected", "held_back"):
            self.assertTrue(d["learning"][key], key)

    def test_no_raw_codes_in_shown_text(self):
        shown = []

        def walk(node, key=None):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, k)
            elif isinstance(node, list):
                for v in node:
                    walk(v, key)
            elif isinstance(node, str) and key in ("en", "zh"):
                shown.append(node)
        for part in ("items", "closures", "learning"):
            walk(self.data[part])
        shown += [s for a in self.data["apps"] for s in (a["label"]["en"], a["label"]["zh"])]
        codes = set(rm.load_json(os.path.join(SKILL, "remediation", "actions.json"), {})) | set(rm.load_json(os.path.join(SKILL, "apps", "servicedesk", "actions.json"), {}))
        codes |= {"linked_vendor", "linked_known", "local_repair", "on_hold", "held_back", "needs_corroboration", "advisory_harmful", "source_change", "wifiap", "servicedesk"}
        for text in shown:
            for code in codes:
                self.assertNotIn(code, text, text)
            self.assertIsNone(re.search(r"\bINC\d{4,}", text), text)

    def test_shipped_file_matches_a_fresh_run(self):
        path = os.path.join(ROOT, "demo", "data", "skeleton-v4.js")
        text = open(path, encoding="utf-8").read()
        shipped = json.loads(text[text.index("=") + 1:].strip().rstrip(";"))
        self.assertEqual(shipped, self.data)


if __name__ == "__main__":
    unittest.main(verbosity=1)
