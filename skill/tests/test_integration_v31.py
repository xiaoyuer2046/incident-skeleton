#!/usr/bin/env python3
"""Acceptance tests for v3.1: v2 and v3 plugged into the six-state skeleton (SPEC-v3.1 section 10).

    python skill/tests/test_integration_v31.py
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(SKILL, ".."))
sys.path.insert(0, SKILL)
os.environ["BRAIN"] = "off"

from integration_v31 import STATES, desk_v31, devices_v31, plugins, simulate  # noqa: E402
from integration_v31.plugins import rm, method_key  # noqa: E402

REQS = {r["id"]: r for r in rm.load_json(os.path.join(SKILL, "integration_v31", "requests_v31.json"), [])}
DIRX = rm.load_json(os.path.join(plugins.APP, "data", "directory.json"), {})
DEMO_JS = os.path.join(ROOT, "demo", "data", "integrated-v31.js")
GUARDED = [os.path.join(SKILL, "remediation", n) for n in ("policy.json", "actions.json", "runbooks.json")] + \
          [os.path.join(plugins.APP, n) for n in ("policy.json", "app.json", "actions.json", "runbooks.json")]
DATA_DIRS = [os.path.join(SKILL, "remediation", "data"), os.path.join(plugins.APP, "data")]
at = lambda ts: datetime.fromisoformat(ts).timestamp()  # noqa: E731


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def snapshot_data():
    snap = {}
    for base in DATA_DIRS:
        for folder, _, names in os.walk(base):
            for n in names:
                p = os.path.join(folder, n)
                st = os.stat(p)
                snap[p] = (st.st_size, st.st_mtime_ns)
    return snap


class SpyGate(plugins.GlobalGate):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.asked = []

    def check(self, text):
        self.asked.append(text)
        return super().check(text)


class Base(unittest.TestCase):
    cycles = 3  # v3 cycles processed: 3 = Microsoft confirmed, Cisco local

    def setUp(self):
        self.box = {"now": at("2026-11-21T09:25:00")}
        clock = lambda: self.box["now"]  # noqa: E731
        self.tmp = tempfile.TemporaryDirectory(prefix="v31test-")
        self.d2 = desk_v31.ctx_for(os.path.join(self.tmp.name, "desk"), "en", clock=clock)
        self.d1 = devices_v31.ctx_for(os.path.join(self.tmp.name, "dev"), "en", clock=clock)
        self.gate = SpyGate()
        self.gate.advance(self.cycles)
        self.evo = plugins.new_evolution()
        self.addCleanup(self.tmp.cleanup)

    def req(self, rid, gate=True, **over):
        rec, msgs = desk_v31.handle(self.d2, None, dict(REQS[rid], **over), DIRX, self.gate if gate else None)
        return rec

    def dev(self, dev, fault, gate=True, recheck=None):
        return devices_v31.handle(self.d1, dev, fault, self.gate if gate else None, self.evo, recheck)

    @staticmethod
    def state(rec, name):
        return next(s for s in rec["states"] if s["name"] == name)


AV = {"id": "AV-5F-502", "type": "av", "loc": {"en": "Room 5F-502", "zh": "5F-502 会议室"}}
AV_TEAMS = {"message": "Teams Rooms cannot join the meeting, panel frozen", "fixes": ["restart-room-app"]}
AV_PLAIN = {"message": "Room panel frozen, cannot start the display", "fixes": ["reboot-codec"]}
AP = {"id": "AP-4F-07", "type": "wifiap", "loc": {"en": "Floor 4 west", "zh": "四楼西侧"}}
AP_FAULT = {"message": "Wi-Fi access point offline, wireless clients cannot join", "fixes": ["poe-cycle"]}
SIG = {"id": "SIG-LOBBY-E", "type": "signage", "loc": {"en": "Lobby east", "zh": "大厅东侧"}}
SIG_FAULT = {"message": "Signage black screen, not updating", "fixes": ["clear-player-cache"]}


class TestAcceptance(Base):
    def test_01_teams_request_links_to_vendor_and_runs_no_crew(self):
        rec = self.req("V31-01")
        self.assertEqual(rec["outcome"], "linked_vendor")
        self.assertEqual(self.state(rec, "TRIAGE")["plugin"], "v3")
        self.assertIn("Teams", rec["parent"]["en"])
        self.assertIn("Skipped", self.state(rec, "INVESTIGATE")["en"])
        self.assertFalse(os.path.exists(self.d2.attempts_path), "no crew repair may run")
        tk = rm.tickets_load(self.d2)["tickets"][rec["ticket"]]
        self.assertEqual((tk["state"], tk["device"]), ("On Hold", "vendor-linked"))
        self.assertIn("confidence", rec["reply"]["en"])

    def test_02_password_reset_actions_are_held(self):
        rec = self.req("V31-01")
        self.assertTrue({"send-reset-link", "unlock-account", "reset-mfa"} <= set(rec["held_actions"]))
        self.assertTrue({"repair-app-install", "send-outlook-steps"} <= set(rec["held_actions"]))
        self.assertFalse(os.path.exists(self.d2.attempts_path))

    def test_03_outlook_links_to_outlook_incident(self):
        rec = self.req("V31-03")
        self.assertEqual(rec["outcome"], "linked_vendor")
        self.assertIn("Outlook", rec["parent"]["en"])
        self.assertIn("send-outlook-steps", rec["held_actions"])
        self.assertEqual(plugins.detect_service("Outlook 连不上邮箱"), ("microsoft", "outlook"))
        self.assertEqual(plugins.detect_service("会议软件打不开"), ("microsoft", "teams"))
        self.assertEqual(plugins.detect_service("无线网很慢"), ("cisco", "meraki"))

    def test_04_injection_and_admin_rejected_before_the_gate(self):
        rec = self.req("V31-09")  # the text names Teams, but safety runs first
        self.assertEqual(rec["outcome"], "rejected")
        self.assertEqual(self.gate.asked, [], "the v3 gate must not be asked")
        self.assertIsNone(self.state(rec, "TRIAGE")["plugin"])
        self.assertEqual(rec["held_actions"], [])
        admin = self.req("V31-04", text="Please give me admin rights so Teams works", user="ext")
        self.assertEqual(admin["outcome"], "rejected")
        self.assertEqual(self.gate.asked, [])
        self.assertFalse(os.path.exists(self.d2.attempts_path))

    def test_05_no_vendor_incident_teams_follows_v1_account_path(self):
        self.gate = SpyGate()  # no cycles: v3 knows nothing
        rec = self.req("V31-04")
        self.assertEqual(rec["outcome"], "resolved")
        self.assertIn("Account", self.state(rec, "TRIAGE")["en"])
        self.assertIsNone(self.state(rec, "TRIAGE")["plugin"])
        self.assertEqual(rec["held_actions"], [])
        self.assertTrue(os.path.exists(self.d2.attempts_path))

    def test_06_cisco_local_does_not_block_wifi_crew(self):
        verdict = self.gate.check("Wi-Fi on floor 3 is flaky")
        self.assertEqual(verdict["decision"], "local_issue_likely")
        self.assertFalse(verdict["link"])
        rec = self.dev(AP, AP_FAULT)
        self.assertEqual(rec["outcome"], "local_repair")
        self.assertEqual(self.state(rec, "TRIAGE")["plugin"], "v3")
        self.assertIn("Wireless AP crew", self.state(rec, "TRIAGE")["en"])
        self.assertEqual(rec["held_actions"], [])
        self.assertTrue(os.path.exists(self.d1.attempts_path))
        # the same on the service desk: a Wi-Fi request is not linked to a vendor
        wifi = self.req("V31-04", text="Wi-Fi is slow today, lunch break", user="li")
        self.assertNotEqual(wifi["outcome"], "linked_vendor")

    def test_07_teams_rooms_av_fault_is_held(self):
        rec = self.dev(AV, AV_TEAMS)
        self.assertEqual(rec["outcome"], "linked_vendor")
        self.assertIn("Teams", rec["parent"]["en"])
        self.assertIn("restart-room-app", rec["held_actions"])
        self.assertFalse(os.path.exists(self.d1.attempts_path), "device repair must not run")
        # the staff request and the room share one Microsoft parent
        staff = self.req("V31-01")
        self.assertEqual(rec["parent"], staff["parent"])
        # a frozen room panel with no Teams in the symptom follows the normal AV path
        plain = self.dev(AV, AV_PLAIN)
        self.assertEqual(plain["outcome"], "local_repair")

    def test_08_v2_adopted_method_is_passed_as_hint(self):
        simulate.prime_v2(self.evo)
        with mock.patch.object(rm, "remediate", wraps=rm.remediate) as spy:
            rec = self.dev(SIG, SIG_FAULT)
        hints = spy.call_args.kwargs["hints"]
        self.assertIn("clear-player-cache", hints)
        self.assertEqual(self.state(rec, "MITIGATE")["plugin"], "v2")
        first = [t for t in rm.read_jsonl(self.d1.attempts_path)][0]
        self.assertEqual(first["action"], "clear-player-cache")  # tried first
        self.assertEqual(first["tier"], "auto")                  # and still went through policy
        # without adoption there is no hint
        self.setUp()
        with mock.patch.object(rm, "remediate", wraps=rm.remediate) as spy2:
            self.dev(SIG, SIG_FAULT)
        self.assertIsNone(spy2.call_args.kwargs["hints"])

    def test_09_v2_paused_method_removed_only_from_memory_copy(self):
        key = method_key("av", "hung", "restart-room-app")
        for _ in range(3):
            self.evo.verify(key, False)
        self.assertEqual(self.evo.methods[key]["state"], "demoted")
        seen = {}
        real = rm.remediate

        def spy(ns, ctx, **kw):
            seen["allow"] = list(ctx.policy["allow"]["av"])
            seen["policy_obj"] = ctx.policy
            return real(ns, ctx, **kw)

        before = read_bytes(os.path.join(SKILL, "remediation", "policy.json"))
        original_policy = self.d1.policy
        with mock.patch.object(rm, "remediate", side_effect=spy):
            rec = self.dev(AV, AV_PLAIN, gate=False)
        self.assertNotIn("restart-room-app", seen["allow"])
        self.assertIn("restart-room-app", self.d1.policy["allow"]["av"])   # restored after the call
        self.assertIs(self.d1.policy, original_policy)
        self.assertIsNot(seen["policy_obj"], original_policy)             # it was a copy
        self.assertEqual(before, read_bytes(os.path.join(SKILL, "remediation", "policy.json")))
        self.assertEqual(self.state(rec, "MITIGATE")["plugin"], "v2")
        ran = [r["action"] for r in rm.read_jsonl(self.d1.attempts_path)]
        self.assertNotIn("restart-room-app", ran)

    def test_10_policy_and_app_bytes_unchanged_after_full_run(self):
        before = {p: read_bytes(p) for p in GUARDED}
        data_before = snapshot_data()
        simulate.build()
        for p, raw in before.items():
            self.assertEqual(raw, read_bytes(p), p)
        self.assertEqual(data_before, snapshot_data(), "v1 data folders must not be written")

    def test_11_no_paused_or_held_action_is_ever_added_to_an_allow_list(self):
        orig = {d: set(a) for d, a in rm.load_json(os.path.join(SKILL, "remediation", "policy.json"), {})["allow"].items()}
        orig.update({d: set(a) for d, a in rm.load_json(os.path.join(plugins.APP, "policy.json"), {})["allow"].items()})
        for n in (3, 4):  # n=4: Microsoft is recovering, hold still on but not linking
            self.setUp()
            self.gate = SpyGate()
            self.gate.advance(n)
            for _ in range(3):
                self.evo.verify(method_key("av", "hung", "restart-room-app"), False)
            captured = []
            real = rm.remediate

            def spy(ns, ctx, **kw):
                captured.append(copy.deepcopy(ctx.policy["allow"]))
                return real(ns, ctx, **kw)

            with mock.patch.object(rm, "remediate", side_effect=spy):
                self.req("V31-04")                    # Teams + locked account
                self.dev(AV, AV_PLAIN, gate=False)
                self.dev(SIG, SIG_FAULT)
            self.assertTrue(captured)
            for allow in captured:
                for device, ids in allow.items():
                    self.assertTrue(set(ids) <= orig[device], (device, ids))
            if n == 4:
                verdict = self.gate.check("Teams sign-in")
                self.assertFalse(verdict["link"])
                self.assertTrue(verdict["held_ids"])
                account_allow = next(a for a in captured if "account" in a)["account"]
                self.assertFalse(set(verdict["held_ids"]) & set(account_allow), "held actions leave the in-memory list")
        self.assertEqual(set(plugins.HELD_MAP), {"password reset", "Office reinstall"})

    def test_12_vendor_recovery_closes_linked_requests_with_bilingual_dry_run_notice(self):
        a = self.req("V31-01")
        room = self.dev(AV, AV_TEAMS)
        closures, msgs = desk_v31.close_vendor_linked(self.d2, self.gate)
        self.assertEqual(closures, [], "nothing closes while the vendor incident is active")
        self.gate.advance(5)
        self.box["now"] = at("2026-11-21T09:42:00")
        closures, msgs = desk_v31.close_vendor_linked(self.d2, self.gate)
        self.assertEqual([c["id"] for c in closures], ["V31-01"])
        self.assertEqual(rm.tickets_load(self.d2)["tickets"][a["ticket"]]["state"], "Resolved")
        c = closures[0]
        self.assertTrue(c["dry_run"])
        self.assertIn("DRY-RUN", c["reply"]["en"])
        self.assertIn("演练", c["reply"]["zh"])
        sent = desk_v31.send(self.d2, msgs)
        self.assertTrue(all(m["dry_run"] for m in sent))
        outbox = rm.read_jsonl(os.path.join(self.d2.dir, "outbox.jsonl"))
        self.assertTrue(outbox and all(o["dry_run"] and not o["sent"] for o in outbox))
        dev_closures, _ = devices_v31.close_vendor_linked(self.d1, self.gate)
        self.assertEqual([c["id"] for c in dev_closures], ["AV-5F-502"])
        self.assertEqual(rm.tickets_load(self.d1)["tickets"][room["ticket"]]["state"], "Resolved")

    def test_13_every_item_has_six_states_in_order(self):
        data = simulate.build()
        self.assertEqual(len(data["items"]), 7)
        for item in data["items"]:
            self.assertEqual([s["name"] for s in item["states"]], STATES, item["id"])
            self.assertEqual([s["kind"] for s in item["states"]], ["shared", "shared", "crew", "crew", "shared", "shared"])
        extra = [self.req("V31-04", gate=False), self.dev(SIG, SIG_FAULT, gate=False)]
        for item in extra:
            self.assertEqual([s["name"] for s in item["states"]], STATES)

    def test_14_v1_v2_v3_tests_still_pass(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", BRAIN="off")
        files = sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py") and f != os.path.basename(__file__))
        self.assertTrue(files)
        for name in files:
            proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", HERE, "-p", name], cwd=ROOT, env=env,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
            ran = re.search(r"Ran (\d+) test", proc.stderr)
            self.assertEqual(proc.returncode, 0, "%s failed:\n%s" % (name, proc.stderr[-1500:]))
            self.assertTrue(ran and int(ran.group(1)) > 0, name)

    def test_15_demo_data_matches_the_page_contract(self):
        data = simulate.build()
        simulate.validate_demo(data)
        self.assertEqual(data["version"], "3.1")
        self.assertEqual(data["summary"]["apps"], 2)
        self.assertEqual(data["summary"]["plugins"], ["v2", "v3"])
        self.assertEqual(data["summary"], {"apps": 2, "plugins": ["v2", "v3"], "items": 7, "vendor_linked": 4,
                                           "held_actions": data["summary"]["held_actions"], "v2_ranked": 2, "rejected": 1})
        self.assertGreater(data["summary"]["held_actions"], 0)
        self.assertEqual(len(data["closures"]), 4)
        # the writer produces exactly what the engines produce now
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "integrated-v31.js")
            simulate.write_demo(data, out)
            with open(out, encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("window.INTEGRATED_V31 = ", text)
        written = json.loads(text.split("window.INTEGRATED_V31 = ", 1)[1].rstrip().rstrip(";"))
        self.assertEqual(written, data)
        # a story check: the Teams request and the room share one parent; v2 and v3 tags are present
        teams = [i for i in data["items"] if i["outcome"] == "linked_vendor" and "Teams" in i["parent"]["en"]]
        self.assertEqual({i["app"] for i in teams}, {"servicedesk", "devices"})
        tags = {(s["name"], s["plugin"]) for i in data["items"] for s in i["states"] if s["plugin"]}
        self.assertTrue({("TRIAGE", "v3"), ("MITIGATE", "v2"), ("LOG", "v2")} <= tags)


class TestLearning(Base):
    def setUp(self):
        super().setUp()
        simulate.prime_v2(self.evo)  # adopted: tried first, so a fix can happen (2 verified successes)
        self.key = method_key("signage", "down", "clear-player-cache")

    def stats(self):
        m = self.evo.methods[self.key]
        return m["attempts"], m["successes"]

    def test_log_learns_from_delayed_recheck_only(self):
        provisional = self.dev(SIG, SIG_FAULT, gate=False)  # no re-check yet
        self.assertIsNone(self.state(provisional, "LOG")["plugin"])
        self.assertEqual(self.stats(), (2, 2))
        self.setUp()
        learned = self.dev(SIG, SIG_FAULT, gate=False, recheck="healthy")
        self.assertEqual(self.state(learned, "LOG")["plugin"], "v2")
        self.assertEqual(self.stats(), (3, 3))
        self.setUp()
        failed = self.dev(SIG, SIG_FAULT, gate=False, recheck="confirmed")  # the fault came back: counts as a failure
        self.assertEqual(self.stats(), (3, 2))
        self.assertEqual(failed["outcome"], "local_repair")


if __name__ == "__main__":
    unittest.main(verbosity=1)
