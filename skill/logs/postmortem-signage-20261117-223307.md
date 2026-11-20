# 事件复盘 — 📺 数字标牌

- 时间: 2026-11-17T22:33:07
- 设备/来源: CMS / 大厅东
- 告警消息: player offline 14m
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

- [ok] curl https://example.com: HTTP 200
- [ok] ping example.com: 可达 (reachable)

## 处理步骤 (MITIGATE)

- [需人工] 重启播放器（远程 reboot 或现场断电）
- [需人工] CMS 重新推送内容 / 排期
- [需人工] 重新插拔 HDMI 线
- [需人工] 换备用播放器

---
*由 Incident Skeleton (Skeleton Crew) 生成。一套骨架，四套班底。*