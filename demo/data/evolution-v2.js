window.EVOLUTION_V2 = {
  "version": "2.0",
  "generated_at": "2026-11-21T09:30:00Z",
  "current": {
    "intelligence_score": 67,
    "strategy_version": "2.0.12",
    "watched_sources": 7,
    "known_methods": 5,
    "promoted": 1,
    "demoted": 1,
    "pending": 3
  },
  "cycles": [
    {
      "ts": "09:00",
      "source_events": [
        {
          "id": "EV-df412fbb39177390",
          "ts": "2026-11-21T09:00:00Z",
          "source": "servicenow_kb",
          "ref": "KB001042",
          "source_key": "servicenow_kb|KB001042",
          "updated_at": "2026-11-21T09:00:00Z",
          "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "signage|down|clear-player-cache"
          ]
        },
        {
          "id": "EV-e2636617dd01f91d",
          "ts": "2026-11-21T09:00:00Z",
          "source": "incident",
          "ref": "INC0098123",
          "source_key": "incident|INC0098123",
          "updated_at": "2026-11-21T09:00:00Z",
          "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "av|hung|restart-room-app"
          ]
        },
        {
          "id": "EV-f46cae18c1d5da6f",
          "ts": "2026-11-21T09:00:00Z",
          "source": "email",
          "ref": "mail-printer-2201",
          "source_key": "email|mail-printer-2201",
          "updated_at": "2026-11-21T09:00:00Z",
          "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "printer|offline|power-cycle-printer"
          ]
        },
        {
          "id": "EV-198806b2fd1a3177",
          "ts": "2026-11-21T09:00:00Z",
          "source": "shared_drive",
          "ref": "wireless-recovery.md",
          "source_key": "shared_drive|wireless-recovery.md",
          "updated_at": "2026-11-21T09:00:00Z",
          "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "wifiap|offline|poe-cycle"
          ]
        },
        {
          "id": "EV-d09a05edd81bc37e",
          "ts": "2026-11-21T09:00:00Z",
          "source": "chat",
          "ref": "teams-print-884",
          "source_key": "chat|teams-print-884",
          "updated_at": "2026-11-21T09:00:00Z",
          "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "printer|jam|clear-queue"
          ]
        }
      ],
      "method_events": [
        {
          "id": "EV-d999274349035345",
          "ts": "2026-11-21T09:00:00Z",
          "source_event_id": "EV-df412fbb39177390",
          "source": "servicenow_kb|KB001042",
          "method": "signage|down|clear-player-cache",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change"
        },
        {
          "id": "EV-dc5f0a8ef9d40e5c",
          "ts": "2026-11-21T09:00:00Z",
          "source_event_id": "EV-e2636617dd01f91d",
          "source": "incident|INC0098123",
          "method": "av|hung|restart-room-app",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change"
        },
        {
          "id": "EV-0b15f651946eb715",
          "ts": "2026-11-21T09:00:00Z",
          "source_event_id": "EV-f46cae18c1d5da6f",
          "source": "email|mail-printer-2201",
          "method": "printer|offline|power-cycle-printer",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change"
        },
        {
          "id": "EV-f57463866666c60a",
          "ts": "2026-11-21T09:00:00Z",
          "source_event_id": "EV-198806b2fd1a3177",
          "source": "shared_drive|wireless-recovery.md",
          "method": "wifiap|offline|poe-cycle",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change"
        },
        {
          "id": "EV-c958249970c33906",
          "ts": "2026-11-21T09:00:00Z",
          "source_event_id": "EV-d09a05edd81bc37e",
          "source": "chat|teams-print-884",
          "method": "printer|jam|clear-queue",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change"
        }
      ],
      "notices": [
        {
          "id": "EV-f2bd3bfa66a6d560",
          "event_id": "EV-df412fbb39177390",
          "ts": "2026-11-21T09:00:00Z",
          "kind": "candidate_added",
          "source": "servicenow_kb|KB001042",
          "method": "signage|down|clear-player-cache",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] New method found. Source: ServiceNow KB · KB001042. Method: digital signage · black or offline · Clear the player cache and reload. observed -> needs verification. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 发现新方法。来源：ServiceNow 知识库 · KB001042。方法：数字标牌 · 黑屏或离线 · 清除播放器缓存并重新加载。已发现 → 待验证。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        },
        {
          "id": "EV-99dda3ec3d079f85",
          "event_id": "EV-e2636617dd01f91d",
          "ts": "2026-11-21T09:00:00Z",
          "kind": "candidate_added",
          "source": "incident|INC0098123",
          "method": "av|hung|restart-room-app",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] New method found. Source: resolved incident · INC0098123. Method: meeting-room AV · frozen or cannot join · Restart the room app (Zoom/Teams Rooms). observed -> needs verification. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 发现新方法。来源：历史工单 · INC0098123。方法：会议室音视频 · 卡死或无法入会 · 重启房间应用 (Zoom/Teams Rooms)。已发现 → 待验证。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        },
        {
          "id": "EV-3bc983bb4679fbb6",
          "event_id": "EV-f46cae18c1d5da6f",
          "ts": "2026-11-21T09:00:00Z",
          "kind": "candidate_added",
          "source": "email|mail-printer-2201",
          "method": "printer|offline|power-cycle-printer",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": true,
            "tier": "human",
            "permission_source": "policy.json",
            "en": "Physical action remains human-only; no automatic permission was granted.",
            "zh": "物理操作仍须人工执行；未授予自动权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] New method found. Source: email · mail-printer-2201. Method: printer · offline · Power-cycle the printer. observed -> needs verification. Physical action remains human-only; no automatic permission was granted.",
            "zh": "[演练] 发现新方法。来源：邮件 · mail-printer-2201。方法：打印机 · 离线 · 断电重启打印机。已发现 → 待验证。物理操作仍须人工执行；未授予自动权限。"
          }
        },
        {
          "id": "EV-d63387c46f03c048",
          "event_id": "EV-198806b2fd1a3177",
          "ts": "2026-11-21T09:00:00Z",
          "kind": "candidate_added",
          "source": "shared_drive|wireless-recovery.md",
          "method": "wifiap|offline|poe-cycle",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "notify_then_act",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] New method found. Source: shared drive · wireless-recovery.md. Method: wireless AP · offline · Power-cycle the PoE switch port. observed -> needs verification. Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "[演练] 发现新方法。来源：共享盘 · wireless-recovery.md。方法：无线 AP · 离线 · PoE 端口断电再上电。已发现 → 待验证。权限保持“先提醒再执行”；学习过程没有增加权限。"
          }
        },
        {
          "id": "EV-919f28853c7efc9a",
          "event_id": "EV-d09a05edd81bc37e",
          "ts": "2026-11-21T09:00:00Z",
          "kind": "candidate_added",
          "source": "chat|teams-print-884",
          "method": "printer|jam|clear-queue",
          "old_state": "observed",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] New method found. Source: team chat · teams-print-884. Method: printer · paper jam · Clear stuck print jobs. observed -> needs verification. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 发现新方法。来源：团队聊天 · teams-print-884。方法：打印机 · 卡纸 · 清空卡住的打印任务。已发现 → 待验证。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        }
      ],
      "methods": [
        {
          "key": "av|hung|restart-room-app",
          "device": "av",
          "symptom": "hung",
          "action": "restart-room-app",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "incident",
              "ref": "INC0098123",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "printer|jam|clear-queue",
          "device": "printer",
          "symptom": "jam",
          "action": "clear-queue",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "chat",
              "ref": "teams-print-884",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "printer|offline|power-cycle-printer",
          "device": "printer",
          "symptom": "offline",
          "action": "power-cycle-printer",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "email",
              "ref": "mail-printer-2201",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": true,
            "tier": "human",
            "permission_source": "policy.json",
            "en": "Physical action remains human-only; no automatic permission was granted.",
            "zh": "物理操作仍须人工执行；未授予自动权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "signage|down|clear-player-cache",
          "device": "signage",
          "symptom": "down",
          "action": "clear-player-cache",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "servicenow_kb",
              "ref": "KB001042",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "wifiap|offline|poe-cycle",
          "device": "wifiap",
          "symptom": "offline",
          "action": "poe-cycle",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "shared_drive",
              "ref": "wireless-recovery.md",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "notify_then_act",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        }
      ],
      "versions": [
        {
          "version": "2.0.1",
          "created_at": "2026-11-21T09:00:00Z",
          "reason": "source_change",
          "method": "signage|down|clear-player-cache",
          "before": {},
          "after": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          }
        },
        {
          "version": "2.0.2",
          "created_at": "2026-11-21T09:00:00Z",
          "reason": "source_change",
          "method": "av|hung|restart-room-app",
          "before": {},
          "after": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          }
        },
        {
          "version": "2.0.3",
          "created_at": "2026-11-21T09:00:00Z",
          "reason": "source_change",
          "method": "printer|offline|power-cycle-printer",
          "before": {},
          "after": {
            "key": "printer|offline|power-cycle-printer",
            "device": "printer",
            "symptom": "offline",
            "action": "power-cycle-printer",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "email",
                "ref": "mail-printer-2201",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": false,
              "automatic": false,
              "physical": true,
              "tier": "human",
              "permission_source": "policy.json",
              "en": "Physical action remains human-only; no automatic permission was granted.",
              "zh": "物理操作仍须人工执行；未授予自动权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          }
        },
        {
          "version": "2.0.4",
          "created_at": "2026-11-21T09:00:00Z",
          "reason": "source_change",
          "method": "wifiap|offline|poe-cycle",
          "before": {},
          "after": {
            "key": "wifiap|offline|poe-cycle",
            "device": "wifiap",
            "symptom": "offline",
            "action": "poe-cycle",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "shared_drive",
                "ref": "wireless-recovery.md",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "notify_then_act",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
              "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          }
        },
        {
          "version": "2.0.5",
          "created_at": "2026-11-21T09:00:00Z",
          "reason": "source_change",
          "method": "printer|jam|clear-queue",
          "before": {},
          "after": {
            "key": "printer|jam|clear-queue",
            "device": "printer",
            "symptom": "jam",
            "action": "clear-queue",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "chat",
                "ref": "teams-print-884",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          }
        }
      ]
    },
    {
      "ts": "09:10",
      "source_events": [
        {
          "id": "EV-b76727c57f977a58",
          "ts": "2026-11-21T09:10:00Z",
          "source": "chat",
          "ref": "teams-unsafe-991",
          "source_key": "chat|teams-unsafe-991",
          "updated_at": "2026-11-21T09:10:00Z",
          "fingerprint": "cf112817334f983fc68865d68fe0e009e63e2719b4c56ffc32bc8b7522e7084b",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "rejected",
          "reason": "override",
          "methods": []
        },
        {
          "id": "EV-36d2fb5053eff5a5",
          "ts": "2026-11-21T09:10:00Z",
          "source": "incident",
          "ref": "INC0098999",
          "source_key": "incident|INC0098999",
          "updated_at": "2026-11-21T09:10:00Z",
          "fingerprint": "3f937e125c8f99534072f6214ff1caeb242d6bfa48aaabbb2b4e5aec655d542a",
          "previous_fingerprint": null,
          "diff": "discovered",
          "status": "rejected",
          "reason": "unknown_action",
          "rejected_actions": [
            "vendor-secret-reset"
          ],
          "methods": []
        }
      ],
      "method_events": [
        {
          "id": "EV-ef0800cd60e9b75b",
          "ts": "2026-11-21T09:10:00Z",
          "source": "dry_run_verifier",
          "method": "signage|down|clear-player-cache",
          "old_state": "candidate",
          "new_state": "trial",
          "reason": "verified_outcome",
          "succeeded": true,
          "attempts": 1,
          "successes": 1,
          "success_rate": 1.0,
          "dry_run": true
        },
        {
          "id": "EV-04663ddbd3e6b2dd",
          "ts": "2026-11-21T09:10:00Z",
          "source": "dry_run_verifier",
          "method": "av|hung|restart-room-app",
          "old_state": "candidate",
          "new_state": "trial",
          "reason": "verified_outcome",
          "succeeded": false,
          "attempts": 1,
          "successes": 0,
          "success_rate": 0.0,
          "dry_run": true
        }
      ],
      "notices": [
        {
          "id": "EV-fe9d5e1fa740c092",
          "event_id": "EV-b76727c57f977a58",
          "ts": "2026-11-21T09:10:00Z",
          "kind": "source_rejected",
          "source": "chat|teams-unsafe-991",
          "method": null,
          "old_state": "unseen",
          "new_state": "rejected",
          "reason": "override",
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": false,
            "tier": "rejected",
            "permission_source": "policy.json",
            "en": "Rejected source text cannot affect policy or execution.",
            "zh": "被拒绝的来源文本不会影响策略或执行。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] Unsafe source text rejected. Source: team chat · teams-unsafe-991. Method: none. not seen -> rejected. Rejected source text cannot affect policy or execution.",
            "zh": "[演练] 危险来源内容已拦截。来源：团队聊天 · teams-unsafe-991。方法：无。未见过 → 已拦截。被拒绝的来源文本不会影响策略或执行。"
          }
        }
      ],
      "methods": [
        {
          "key": "av|hung|restart-room-app",
          "device": "av",
          "symptom": "hung",
          "action": "restart-room-app",
          "state": "trial",
          "attempts": 1,
          "successes": 0,
          "failures": 1,
          "success_rate": 0.0,
          "sources": [
            {
              "source": "incident",
              "ref": "INC0098123",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:10:00Z"
        },
        {
          "key": "printer|jam|clear-queue",
          "device": "printer",
          "symptom": "jam",
          "action": "clear-queue",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "chat",
              "ref": "teams-print-884",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "printer|offline|power-cycle-printer",
          "device": "printer",
          "symptom": "offline",
          "action": "power-cycle-printer",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "email",
              "ref": "mail-printer-2201",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": true,
            "tier": "human",
            "permission_source": "policy.json",
            "en": "Physical action remains human-only; no automatic permission was granted.",
            "zh": "物理操作仍须人工执行；未授予自动权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "signage|down|clear-player-cache",
          "device": "signage",
          "symptom": "down",
          "action": "clear-player-cache",
          "state": "trial",
          "attempts": 1,
          "successes": 1,
          "failures": 0,
          "success_rate": 1.0,
          "sources": [
            {
              "source": "servicenow_kb",
              "ref": "KB001042",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:10:00Z"
        },
        {
          "key": "wifiap|offline|poe-cycle",
          "device": "wifiap",
          "symptom": "offline",
          "action": "poe-cycle",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "shared_drive",
              "ref": "wireless-recovery.md",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "notify_then_act",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        }
      ],
      "versions": [
        {
          "version": "2.0.6",
          "created_at": "2026-11-21T09:10:00Z",
          "reason": "verified_outcome",
          "method": "signage|down|clear-player-cache",
          "before": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          },
          "after": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "trial",
            "attempts": 1,
            "successes": 1,
            "failures": 0,
            "success_rate": 1.0,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:10:00Z"
          }
        },
        {
          "version": "2.0.7",
          "created_at": "2026-11-21T09:10:00Z",
          "reason": "verified_outcome",
          "method": "av|hung|restart-room-app",
          "before": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:00:00Z"
          },
          "after": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "trial",
            "attempts": 1,
            "successes": 0,
            "failures": 1,
            "success_rate": 0.0,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:10:00Z"
          }
        }
      ]
    },
    {
      "ts": "09:20",
      "source_events": [
        {
          "id": "EV-9ccbc5bc512e6440",
          "ts": "2026-11-21T09:20:00Z",
          "source": "servicenow_kb",
          "ref": "KB001042",
          "source_key": "servicenow_kb|KB001042",
          "updated_at": "2026-11-21T09:20:00Z",
          "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed",
          "previous_fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b",
          "diff": "changed",
          "status": "accepted",
          "reason": "source_change",
          "methods": [
            "signage|down|clear-player-cache"
          ]
        }
      ],
      "method_events": [
        {
          "id": "EV-d177d6b86713523c",
          "ts": "2026-11-21T09:20:00Z",
          "source_event_id": "EV-9ccbc5bc512e6440",
          "source": "servicenow_kb|KB001042",
          "method": "signage|down|clear-player-cache",
          "old_state": "trial",
          "new_state": "candidate",
          "reason": "source_change"
        },
        {
          "id": "EV-59d3339606118de4",
          "ts": "2026-11-21T09:20:00Z",
          "source": "dry_run_verifier",
          "method": "signage|down|clear-player-cache",
          "old_state": "candidate",
          "new_state": "trial",
          "reason": "verified_outcome",
          "succeeded": true,
          "attempts": 1,
          "successes": 1,
          "success_rate": 1.0,
          "dry_run": true
        },
        {
          "id": "EV-816db86d6f7ef229",
          "ts": "2026-11-21T09:20:00Z",
          "source": "dry_run_verifier",
          "method": "av|hung|restart-room-app",
          "old_state": "trial",
          "new_state": "trial",
          "reason": "verified_outcome",
          "succeeded": false,
          "attempts": 2,
          "successes": 0,
          "success_rate": 0.0,
          "dry_run": true
        }
      ],
      "notices": [
        {
          "id": "EV-0622361e2b74aba3",
          "event_id": "EV-9ccbc5bc512e6440",
          "ts": "2026-11-21T09:20:00Z",
          "kind": "candidate_changed",
          "source": "servicenow_kb|KB001042",
          "method": "signage|down|clear-player-cache",
          "old_state": "trial",
          "new_state": "candidate",
          "reason": "source_change",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] Method guidance changed. Source: ServiceNow KB · KB001042. Method: digital signage · black or offline · Clear the player cache and reload. being verified -> needs verification. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 方法内容有更新。来源：ServiceNow 知识库 · KB001042。方法：数字标牌 · 黑屏或离线 · 清除播放器缓存并重新加载。验证中 → 待验证。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        }
      ],
      "methods": [
        {
          "key": "av|hung|restart-room-app",
          "device": "av",
          "symptom": "hung",
          "action": "restart-room-app",
          "state": "trial",
          "attempts": 2,
          "successes": 0,
          "failures": 2,
          "success_rate": 0.0,
          "sources": [
            {
              "source": "incident",
              "ref": "INC0098123",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:20:00Z"
        },
        {
          "key": "printer|jam|clear-queue",
          "device": "printer",
          "symptom": "jam",
          "action": "clear-queue",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "chat",
              "ref": "teams-print-884",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "printer|offline|power-cycle-printer",
          "device": "printer",
          "symptom": "offline",
          "action": "power-cycle-printer",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "email",
              "ref": "mail-printer-2201",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": true,
            "tier": "human",
            "permission_source": "policy.json",
            "en": "Physical action remains human-only; no automatic permission was granted.",
            "zh": "物理操作仍须人工执行；未授予自动权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "signage|down|clear-player-cache",
          "device": "signage",
          "symptom": "down",
          "action": "clear-player-cache",
          "state": "trial",
          "attempts": 1,
          "successes": 1,
          "failures": 0,
          "success_rate": 1.0,
          "sources": [
            {
              "source": "servicenow_kb",
              "ref": "KB001042",
              "updated_at": "2026-11-21T09:20:00Z",
              "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial",
            "candidate",
            "trial"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:20:00Z"
        },
        {
          "key": "wifiap|offline|poe-cycle",
          "device": "wifiap",
          "symptom": "offline",
          "action": "poe-cycle",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "shared_drive",
              "ref": "wireless-recovery.md",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "notify_then_act",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        }
      ],
      "versions": [
        {
          "version": "2.0.8",
          "created_at": "2026-11-21T09:20:00Z",
          "reason": "source_change",
          "method": "signage|down|clear-player-cache",
          "before": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "trial",
            "attempts": 1,
            "successes": 1,
            "failures": 0,
            "success_rate": 1.0,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "9e25ca5e0a35d16f5924248af5242af208ae0c2ac719692803553c4b817f094b"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:10:00Z"
          },
          "after": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:20:00Z",
                "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          }
        },
        {
          "version": "2.0.9",
          "created_at": "2026-11-21T09:20:00Z",
          "reason": "verified_outcome",
          "method": "signage|down|clear-player-cache",
          "before": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "candidate",
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": null,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:20:00Z",
                "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "candidate"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          },
          "after": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "trial",
            "attempts": 1,
            "successes": 1,
            "failures": 0,
            "success_rate": 1.0,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:20:00Z",
                "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          }
        },
        {
          "version": "2.0.10",
          "created_at": "2026-11-21T09:20:00Z",
          "reason": "verified_outcome",
          "method": "av|hung|restart-room-app",
          "before": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "trial",
            "attempts": 1,
            "successes": 0,
            "failures": 1,
            "success_rate": 0.0,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:10:00Z"
          },
          "after": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "trial",
            "attempts": 2,
            "successes": 0,
            "failures": 2,
            "success_rate": 0.0,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          }
        }
      ]
    },
    {
      "ts": "09:30",
      "source_events": [],
      "method_events": [
        {
          "id": "EV-9c4fc984250db420",
          "ts": "2026-11-21T09:30:00Z",
          "source": "dry_run_verifier",
          "method": "signage|down|clear-player-cache",
          "old_state": "trial",
          "new_state": "promoted",
          "reason": "verified_outcome",
          "succeeded": true,
          "attempts": 2,
          "successes": 2,
          "success_rate": 1.0,
          "dry_run": true
        },
        {
          "id": "EV-3e85662bd26049c0",
          "ts": "2026-11-21T09:30:00Z",
          "source": "dry_run_verifier",
          "method": "av|hung|restart-room-app",
          "old_state": "trial",
          "new_state": "demoted",
          "reason": "regression",
          "succeeded": false,
          "attempts": 3,
          "successes": 0,
          "success_rate": 0.0,
          "dry_run": true
        }
      ],
      "notices": [
        {
          "id": "EV-5fca2c84b4d193d2",
          "event_id": "EV-9c4fc984250db420",
          "ts": "2026-11-21T09:30:00Z",
          "kind": "method_promoted",
          "source": "dry_run_verifier",
          "method": "signage|down|clear-player-cache",
          "old_state": "trial",
          "new_state": "promoted",
          "reason": "verified_outcome",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] Method adopted after verification. Source: dry_run_verifier. Method: digital signage · black or offline · Clear the player cache and reload. being verified -> adopted. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 方法验证通过，已采用。来源：dry_run_verifier。方法：数字标牌 · 黑屏或离线 · 清除播放器缓存并重新加载。验证中 → 已采用。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        },
        {
          "id": "EV-5b32ac23619cff52",
          "event_id": "EV-3e85662bd26049c0",
          "ts": "2026-11-21T09:30:00Z",
          "kind": "method_demoted",
          "source": "dry_run_verifier",
          "method": "av|hung|restart-room-app",
          "old_state": "trial",
          "new_state": "demoted",
          "reason": "regression",
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "dry_run": true,
          "message": {
            "en": "[dry run] Method paused after regression. Source: dry_run_verifier. Method: meeting-room AV · frozen or cannot join · Restart the room app (Zoom/Teams Rooms). being verified -> paused. Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "[演练] 方法效果变差，已停用。来源：dry_run_verifier。方法：会议室音视频 · 卡死或无法入会 · 重启房间应用 (Zoom/Teams Rooms)。验证中 → 已停用。权限保持“可自动执行”；学习过程没有增加权限。"
          }
        }
      ],
      "methods": [
        {
          "key": "av|hung|restart-room-app",
          "device": "av",
          "symptom": "hung",
          "action": "restart-room-app",
          "state": "demoted",
          "attempts": 3,
          "successes": 0,
          "failures": 3,
          "success_rate": 0.0,
          "sources": [
            {
              "source": "incident",
              "ref": "INC0098123",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial",
            "demoted"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:30:00Z"
        },
        {
          "key": "printer|jam|clear-queue",
          "device": "printer",
          "symptom": "jam",
          "action": "clear-queue",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "chat",
              "ref": "teams-print-884",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "3d560a0b6958e7daf63f394d774d82bcc8036802df309c724530c09303e8e3a8"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "printer|offline|power-cycle-printer",
          "device": "printer",
          "symptom": "offline",
          "action": "power-cycle-printer",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "email",
              "ref": "mail-printer-2201",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "d044437316ecc08730bc9e1dbbc32f4af9cdc90b7d43c89188f7d756a69869ae"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": false,
            "automatic": false,
            "physical": true,
            "tier": "human",
            "permission_source": "policy.json",
            "en": "Physical action remains human-only; no automatic permission was granted.",
            "zh": "物理操作仍须人工执行；未授予自动权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        },
        {
          "key": "signage|down|clear-player-cache",
          "device": "signage",
          "symptom": "down",
          "action": "clear-player-cache",
          "state": "promoted",
          "attempts": 2,
          "successes": 2,
          "failures": 0,
          "success_rate": 1.0,
          "sources": [
            {
              "source": "servicenow_kb",
              "ref": "KB001042",
              "updated_at": "2026-11-21T09:20:00Z",
              "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate",
            "trial",
            "candidate",
            "trial",
            "promoted"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "auto",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the auto tier; learning granted no permission.",
            "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:30:00Z"
        },
        {
          "key": "wifiap|offline|poe-cycle",
          "device": "wifiap",
          "symptom": "offline",
          "action": "poe-cycle",
          "state": "candidate",
          "attempts": 0,
          "successes": 0,
          "failures": 0,
          "success_rate": null,
          "sources": [
            {
              "source": "shared_drive",
              "ref": "wireless-recovery.md",
              "updated_at": "2026-11-21T09:00:00Z",
              "fingerprint": "bd69dc271cc16b5a74b9d513ce607f9cb7dabe474c441339b2c937d8b246c88a"
            }
          ],
          "lifecycle": [
            "observed",
            "candidate"
          ],
          "policy_effect": {
            "allowed": true,
            "automatic": true,
            "physical": false,
            "tier": "notify_then_act",
            "permission_source": "policy.json",
            "en": "Existing policy remains at the notify_then_act tier; learning granted no permission.",
            "zh": "权限保持“先提醒再执行”；学习过程没有增加权限。"
          },
          "updated_at": "2026-11-21T09:00:00Z"
        }
      ],
      "versions": [
        {
          "version": "2.0.11",
          "created_at": "2026-11-21T09:30:00Z",
          "reason": "verified_outcome",
          "method": "signage|down|clear-player-cache",
          "before": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "trial",
            "attempts": 1,
            "successes": 1,
            "failures": 0,
            "success_rate": 1.0,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:20:00Z",
                "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          },
          "after": {
            "key": "signage|down|clear-player-cache",
            "device": "signage",
            "symptom": "down",
            "action": "clear-player-cache",
            "state": "promoted",
            "attempts": 2,
            "successes": 2,
            "failures": 0,
            "success_rate": 1.0,
            "sources": [
              {
                "source": "servicenow_kb",
                "ref": "KB001042",
                "updated_at": "2026-11-21T09:20:00Z",
                "fingerprint": "10e0b1862f4e6871bf001bdf07b06ee99df992453b1e4df041ed485b549041ed"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "candidate",
              "trial",
              "promoted"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:30:00Z"
          }
        },
        {
          "version": "2.0.12",
          "created_at": "2026-11-21T09:30:00Z",
          "reason": "regression",
          "method": "av|hung|restart-room-app",
          "before": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "trial",
            "attempts": 2,
            "successes": 0,
            "failures": 2,
            "success_rate": 0.0,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:20:00Z"
          },
          "after": {
            "key": "av|hung|restart-room-app",
            "device": "av",
            "symptom": "hung",
            "action": "restart-room-app",
            "state": "demoted",
            "attempts": 3,
            "successes": 0,
            "failures": 3,
            "success_rate": 0.0,
            "sources": [
              {
                "source": "incident",
                "ref": "INC0098123",
                "updated_at": "2026-11-21T09:00:00Z",
                "fingerprint": "d20ac70c3d24ec6c4b32749a76024cd6423fb09dfcf8f6c377ee6125cdbbdd36"
              }
            ],
            "lifecycle": [
              "observed",
              "candidate",
              "trial",
              "demoted"
            ],
            "policy_effect": {
              "allowed": true,
              "automatic": true,
              "physical": false,
              "tier": "auto",
              "permission_source": "policy.json",
              "en": "Existing policy remains at the auto tier; learning granted no permission.",
              "zh": "权限保持“可自动执行”；学习过程没有增加权限。"
            },
            "updated_at": "2026-11-21T09:30:00Z"
          }
        }
      ]
    }
  ]
};
