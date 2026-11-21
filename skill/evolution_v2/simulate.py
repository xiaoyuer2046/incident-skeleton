#!/usr/bin/env python3
"""Generate deterministic Incident Skeleton v2 demo data from the real engine."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List

try:
    from .engine import EvolutionEngine, method_key
except ImportError:  # direct: python skill/evolution_v2/simulate.py
    from engine import EvolutionEngine, method_key

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_SOURCES = os.path.join(HERE, "sources.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "demo", "data", "evolution-v2.js")
TIMES = ["09:00", "09:10", "09:20", "09:30"]


def _load(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _cycle_snapshot(engine: EvolutionEngine, starts: Dict[str, int], ts: str) -> Dict[str, Any]:
    state = engine.export_state()
    return {
        "ts": ts,
        "source_events": state["source_events"][starts["source_events"] :],
        "method_events": state["method_events"][starts["method_events"] :],
        "notices": state["notices"][starts["notices"] :],
        "methods": sorted(engine.methods.values(), key=lambda method: method["key"]),
        "versions": state["versions"][starts["versions"] :],
    }


def _starts(engine: EvolutionEngine) -> Dict[str, int]:
    state = engine.export_state()
    return {name: len(state[name]) for name in ("source_events", "method_events", "notices", "versions")}


def validate_demo(data: Dict[str, Any]) -> None:
    if data.get("version") != "2.0" or not isinstance(data.get("generated_at"), str):
        raise ValueError("invalid v2 demo header")
    required_current = {
        "intelligence_score",
        "strategy_version",
        "watched_sources",
        "known_methods",
        "promoted",
        "demoted",
        "pending",
    }
    if set(data.get("current", {})) != required_current:
        raise ValueError("invalid current summary")
    if not isinstance(data.get("cycles"), list) or not data["cycles"]:
        raise ValueError("demo must contain cycles")
    required_cycle = {"ts", "source_events", "method_events", "notices", "methods", "versions"}
    for cycle in data["cycles"]:
        if set(cycle) != required_cycle:
            raise ValueError("invalid cycle contract")


def build_demo(sources_path: str = DEFAULT_SOURCES) -> Dict[str, Any]:
    records = _load(sources_path)
    clock = {"value": "2026-11-21T09:00:00Z"}
    engine = EvolutionEngine(now=lambda: clock["value"])
    cycles: List[Dict[str, Any]] = []
    signage = method_key("signage", "down", "clear-player-cache")
    room = method_key("av", "hung", "restart-room-app")

    for index, label in enumerate(TIMES):
        clock["value"] = "2026-11-21T%s:00Z" % label
        starts = _starts(engine)
        engine.watch_many(record for record in records if record.get("cycle") == index)
        if index == 1:
            # An unchanged read proves DIFF suppresses duplicate events/notices.
            engine.watch(records[0])
            engine.verify(signage, True)
            engine.verify(room, False)
        elif index == 2:
            engine.verify(signage, True)
            engine.verify(room, False)
        elif index == 3:
            engine.verify(signage, True)
            engine.verify(room, False)
        cycles.append(_cycle_snapshot(engine, starts, label))

    data = {
        "version": "2.0",
        "generated_at": clock["value"],
        "current": engine.current(),
        "cycles": cycles,
    }
    validate_demo(data)
    return data


def write_demo(data: Dict[str, Any], output_path: str = DEFAULT_OUTPUT) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("window.EVOLUTION_V2 = ")
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v2 intelligence-evolution demo data")
    parser.add_argument("--sources", default=DEFAULT_SOURCES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    data = build_demo(args.sources)
    write_demo(data, args.output)
    print("generated %s (%d cycles, %s)" % (args.output, len(data["cycles"]), data["current"]["strategy_version"]))


if __name__ == "__main__":
    main()
