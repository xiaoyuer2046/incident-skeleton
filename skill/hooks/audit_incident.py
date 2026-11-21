#!/usr/bin/env python3
"""audit_incident.py: cross-platform PostToolUse hook for Incident Skeleton (same job as audit_incident.sh).

Fires after a tool runs. If the tool event mentions an incident postmortem file, it appends one audit line to
$KIROCREW_HOME/incident-audit.log (default ~/.kiro/crew). Non-blocking: always exits 0, never denies or stalls a tool.

Install in Kiro Crew (dashboard -> Hooks -> New hook):
    event: PostToolUse   matcher: *   command: python <repo>/skill/hooks/audit_incident.py

Try it without the dashboard:
    echo {"tool_name":"shell","tool_input":{"command":"postmortem-printer-1.md"}} | python skill/hooks/audit_incident.py
"""
import os
import re
import sys
from datetime import datetime, timezone


def main() -> int:
    try:
        raw = sys.stdin.read()
        if re.search(r"postmortem-[a-z0-9-]*\.md", raw):
            home = os.environ.get("KIROCREW_HOME") or os.path.join(os.path.expanduser("~"), ".kiro", "crew")
            os.makedirs(home, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(os.path.join(home, "incident-audit.log"), "a", encoding="utf-8") as log:
                log.write("[%s] incident-skeleton: postmortem written\n" % stamp)
    except Exception:  # a hook must never block a tool
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
