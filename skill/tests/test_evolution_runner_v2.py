#!/usr/bin/env python3
"""Tests for the persistent, schedule-ready v2 learning cycle."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, SKILL)

from evolution_v2.run_cycle import run_cycle


class EvolutionRunnerV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sources = os.path.join(self.tmp.name, "sources.json")
        self.state = os.path.join(self.tmp.name, "state.json")
        self.attempts = os.path.join(self.tmp.name, "attempts.jsonl")
        with open(self.sources, "w", encoding="utf-8") as handle:
            json.dump([
                {
                    "source": "servicenow_kb",
                    "ref": "KB-RUNNER-1",
                    "updated_at": "2026-11-21T09:00:00Z",
                    "device": "signage",
                    "symptom": "down",
                    "text": "Clear the player cache and verify the display.",
                }
            ], handle)

    def write_attempts(self, rows):
        with open(self.attempts, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    @staticmethod
    def attempt(ts, confirmed):
        return {
            "ts": ts,
            "rechecked_at": ts,
            "device": "signage",
            "target": "SIG-TEST",
            "symptom": "down",
            "action": "clear-player-cache",
            "outcome": "ran",
            "confirmed": confirmed,
        }

    def test_confirmed_rechecks_promote_and_are_consumed_once(self):
        self.write_attempts([
            self.attempt("2026-11-21T09:10:00", True),
            self.attempt("2026-11-21T09:20:00", True),
        ])
        first = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(len(first["attempt_events"]), 2)
        self.assertEqual(first["current"]["promoted"], 1)
        self.assertTrue(any(item["kind"] == "method_promoted" for item in first["notices"]))
        second = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(second["source_events"], [])
        self.assertEqual(second["attempt_events"], [])
        self.assertEqual(second["notices"], [])

    def test_provisional_recheck_is_not_learning_evidence(self):
        self.write_attempts([self.attempt("2026-11-21T09:10:00", None)])
        result = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(result["attempt_events"], [])
        self.assertEqual(result["current"]["pending"], 1)

    def test_source_change_proactively_notifies_once(self):
        self.write_attempts([])
        first = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(len(first["source_events"]), 1)
        self.assertTrue(first["notices"])
        self.assertTrue(all(item["dry_run"] for item in first["notices"]))
        second = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(second["notices"], [])
    def test_multiple_revisions_use_only_latest_snapshot(self):
        with open(self.sources, encoding="utf-8") as handle:
            old = json.load(handle)[0]
        new = dict(
            old,
            updated_at="2026-11-21T09:20:00Z",
            text="Updated: clear the player cache, reload, and verify the display.",
        )
        with open(self.sources, "w", encoding="utf-8") as handle:
            json.dump([old, new], handle)
        first = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(len(first["source_events"]), 1)
        self.assertEqual(first["source_events"][0]["updated_at"], new["updated_at"])
        second = run_cycle(self.sources, self.state, self.attempts)
        self.assertEqual(second["source_events"], [])
        self.assertEqual(second["notices"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
