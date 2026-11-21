#!/usr/bin/env python3
"""Run persistent v3 intelligence cycles. Dry-run only; prints only NEW notices.

Input is a JSON list of normalized signals, or {"cycles": [{"ts", "signals"}]}.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List

try:
    from .engine import GlobalIntelligenceEngine
except ImportError:  # direct run
    from engine import GlobalIntelligenceEngine

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SIGNALS = os.path.join(HERE, "signals.json")
DEFAULT_STATE = os.path.abspath(
    os.path.join(HERE, "..", "remediation", "data", "global-intelligence-v3-state.json"))


def load_cycles(path: str, upto: int = 0) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cycles = data["cycles"] if isinstance(data, dict) else [{"ts": None, "signals": data}]
    return cycles[:upto] if upto else cycles


def run(signals_path: str, state_path: str, upto: int = 0) -> List[Dict[str, Any]]:
    engine = GlobalIntelligenceEngine(state_path=state_path)
    notices: List[Dict[str, Any]] = []
    for cycle in load_cycles(signals_path, upto):
        notices.extend(engine.run_cycle(cycle["signals"], cycle.get("ts"))["notices"])
    return notices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", default=DEFAULT_SIGNALS)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--upto", type=int, default=0, help="process only the first N cycles")
    args = parser.parse_args()
    print(json.dumps(run(args.signals, args.state, args.upto), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
