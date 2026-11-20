#!/bin/sh
# audit_incident.sh — PostToolUse chat-lifecycle hook for Incident Skeleton.
#
# Fires AFTER a tool runs. If that tool produced an incident postmortem, it
# appends one audit line. Non-blocking: it always exits 0, so it can never deny
# or stall a tool. Safe to leave enabled.
#
# Install in Kiro Crew (dashboard -> Hooks tab -> New hook):
#     event   : PostToolUse
#     matcher : *            (fires after every tool)
#     command : <repo>/skill/hooks/audit_incident.sh
#
# The hook receives the tool-event JSON on stdin; the gateway sets
# KIROCREW_HOOK_EVENT and KIROCREW_HOOK_CONTEXT in the env.
#
# Demo / test it without the dashboard:
#     printf '%s\n' '{"tool_name":"shell","tool_input":{"command":"...postmortem-printer-1.md..."}}' \
#       | sh skill/hooks/audit_incident.sh

ctx=$(cat)
log="${KIROCREW_HOME:-$HOME/.kiro/crew}/incident-audit.log"
if echo "$ctx" | grep -qo 'postmortem-[a-z0-9-]*\.md'; then
  printf '[%s] incident-skeleton: postmortem written\n' "$(date -u +%FT%TZ)" >> "$log"
fi
exit 0
