#!/usr/bin/env python3
"""Run one persistent v2 learning cycle.

This runner is schedule-ready and dry-run only. It watches approved source
records and absorbs only delayed re-check results from the v1 repair loop.
It prints only new proactive notices, so an unchanged cycle stays quiet.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Iterable, List

try:
    from .engine import EvolutionEngine
except ImportError:  # direct: python skill/evolution_v2/run_cycle.py
    from engine import EvolutionEngine

HERE = os.path.dirname(os.path.abspath(__file__))
REMEDIATION_DATA = os.path.abspath(os.path.join(HERE, "..", "remediation", "data"))
DEFAULT_SOURCES = os.path.join(HERE, "sources.json")
DEFAULT_STATE = os.path.join(REMEDIATION_DATA, "evolution-v2-state.json")
DEFAULT_ATTEMPTS = os.path.join(REMEDIATION_DATA, "attempts.jsonl")


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def latest_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the newest snapshot for each stable source id."""
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = "%s|%s" % (record.get("source", ""), record.get("ref", ""))
        current = latest.get(key)
        if current is None or str(record.get("updated_at", "")) >= str(current.get("updated_at", "")):
            latest[key] = record
    return list(latest.values())


def run_cycle(
    source_path: str = DEFAULT_SOURCES,
    state_path: str = DEFAULT_STATE,
    attempts_path: str = DEFAULT_ATTEMPTS,
) -> Dict[str, Any]:
    engine = EvolutionEngine(state_path=state_path)
    before = len(engine.notices)
    records = load_json(source_path, [])
    if not isinstance(records, list):
        raise ValueError("source file must contain a JSON list")
    source_events = engine.watch_many(latest_records(records))
    attempt_events: List[Dict[str, Any]] = []
    for attempt in read_jsonl(attempts_path):
        event = engine.absorb_attempt(attempt)
        if event is not None:
            attempt_events.append(event)
    notices = engine.notices[before:]
    return {
        "dry_run": True,
        "source_events": source_events,
        "attempt_events": attempt_events,
        "notices": notices,
        "current": engine.current(),
        "state_path": state_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one dry-run v2 intelligence evolution cycle")
    parser.add_argument("--sources", default=DEFAULT_SOURCES)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--attempts", default=DEFAULT_ATTEMPTS)
    parser.add_argument("--lang", choices=("zh", "en"), default="zh")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_cycle(args.sources, args.state, args.attempts)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for notice in result["notices"]:
        print(notice["message"][args.lang])


if __name__ == "__main__":
    main()
