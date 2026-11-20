#!/usr/bin/env python3
"""
Incident Skeleton: the runnable skeleton.  (中英双语 / bilingual: --lang zh|en)

One incident-response state machine (RECEIVE -> TRIAGE -> INVESTIGATE ->
MITIGATE -> RESOLVE -> LOG), crewed by four device handlers (printer, digital
signage, meeting-room AV, wireless AP). The shared core drives every alert;
each handler plugs its own read-only checks into INVESTIGATE and its own
prescribed fixes into MITIGATE.

Read-only by default. For automatic repair see ../remediation/remediate.py.

Usage:
  python3 run_incident.py --type printer --target 10.0.4.21 --message "PAPER JAM (13.20)"
  python3 run_incident.py --sample --lang zh
"""
import argparse, os, re, shutil, subprocess, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "..", "logs")

# Language: --lang, else INCIDENT_LANG, else the system locale, else English.
LANG = os.environ.get("INCIDENT_LANG") or ("zh" if os.environ.get("LANG", "").lower().startswith("zh") else "en")


def set_lang(lang):
    global LANG
    if lang in ("zh", "en"):
        LANG = lang


def T(zh, en):
    return zh if LANG == "zh" else en


SKELETON = [
    ("RECEIVE",     "shared", ("收告警：类型 / 严重度 / 来源 / 消息", "alert in: type / severity / source / message")),
    ("TRIAGE",      "shared", ("分类并打分严重度，决定要不要动手", "classify and score severity, decide act or not")),
    ("INVESTIGATE", "crew",   ("为这类设备收集上下文", "gather context for this device type")),
    ("MITIGATE",    "crew",   ("为这类设备动手减小影响", "act to cut impact for this device type")),
    ("RESOLVE",     "shared", ("复查健康，确认恢复", "re-check health, confirm recovery")),
    ("LOG",         "shared", ("写事件复盘记录", "write the postmortem record")),
]

PRINTER_ERRORS = {
    "13.20": ("定影器/出纸区卡纸", "fuser area paper jam"),
    "13.01": ("进纸区卡纸", "input area jam"),
    "41.20": ("扫描仪错误", "scanner error"),
    "50.1":  ("定影器故障", "fuser failure"),
    "51.20": ("激光器错误", "laser/scanner error"),
    "79":    ("固件错误，尝试断电重启", "firmware error, power-cycle"),
}


def which(name):
    return shutil.which(name) is not None


