---
name: incident-skeleton-v4
description: 事件骨架 v4。一个共用的六步运行时，两个应用只写适配器，三个插件插槽，AI 先学习（厂商 MCP → 公司内部 → 可信互联网）。全部为 dry run 与模拟数据。
---

# Incident Skeleton v4

## 何时使用

处理办公设备故障（打印机、数字标牌、会议室 AV、无线 AP）或服务台一线请求（账号、VPN、邮件、软件）时使用。

## 共用运行时

`skill/skeleton_v4/skeleton.py` 是唯一的六步运行时：

```
RECEIVE → TRIAGE → INVESTIGATE → MITIGATE → RESOLVE → LOG
```

- 顺序固定。插件和小组不能增加、删除或重排步骤。
- 提前结束（拒绝、关联已知故障、关联厂商故障）时，后面的步骤记录为"跳过"并写明原因。
- 应用只写适配器：`skill/skeleton_v4/app_devices.py`（设备）和 `skill/skeleton_v4/app_servicedesk.py`（服务台）。新增应用只需新适配器加配置。

## 三个插件插槽

| 插槽 | 位置 | 作用 |
|---|---|---|
| `triage_gate` | TRIAGE | 全局故障判断：厂商整体故障时关联到同一张总单，并暂停无用动作 |
| `mitigate_rank` | MITIGATE | 方法排名：已采用的方法优先尝试，被暂停的方法从内存中的允许列表移除 |
| `log_learn` | LOG | 学习：只记录已确认的复查结果，临时结果忽略 |

## TRIAGE 顺序

1. 安全拒绝（管理员权限、注入请求）
2. 全局故障判断
3. 已知故障关联（例如"4 楼没有 Wi-Fi"）
4. 选择小组

## AI 先学习

读取顺序：

1. A 层：厂商 MCP（如 Microsoft、Cisco）和官方状态
2. B 层：公司 KB、工单、聊天、邮件、共享文档
3. C 层：可信互联网
4. D 层：公众报告

规则：

- C、D 层需要 A 或 B 层佐证才能形成可用候选。
- 公众报告不能升级或降级任何方法。
- 危险内容拦截：指令、命令、凭据、权限请求一律拒绝并记录；未知动作和其他设备类型的动作同样拒绝。
- 厂商公告说方法有害时，暂停该方法并通知。
- 每次变化追加不可改的 `4.0.N` 版本，并生成一条双语 dry run 通知。来源没变不生成。

## 权限不变量

- 学习只能收紧权限，不能放宽。
- 不写入 `policy.json`、`actions.json`、`app.json`。
- 物理动作不会变成自动执行。
- 暂停的动作只是建议暂缓，真正的动作仍由人和策略决定。

## 例子：Teams 故障

Microsoft Teams 出现厂商故障时，服务台的登录请求和会议室 Teams Rooms 故障关联到同一张微软总单，密码重置和 AV 修复被暂停。微软与内部都恢复后，关联单关闭并发出双语通知。

## 诚实说明

- 全部为 dry run，使用模拟数据。
- Microsoft、Cisco 和互联网的真实连接未登录。
- 不要把 dry run 结果说成真实修复，也不要写具体测试数量。

## 文件

- 评委入口：`demo/guide-v4.html`
- 演示：`demo/skeleton-v4.html`
- 规格：`.kiro/specs/incident-skeleton-v4/`
- 提交：`DEVPOST-v4.md`
- 版本清单：`VERSIONS.md`
