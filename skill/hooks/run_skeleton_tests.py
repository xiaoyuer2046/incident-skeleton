#!/usr/bin/env python3
"""run_skeleton_tests.py: run the skeleton tests (v4 runtime, v4 learning, v5) for the Kiro "Skeleton tests on save" hook.

One Python call, so the hook command works the same on macOS, Linux and Windows.
Exit code is 0 only when every test file passes.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS = ["skill/tests/test_skeleton_v4.py", "skill/tests/test_learning_v4.py", "skill/tests/test_skeleton_v5.py"]


def main() -> int:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    failed = 0
    for rel in TESTS:
        code = subprocess.call([sys.executable, os.path.join(ROOT, rel)], cwd=ROOT, env=env)
        print("[hook] %s -> %s" % (rel, "pass" if code == 0 else "FAIL (exit %d)" % code))
        failed += code != 0
    print("[hook] skeleton tests: %d/%d passed" % (len(TESTS) - failed, len(TESTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