def run_cmd(cmd, timeout=6):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.returncode == 0), (p.stdout or p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, T("超时", "timeout")
    except FileNotFoundError:
        return False, T("命令不存在: ", "command not found: ") + cmd[0]


def is_url(t):
    return (t or "").lower().startswith("http")


def host_of(t):
    return re.sub(r"^https?://", "", t).split("/")[0] if is_url(t) else t


def ping(host):
    if not host:
        return False, T("(无目标)", "(no target)")
    ok, txt = run_cmd(["ping", "-c", "2", host])
    if ok:
        return True, T("可达", "reachable")
    return False, T("不可达: ", "unreachable: ") + (txt.splitlines()[-1] if txt else T("无响应", "no reply"))


def curl(url):
    if not url:
        return False, T("(无目标)", "(no target)")
    ok, code = run_cmd(["curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", url])
    return ok, ("HTTP " + code if ok else T("请求失败: ", "request failed: ") + code)


def snmpget(host, oid):
    return run_cmd(["snmpget", "-v2c", "-c", "public", host, oid], timeout=5)


def extract_code(msg):
    m = re.search(r"(\d{2}(?:\.\d{1,2})?)", msg or "")
    return m.group(1) if m else None


def _row(label, result, status):
    return (label, result, status)


def investigate_printer(a):
    host = host_of(a.target) if a.target else None
    out = []
    if host:
        ok, txt = ping(host)
        out.append(_row("ping " + host, txt, "ok" if ok else "err"))
        if which("snmpget"):
            ok, txt = snmpget(host, "1.3.6.1.2.1.25.3.5.1.2.1")
            out.append(_row(T("SNMP 状态", "SNMP status"), (txt[:120] if txt else T("无返回", "no reply")), "ok" if ok else "warn"))
        else:
            out.append(_row(T("SNMP 状态", "SNMP status"), T("snmpget 未安装，跳过", "snmpget not installed, skipped"), "warn"))
    else:
        out.append(_row("ping", T("无目标", "no target"), "warn"))
    code = extract_code(a.message)
    if code:
        zh, en = PRINTER_ERRORS.get(code, ("未知错误码，查厂商手册", "unknown code, check the vendor manual"))
        out.append(_row(T("错误码 ", "error code ") + code, T(zh, en), "warn"))
    else:
        out.append(_row(T("错误码", "error code"), T("消息里没找到错误码", "no error code in the message"), "warn"))
    return out


def investigate_signage(a):
    t, out = a.target, []
    if is_url(t):
        ok, txt = curl(t)
        out.append(_row("curl " + t, txt, "ok" if ok else "err"))
        ok, txt = ping(host_of(t))
        out.append(_row("ping " + host_of(t), txt, "ok" if ok else "warn"))
    else:
        ok, txt = ping(t)
        out.append(_row("ping " + (t or "?"), txt, "ok" if ok else "err"))
        out.append(_row(T("CMS 排期/推送", "CMS schedule/push"), T("没给 CMS 地址，跳过", "no CMS URL, skipped"), "warn"))
    return out


def investigate_av(a):
    t, out = a.target, []
    if is_url(t):
        ok, txt = curl(t)
        out.append(_row(T("curl 控制器 API ", "curl controller API ") + t, txt, "ok" if ok else "err"))
        ok, txt = ping(host_of(t))
        out.append(_row("ping " + host_of(t), txt, "ok" if ok else "warn"))
    else:
        ok, txt = ping(t)
        out.append(_row(T("ping 控制器 ", "ping controller ") + (t or "?"), txt, "ok" if ok else "err"))
        out.append(_row(T("Zoom/Teams 房间状态", "Zoom/Teams room status"), T("没给房间 API，跳过", "no room API, skipped"), "warn"))
    out.append(_row(T("麦克风/摄像头", "mic / camera"), T("需到场或管理平台确认", "needs on-site or admin-console check"), "warn"))
    return out


def investigate_wifiap(a):
    t, out = a.target, []
    if is_url(t):
        ok, txt = curl(t)
        out.append(_row(T("curl 控制器 API ", "curl controller API ") + t, txt, "ok" if ok else "err"))
        ok, txt = ping(host_of(t))
        out.append(_row("ping " + host_of(t), txt, "ok" if ok else "warn"))
    else:
        ok, txt = ping(t)
        out.append(_row("ping AP " + (t or "?"), txt, "ok" if ok else "err"))
        if which("snmpget"):
            ok, txt = snmpget(t, "1.3.6.1.2.1.2.2.1.8")
            out.append(_row(T("SNMP 端口状态", "SNMP port status"), (txt[:120] if txt else T("无返回", "no reply")), "ok" if ok else "warn"))
        else:
            out.append(_row(T("SNMP 端口状态", "SNMP port status"), T("snmpget 未安装，跳过", "snmpget not installed, skipped"), "warn"))
    out.append(_row(T("客户端/射频", "clients / radio"), T("需控制器 API（--target <controller-url>）", "needs the controller API (--target <controller-url>)"), "warn"))
    return out


# (zh, en, safe_to_auto)
MITIGATE = {
    "printer": [("现场清除卡纸 / 换耗材", "Clear the jam / swap supplies on site", False),
                ("重启打印后台 (cups)", "Restart the print spooler (cups)", True),
                ("删除并重新添加打印队列", "Remove and re-add the print queue", False),
                ("断电重启打印机", "Power-cycle the printer", False)],
    "signage": [("重启播放器", "Reboot the player", False),
                ("CMS 重新推送内容 / 排期", "Re-push content / schedule from the CMS", False),
                ("重新插拔 HDMI", "Reseat the HDMI cable", False),
                ("换备用播放器", "Swap in a spare player", False)],
    "av":      [("重启控制器", "Reboot the controller", False),
                ("重启编解码器 / 房间主机", "Reboot the codec / room PC", False),
                ("重启房间应用", "Restart the room app", True),
                ("重新插拔 USB 麦 / 摄", "Reseat the USB mic / camera", False),
                ("派 AV 工程师到场", "Dispatch an AV technician", False)],
    "wifiap":  [("控制器 API 重启 AP", "Reboot the AP through the controller API", True),
                ("PoE 端口断电再上电", "Power-cycle the PoE port", False),
                ("射频调优：换信道 / 调功率", "Radio tuning: channel / power", False),
                ("补 AP / 换设备", "Add or replace an AP", False)],
}

CREW = {
    "printer": {"icon": "🖨️", "zh": "打印机", "en": "Printer", "inv": investigate_printer},
    "signage": {"icon": "📺", "zh": "数字标牌", "en": "Digital signage", "inv": investigate_signage},
    "av":      {"icon": "🎥", "zh": "会议室音视频", "en": "Meeting-room AV", "inv": investigate_av},
    "wifiap":  {"icon": "📶", "zh": "无线 AP", "en": "Wireless AP", "inv": investigate_wifiap},
}


def label(k):
    return CREW[k][LANG]


C = {"ok": "\033[32m", "warn": "\033[33m", "err": "\033[31m", "crew": "\033[38;5;208m",
     "shared": "\033[38;5;141m", "dim": "\033[2m", "bold": "\033[1m", "rst": "\033[0m"}


def col(name, s):
    return f"{C[name]}{s}{C['rst']}" if ((sys.stdout.isatty() or os.environ.get("FORCE_COLOR")) and name in C) else s


def triage(a):
    words = ("can't", "cannot", "offline", "hung", "dropping", "无法", "黑屏", "卡死", "掉线", "离线")
    return ("high" if any(w in (a.message or "").lower() for w in words) else "medium"), True


def sev_text(s):
    return {"high": T("高", "high"), "medium": T("中", "medium")}[s]


def run_incident(a, apply_fixes=False):
    crew = CREW[a.type]
    total = len(SKELETON)
    record = []
    print()
    print(col("bold", f"  💀 Incident Skeleton — {crew['icon']} {label(a.type)} {T('班底', 'crew')}"))
    print(col("dim", "  " + "═" * 54))
    for idx, (name, kind, desc) in enumerate(SKELETON, 1):
        head = f"[{idx}/{total}] {name}"
        tag = T("共享", "SHARED") if kind == "shared" else T("班底", "CREW")
        print(f"╰ {col('shared' if kind == 'shared' else 'crew', head)}  {col('dim', tag)}")
        print(col("dim", "  " + T(*desc)))
        rec = {"state": name, "kind": kind}
        if name == "RECEIVE":
            print(f"  {T('类型', 'type')}={label(a.type)}  {T('来源', 'source')}={a.source or a.target or '?'}  {T('消息', 'message')}={a.message}")
        elif name == "TRIAGE":
            sev, act = triage(a)
            print(f"  {T('严重度', 'severity')}={col('warn' if sev == 'high' else 'ok', sev_text(sev))}  → {T('动手处理', 'act')}")
            rec["data"] = {"severity": sev_text(sev), "act": act}
        elif name == "INVESTIGATE":
            rec["data"] = []
            for lab, detail, status in crew["inv"](a):
                print(f"  {col(status, {'ok': '✓', 'warn': '·', 'err': '✗'}[status])} {lab}")
                print(col("dim", f"      {detail}"))
                rec["data"].append({"check": lab, "result": detail, "status": status})
        elif name == "MITIGATE":
            rec["data"] = []
            for i, (zh, en, safe) in enumerate(MITIGATE[a.type], 1):
                run = bool(apply_fixes and safe)
                mark = T("执行", "run") if run else (T("可执行", "can run") if safe else T("需人工", "human"))
                print(f"  {i}. [{mark}] {T(zh, en)}")
                rec["data"].append({"step": T(zh, en), "safe": safe, "executed": run})
            if not apply_fixes:
                print(col("dim", "  " + T("(默认只读。要自动修复请用 remediation/remediate.py)",
                                          "(read-only by default. For automatic repair use remediation/remediate.py)")))
        elif name == "RESOLVE":
            host = host_of(a.target) if a.target else None
            if host and not is_url(a.target):
                ok, txt = ping(host)
                print(f"  {T('复查', 're-check')} ping {host}: {col('ok' if ok else 'err', txt)}")
            elif a.target:
                ok, txt = curl(a.target)
                print(f"  {T('复查', 're-check')} curl {a.target}: {col('ok' if ok else 'err', txt)}")
            else:
                ok = True
                print(col("dim", "  " + T("(没有复查目标)", "(no target to re-check)")))
            rec["data"] = {"recovered": ok}
        elif name == "LOG":
            print(col("dim", "  " + T("写入复盘…", "writing the postmortem…")))
        record.append(rec)
        print()
        time.sleep(0.05)
    pm = write_postmortem(a, crew, record)
    print(col("ok", f"  ✅ {T('事件闭环。复盘已写入', 'incident closed. Postmortem written to')}: {pm}"))
    print()
    return pm


def write_postmortem(a, crew, record):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"postmortem-{a.type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md")
    get = lambda n, d: next((r for r in record if r["state"] == n), {}).get("data", d)
    tri, inv, mit, res = get("TRIAGE", {}), get("INVESTIGATE", []), get("MITIGATE", []), get("RESOLVE", {})
    L = [f"# {T('事件复盘', 'Incident postmortem')} — {crew['icon']} {label(a.type)}",
         f"\n- {T('时间', 'time')}: {datetime.now().isoformat(timespec='seconds')}",
         f"- {T('设备/来源', 'device / source')}: {a.source or a.target or '?'}",
         f"- {T('告警消息', 'alert')}: {a.message}",
         f"- {T('严重度', 'severity')}: {tri.get('severity', '?')}",
         f"- {T('恢复', 'recovered')}: {res.get('recovered', '?')}",
         f"\n## {T('走过的骨架（同一套六步）', 'The skeleton it walked (the same six steps)')}\n"]
    for r in record:
        L.append(f"- **{r['state']}** ({T('共享', 'shared') if r['kind'] == 'shared' else T('班底', 'crew')})")
    L.append(f"\n## {T('排查发现', 'Findings')} (INVESTIGATE)\n")
    L += [f"- [{x.get('status', '?')}] {x.get('check', '')}: {x.get('result', '')}" for x in inv]
    L.append(f"\n## {T('处理步骤', 'Steps')} (MITIGATE)\n")
    for x in mit:
        tag = T("已执行", "ran") if x.get("executed") else (T("可执行", "can run") if x.get("safe") else T("需人工", "human"))
        L.append(f"- [{tag}] {x.get('step', '')}")
    L.append("\n---\n*" + T("由 Incident Skeleton 生成。一套骨架，四套班底。", "Generated by Incident Skeleton. One skeleton, four crews.") + "*")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


