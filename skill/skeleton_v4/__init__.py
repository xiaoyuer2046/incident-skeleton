"""Incident Skeleton v4: one shared six-step runtime, two apps, three plug-in slots, tiered learning.

This package imports and calls the libraries kept from earlier versions (listed in VERSIONS.md); the old versions
themselves were removed from the tree and remain in the Git history.
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
