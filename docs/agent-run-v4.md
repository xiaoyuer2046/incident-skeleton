# Multi-agent run record / 多 agent 协作试跑记录

> A real run of the Kiro Crew agents in `.kiro/agents/`, recorded on 2026-11-21 (Windows, Kiro Crew dashboard). Everything is a **dry run**: no `--live`, no approval given, no file changed.
> 这是 `.kiro/agents/` 里 Kiro Crew agent 的一次真实运行记录。全程**演练**：没有 `--live`，没有批准任何操作，没有改动文件。

## Who did what / 分工

```
incident-crew-lead ──crew_status, list_open_tickets──▶ incident-kb MCP
        │
        └──spawn_run(agent = wifiap-crew)──▶ wifiap-crew ──recall_fix──▶ incident-kb MCP
```

| Step | Agent | Tool | Result |
|---|---|---|---|
| 1 | `incident-crew-lead` | `incident-kb/crew_status` | Patrol at 21:40: 0 of 4 sample devices healthy |
| 2 | `incident-crew-lead` | `incident-kb/list_open_tickets` | 4 open dry-run tickets, one per device type |
| 3 | `incident-crew-lead` | decision | Four different device types, no shared upstream switch, so no blast-radius incident. Picked the wireless AP. |
| 4 | `incident-crew-lead` | `spawn_run` → `wifiap-crew` | Handed over device `wifiap-sample`, symptom "down", ticket `DRYRUN-INC0000004`, scope "recall_fix only" |
| 5 | `wifiap-crew` | `incident-kb/recall_fix` | Ranked fixes with risk and permission tier |
| 6 | `incident-crew-lead` | `spawn_status`, `wait` | Collected the sub-agent result and wrote the summary |

The first `spawn_run` carried a working directory outside the allowed roots and was refused by Kiro Crew. The crew lead retried without it and the sub-agent started. That refusal is the platform's sandbox working as intended.
第一次 `spawn_run` 带了不在允许范围内的工作目录，被 Kiro Crew 拒绝；班长去掉后重试成功。这是平台沙箱正常生效。

## The sub-agent's advice / 子代理给出的建议（仅建议，policy 决定）

| # | Action | Risk | Permission tier | Needs a person |
|---|---|---|---|---|
| 1 | Reboot the AP through the controller | medium | notify, then act | no |
| 2 | Power-cycle the PoE port | medium | notify, then act | no |
| 3 | Radio tuning (channel / power) | medium | notify, then act | no |
| 4 | Add or replace an AP | high | never automatic (on site) | **yes** |

Order suggested: read-only INVESTIGATE first, then the dry-run repair loop, trying 1 before 2. If the controller cannot see the AP, a PoE power-cycle is more likely to help. Radio tuning fits an AP that is online but slow, so it is unlikely to help here.

Hand to a person: if the PoE port reads 0 W, or the AP is still offline after steps 1 and 2, Network / Wireless goes on site. Approvers named by `policy.json`: Zhang Min (Network) and Ravi Kumar (Network on-call).

## What this shows / 说明了什么

- The crew lead coordinates and does not repair. A device crew owns INVESTIGATE and MITIGATE, the same split as the skeleton.
- Both agents read the same data through the project's own MCP server.
- The agents explain and rank. `policy.json` decides; physical steps stay with people.
- 班长只协调不修理；设备班底负责排查和处置，和骨架分工一致。两个 agent 都通过项目自己的 MCP 读同一份数据。agent 只解释和排序，权限由 `policy.json` 决定，现场步骤交给人。

The device data in this run is the sample patrol data (`*-sample` targets), not a real network.
本次数据是示例巡检数据（`*-sample` 设备），不是真实网络。
