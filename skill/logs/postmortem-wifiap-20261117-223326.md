# 事件复盘 — 📶 无线 AP

- 时间: 2026-11-17T22:33:26
- 设备/来源: 控制器 / 楼层3
- 告警消息: AP offline, clients dropping
- 严重度: 高
- 恢复: True

## 走过的骨架（同一套六步）

- **RECEIVE** (共享)
- **TRIAGE** (共享)
- **INVESTIGATE** (班底)
- **MITIGATE** (班底)
- **RESOLVE** (共享)
- **LOG** (共享)

## 排查发现 (INVESTIGATE)

- [ok] ping AP 1.1.1.1: 可达 (reachable)
- [warn] SNMP 端口状态 (ifOperStatus): 超时 (timeout)
- [warn] 客户端/射频: 需控制器 API 查（--target <controller-url>）

## 处理步骤 (MITIGATE)

- [可执行] 控制器 API 重启 AP（Meraki/Aruba/Cisco WLC）
- [需人工] PoE 交换机端口断电再上电（shutdown/no shutdown 端口）
- [需人工] 射频调优：换信道 / 调功率
- [需人工] 补 AP / 换设备（覆盖不足）

---
*由 Incident Skeleton (Skeleton Crew) 生成。一套骨架，四套班底。*