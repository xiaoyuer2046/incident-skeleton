"""Incident Skeleton v4: one shared six-step runtime, two apps, three plug-in slots, tiered learning.

New files only. v1, v2, v3 and v3.1 stay unchanged; this package imports and calls them.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(SKILL, ".."))
os.environ.setdefault("BRAIN", "off")
for _p in (SKILL, os.path.join(SKILL, "apps", "servicedesk"), os.path.join(SKILL, "remediation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
