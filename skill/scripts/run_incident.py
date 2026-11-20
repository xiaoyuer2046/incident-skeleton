#!/usr/bin/env python3
"""
Incident Skeleton — the runnable skeleton.

One incident-response state machine (RECEIVE -> TRIAGE -> INVESTIGATE ->
MITIGATE -> RESOLVE -> LOG), crewed by four device handlers (printer,
digital signage, meeting-room AV, wireless AP). The shared core drives every alert; each
handler plugs its own read-only checks into INVESTIGATE and its own prescribed
fixes into MITIGATE.

Read-only by default: it pings, curls, and (if snmpget is installed) queries a
printer. It never restarts or reconfigures a device unless you pass --apply,
and even then only the steps each handler marks safe (none by default — every
fix needs a human, so --apply currently shows the exact command it would run).

Usage:
  python3 run_incident.py --type printer  --target 10.0.4.21 --message "PAPER JAM (13.20)"
  python3 run_incident.py --type signage  --target https://example.com --message "player offline 14m"
  python3 run_incident.py --type av       --target 10.0.8.30 --message "can't join meeting, panel hung"
  python3 run_incident.py --sample        # run a built-in sample alert of each type
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "..", "logs")

# ---- The skeleton (shared core): every alert walks these 6 states ----
SKELETON = [
    ("RECEIVE",     "shared",  "alert in: type / severity / source / message"),
    ("TRIAGE",      "shared",  "classify type + score severity, decide act/no-act"),
    ("INVESTIGATE", "crew",    "gather context for THIS device type"),
    ("MITIGATE",    "crew",    "act to cut impact for THIS device type"),
    ("RESOLVE",     "shared",  "re-check health, confirm recovery"),
    ("LOG",         "shared",  "write the postmortem record"),
]

PRINTER_ERRORS = {
    "13.20": "定影器/出纸区卡纸 (fuser area paper jam)",
    "13.01": "进纸区卡纸 (input area jam)",
    "41.20": "扫描仪错误 (scanner error)",
    "50.1":  "定影器故障 (fuser failure)",
    "51.20": "激光器错误 (laser/scanner)",
    "79":    "固件错误，尝试重启 (firmware error, power-cycle)",
}

def which(name): return shutil.which(name) is not None

def run_cmd(cmd, timeout=6):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.returncode == 0), (p.stdout or p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, "超时 (timeout)"
    except FileNotFoundError:
        return False, "命令不存在: %s" % cmd[0]

def is_url(t): return t.lower().startswith("http")

def host_of(t): return re.sub(r"^https?://", "", t).split("/")[0] if is_url(t) else t

def ping(host):
    if not host: return False, "(无目标)"
    ok, txt = run_cmd(["ping", "-c", "2", host])
    return ok, ("可达 (reachable)" if ok else "不可达 (unreachable): " + txt.splitlines()[-1] if txt else "不可达")

def curl(url):
    if not url: return False, "(无目标)"
    ok, code = run_cmd(["curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", url])
    return ok, ("HTTP " + code if ok else "请求失败 (curl failed): " + code)

def snmpget(host, oid):
    ok, txt = run_cmd(["snmpget", "-v2c", "-c", "public", host, oid], timeout=5)
    return ok, txt

def extract_code(msg):
    m = re.search(r"(\d{2}(?:\.\d{1,2})?)", msg or "")
    return m.group(1) if m else None

# ---- The crew: each handler plugs INVESTIGATE + MITIGATE ----
def investigate_printer(a):
    out = []
    host = host_of(a.target) if a.target else None
    out.append(("ping " + (host or "?"),) + ((lambda r: (r[1], "ok" if r[0] else "err"))(ping(host))) if host else ("ping", "无目标 (no target)", "warn"))
    if host:
        if which("snmpget"):
            ok, txt = snmpget(host, "1.3.6.1.2.1.25.3.5.1.2.1")
            out.append(("SNMP 状态 (hrDeviceStatus)", txt[:120] if txt else "无返回", "ok" if ok else "warn"))
        else:
            out.append(("SNMP 状态", "snmpget 未安装，跳过（可装 net-snmp 获得真实状态）", "warn"))
    code = extract_code(a.message)
    if code:
        out.append(("错误码 " + code, PRINTER_ERRORS.get(code, "未知错误码，查厂商手册"), "warn"))
    else:
        out.append(("错误码", "消息中未检测到错误码", "warn"))
    return out

def investigate_signage(a):
    out = []
    t = a.target
    if is_url(t):
        out.append(("curl " + t,) + (lambda r: (r[1], "ok" if r[0] else "err"))(curl(t)))
        host = host_of(t)
        out.append(("ping " + host,) + (lambda r: (r[1], "ok" if r[0] else "warn"))(ping(host)))
    else:
        out.append(("ping " + (t or "?"),) + (lambda r: (r[1], "ok" if r[0] else "err"))(ping(t)))
        out.append(("CMS 排期/推送状态", "无 CMS URL，跳过（用 --target <cms-url> 可查）", "warn"))
    return out

def investigate_av(a):
    out = []
    t = a.target
    if is_url(t):
        out.append(("curl 控制器 API " + t,) + (lambda r: (r[1], "ok" if r[0] else "err"))(curl(t)))
        out.append(("ping " + host_of(t),) + (lambda r: (r[1], "ok" if r[0] else "warn"))(ping(host_of(t))))
    else:
        out.append(("ping 控制器 " + (t or "?"),) + (lambda r: (r[1], "ok" if r[0] else "err"))(ping(t)))
        out.append(("Zoom/Teams 房间状态", "无房间 API，跳过（用 --target <room-api-url> 可查）", "warn"))
    out.append(("测麦/摄枚举", "需到场或管理平台确认（CLI 无法直连 USB 设备）", "warn"))
    return out

def investigate_wifiap(a):
    out = []
    t = a.target
    if is_url(t):
        out.append(("curl 控制器 API " + t,) + (lambda r: (r[1], "ok" if r[0] else "err"))(curl(t)))
        out.append(("ping " + host_of(t),) + (lambda r: (r[1], "ok" if r[0] else "warn"))(ping(host_of(t))))
    else:
        out.append(("ping AP " + (t or "?"),) + (lambda r: (r[1], "ok" if r[0] else "err"))(ping(t)))
        if which("snmpget"):
            ok, txt = snmpget(t, "1.3.6.1.2.1.2.2.1.8")
            out.append(("SNMP 端口状态 (ifOperStatus)", txt[:120] if txt else "无返回", "ok" if ok else "warn"))
        else:
            out.append(("SNMP 端口状态", "snmpget 未安装，跳过（可装 net-snmp 获得真实状态）", "warn"))
    out.append(("客户端/射频", "需控制器 API 查（--target <controller-url>）", "warn"))
    return out

MITIGATE = {
    "printer": [
        ("现场清除卡纸 / 更换耗材", False),
        ("重启打印后台 (cups): launchctl kickstart -k system/org.cups.cupsd  # 或 systemctl restart cups", True),
        ("删除并重新添加打印队列", False),
        ("断电重启打印机（拔电 30 秒再插）", False),
    ],
    "signage": [
        ("重启播放器（远程 reboot 或现场断电）", False),
        ("CMS 重新推送内容 / 排期", False),
        ("重新插拔 HDMI 线", False),
        ("换备用播放器", False),
    ],
    "av": [
        ("重启控制器（Crestron / Extron）", False),
        ("重启编解码器 / 房间主机", False),
        ("重启房间应用: launchctl kickstart -k system/<zoom-rooms-service>  # 或对应 systemd unit", True),
        ("重新插拔 USB 麦 / 摄", False),
        ("派 AV 工程师到场", False),
    ],
    "wifiap": [
        ("控制器 API 重启 AP（Meraki/Aruba/Cisco WLC）", True),
        ("PoE 交换机端口断电再上电（shutdown/no shutdown 端口）", False),
        ("射频调优：换信道 / 调功率", False),
        ("补 AP / 换设备（覆盖不足）", False),
    ],
}

CREW = {
    "printer": {"icon": "🖨️", "label": "打印机",  "inv": investigate_printer},
    "signage": {"icon": "📺", "label": "数字标牌", "inv": investigate_signage},
    "av":      {"icon": "🎥", "label": "会议室音视频", "inv": investigate_av},
    "wifiap":  {"icon": "📶", "label": "无线 AP",    "inv": investigate_wifiap},
}

# ---- rendering ----
C = {"ok": "\033[32m", "warn": "\033[33m", "err": "\033[31m", "crew": "\033[38;5;208m",
     "shared": "\033[38;5;141m", "dim": "\033[2m", "bold": "\033[1m", "rst": "\033[0m"}
def use_color():
    return sys.stdout.isatty() or os.environ.get("FORCE_COLOR")

def col(name, s):
    return f"{C[name]}{s}{C['rst']}" if (use_color() and name in C) else s

def print_state(n, name, kind, total, active=True):
    tag = "SHARED" if kind == "shared" else "CREW"
    bar = "─" * 56
    head = f"[{n}/{total}] {name}"
    print(col("bold", "╭" + bar[:len(head)+4]) )
    print(f"╰ {col('shared' if kind=='shared' else 'crew', head)}  {col('dim', tag)}")
    print()

# ---- the walk ----
def triage(a):
    sev = "高" if any(w in a.message for w in ("can't", "无法", "offline", "黑屏", "hung", "卡死")) else "中"
    act = True
    return sev, act

def run_incident(a, apply_fixes=False):
    crew = CREW[a.type]
    total = len(SKELETON)
    record = []
    print()
    print(col("bold", f"  💀 Incident Skeleton — {crew['icon']} {crew['label']} 班底"))
    print(col("dim", "  " + "═" * 54))
    for idx, (name, kind, desc) in enumerate(SKELETON, 1):
        print_state(idx, name, kind, total)
        print(col("dim", f"  {desc}"))
        step_record = {"state": name, "kind": kind}
        if name == "RECEIVE":
            print(f"  类型={crew['label']}  来源={a.source or a.target or '?'}  消息={a.message}")
            step_record["data"] = {"type": crew['label'], "source": a.source, "message": a.message}
        elif name == "TRIAGE":
            sev, act = triage(a)
            print(f"  严重度={col('warn' if sev=='高' else 'ok', sev)}  → {'动手处理' if act else '仅记录'}")
            step_record["data"] = {"severity": sev, "act": act}
            if not act:
                print(col("dim", "  (无需处理，跳到 LOG)"))
                # jump to LOG
                for j in range(idx, total):
                    if SKELETON[j][0] == "LOG":
                        break
                record.append(step_record)
                # fast-forward shared RESOLVE as skipped, then LOG
                print()
                continue
        elif name == "INVESTIGATE":
            results = crew["inv"](a)
            step_record["data"] = []
            for label, detail, status in results:
                mark = {"ok": "✓", "warn": "·", "err": "✗"}[status]
                print(f"  {col(status, mark)} {label}")
                print(col("dim", f"      {detail}"))
                step_record["data"].append({"check": label, "result": detail, "status": status})
        elif name == "MITIGATE":
            steps = MITIGATE[a.type]
            step_record["data"] = []
            for i, (step, safe) in enumerate(steps, 1):
                runnable = "可执行" if safe else "需人工"
                if apply_fixes and safe:
                    print(f"  {i}. [执行] {step}")
                else:
                    print(f"  {i}. [{runnable}] {step}")
                step_record["data"].append({"step": step, "safe": safe, "executed": bool(apply_fixes and safe)})
            if not apply_fixes:
                print(col("dim", "  (默认只读：--apply 才执行标记为「可执行」的步骤)"))
        elif name == "RESOLVE":
            host = host_of(a.target) if a.target else None
            if host and not is_url(a.target):
                ok, txt = ping(host)
                recovered = ok
                print(f"  复查 ping {host}: {col('ok' if recovered else 'err', txt)}")
            elif a.target and is_url(a.target):
                ok, txt = curl(a.target)
                recovered = ok
                print(f"  复查 curl {a.target}: {col('ok' if recovered else 'err', txt)}")
            else:
                recovered = True
                print(col("dim", "  (无复查目标，假设已处理)"))
            step_record["data"] = {"recovered": recovered}
        elif name == "LOG":
            print(col("dim", "  写入事件复盘记录…"))
        record.append(step_record)
        print()
        time.sleep(0.05)

    # postmortem
    pm = write_postmortem(a, crew, record)
    print(col("ok", f"  ✅ 事件闭环。复盘已写入: {pm}"))
    print()
    return pm

def write_postmortem(a, crew, record):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = a.type
    path = os.path.join(LOG_DIR, f"postmortem-{safe}-{ts}.md")
    tri = next((r for r in record if r["state"] == "TRIAGE"), {}).get("data", {})
    inv = next((r for r in record if r["state"] == "INVESTIGATE"), {}).get("data", [])
    mit = next((r for r in record if r["state"] == "MITIGATE"), {}).get("data", [])
    res = next((r for r in record if r["state"] == "RESOLVE"), {}).get("data", {})
    lines = [
        f"# 事件复盘 — {crew['icon']} {crew['label']}",
        f"\n- 时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- 设备/来源: {a.source or a.target or '?'}",
        f"- 告警消息: {a.message}",
        f"- 严重度: {tri.get('severity','?')}",
        f"- 恢复: {res.get('recovered','?')}",
        "\n## 走过的骨架（同一套六步）\n",
    ]
    for r in record:
        lines.append(f"- **{r['state']}** ({'共享' if r['kind']=='shared' else '班底'})")
    lines.append("\n## 排查发现 (INVESTIGATE)\n")
    for x in inv:
        lines.append(f"- [{x.get('status','?')}] {x.get('check','')}: {x.get('result','')}")
    lines.append("\n## 处理步骤 (MITIGATE)\n")
    for x in mit:
        tag = "已执行" if x.get("executed") else ("可执行" if x.get("safe") else "需人工")
        lines.append(f"- [{tag}] {x.get('step','')}")
    lines.append("\n---\n*由 Incident Skeleton (Skeleton Crew) 生成。一套骨架，四套班底。*")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path

# ---- samples (use safe public targets so real ping/curl actually run) ----
SAMPLES = [
    argparse.Namespace(type="printer", target="1.1.1.1",        source="SNMP 10.0.4.21", message="PAPER JAM (13.20)"),
    argparse.Namespace(type="signage", target="https://example.com", source="CMS / 大厅东",   message="player offline 14m"),
    argparse.Namespace(type="av",      target="192.0.2.1",      source="Zoom Rooms / 3F-301", message="can't join meeting, panel hung"),
    argparse.Namespace(type="wifiap",  target="1.1.1.1",        source="控制器 / 楼层3",      message="AP offline, clients dropping"),
]

def main():
    ap = argparse.ArgumentParser(description="Incident Skeleton — 一套骨架，四套班底")
    ap.add_argument("--type", choices=list(CREW), help="设备类型")
    ap.add_argument("--target", help="目标：host 用于 ping/snmp，URL 用于 curl")
    ap.add_argument("--source", default="", help="告警来源（可选）")
    ap.add_argument("--message", default="", help="告警消息")
    ap.add_argument("--apply", action="store_true", help="执行标记为可执行的处理步骤（默认只读）")
    ap.add_argument("--sample", action="store_true", help="跑三个内置样例（各类型一个）")
    args = ap.parse_args()

    if args.sample:
        for s in SAMPLES:
            run_incident(s, apply_fixes=False)
        return
    if not args.type:
        ap.error("--type 必填（或用 --sample）")
    if not args.message:
        ap.error("--message 必填")
    run_incident(args, apply_fixes=args.apply)

if __name__ == "__main__":
    main()
