# Incident Skeleton — Kiro power

This folder packages Incident Skeleton as a [Kiro power](https://kiro.dev/docs/powers/create/): a manifest, the project's own MCP server, and one skill.

| File | What it does |
|---|---|
| `plugin.json` | Name, version and the keywords that activate the power |
| `mcp.json` | Starts the `incident-kb` MCP server from this repository |
| `skills/triage-incident/SKILL.md` | Steps for triaging one fault or request in dry run |

## Install

1. Clone the repository and set `INCIDENT_SKELETON_HOME` to its absolute path.
2. In Kiro, open **Powers → Add Custom Power → Import power from a folder**.
3. Pick this `power-incident-skeleton` folder.
4. Say "a meeting room cannot join Teams" to activate it.

On Windows, change `python3` to `python` in `mcp.json` if `python3` is not on the path.

Everything runs in dry run with sample data.
