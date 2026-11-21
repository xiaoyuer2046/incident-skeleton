"""Incident Skeleton v5: the v4 six-step runtime, unchanged, plus an access layer, news consensus and approved permission growth.

New files only. skeleton_v4 (and the libraries it calls) stay as they are; this package imports them.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.abspath(os.path.join(HERE, ".."))
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from skeleton_v4 import SKILL, ROOT  # noqa: E402,F401  (also puts the v1 modules on sys.path)
