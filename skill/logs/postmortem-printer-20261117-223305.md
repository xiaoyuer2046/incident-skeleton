# 事件复盘 — 🖨️ 打印机

- 时间: 2026-11-17T22:33:05
- 设备/来源: SNMP 10.0.4.21
- 告警消息: PAPER JAM (13.20)
- 严重度: 中
- 恢复: True

## 走过的骨架（同一套六步）

- **RECEIVE** (共享)
- **TRIAGE** (共享)
- **INVESTIGATE** (班底)
- **MITIGATE** (班底)
- **RESOLVE** (共享)
- **LOG** (共享)

## 排查发现 (INVESTIGATE)

- [ok] ping 1.1.1.1: 可达 (reachable)
- [warn] SNMP 状态 (hrDeviceStatus): 超时 (timeout)
- [warn] 错误码 13.20: 定影器/出纸区卡纸 (fuser area paper jam)

## 处理步骤 (MITIGATE)

- [需人工] 现场清除卡纸 / 更换耗材
- [可执行] 重启打印后台 (cups): launchctl kickstart -k system/org.cups.cupsd  # 或 systemctl restart cups
- [需人工] 删除并重新添加打印队列
- [需人工] 断电重启打印机（拔电 30 秒再插）

---
*由 Incident Skeleton (Skeleton Crew) 生成。一套骨架，四套班底。*