SAMPLES = [
    argparse.Namespace(type="printer", target="1.1.1.1", source="SNMP 10.0.4.21", message="PAPER JAM (13.20)"),
    argparse.Namespace(type="signage", target="https://example.com", source="CMS / lobby east", message="player offline 14m"),
    argparse.Namespace(type="av", target="192.0.2.1", source="Zoom Rooms / 3F-301", message="can't join meeting, panel hung"),
    argparse.Namespace(type="wifiap", target="1.1.1.1", source="controller / floor 3", message="AP offline, clients dropping"),
]


def main():
    ap = argparse.ArgumentParser(description="Incident Skeleton: one skeleton, four crews")
    ap.add_argument("--type", choices=list(CREW))
    ap.add_argument("--target")
    ap.add_argument("--source", default="")
    ap.add_argument("--message", default="")
    ap.add_argument("--lang", choices=["zh", "en"], help="output language (default: system locale, else en)")
    ap.add_argument("--apply", action="store_true", help="run the steps marked safe (default read-only)")
    ap.add_argument("--sample", action="store_true", help="run one built-in alert of each type")
    args = ap.parse_args()
    if args.lang:
        set_lang(args.lang)
    if args.sample:
        for s in SAMPLES:
            run_incident(s)
        return
    if not args.type:
        ap.error("--type is required (or use --sample)")
    if not args.message:
        ap.error("--message is required")
    run_incident(args, apply_fixes=args.apply)


if __name__ == "__main__":
    main()
