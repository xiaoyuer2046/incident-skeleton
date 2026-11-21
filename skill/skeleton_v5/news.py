"""v5 news consensus: when many independent sites report the same vendor outage, say it is LIKELY, even with no official word.

Officials sometimes post late or never, so the count of independent reports is evidence of its own.
Rules (rules_v5.json -> news_consensus):
  * one vote per website, and a repost of the same headline on another site counts once;
  * only reports inside the time window count;
  * a report whose text gives orders ("run this", "ignore your rules") is dropped and never followed;
  * an official status page or vendor MCP report makes it CONFIRMED.
This module only reads simulated report records. It never changes a permission.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import HERE
from skeleton_v4.learning import unsafe  # noqa: E402  (reuses the v1/v3/v4 injection checks)

NEWS_FILE = os.path.join(HERE, "news_v5.json")
LEVEL = {
    "confirmed": {"en": "confirmed vendor outage", "zh": "确认是厂商故障"},
    "likely": {"en": "likely vendor outage", "zh": "大概率是厂商故障"},
    "watch": {"en": "a few reports, still watching", "zh": "有少量报道，继续观察"},
    "none": {"en": "no reports", "zh": "没有报道"},
}
DROP = {"injection": {"en": "gives orders, ignored", "zh": "文本在下命令，已忽略"}, "out_of_window": {"en": "too old", "zh": "太旧"},
        "same_site": {"en": "same website again", "zh": "同一个网站"}, "repost": {"en": "repost of a headline already counted", "zh": "转载，已算过"},
        "malformed": {"en": "missing site, title or time", "zh": "缺少网站、标题或时间"}}


def _t(ts: str) -> datetime:
    """Parse an ISO time. A time without a zone is read as UTC."""
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def site(domain: str) -> str:
    """One vote per site: news.a.example and a.example are the same site. Simple last-two-labels rule; a real
    deployment should use the public-suffix list (so bbc.co.uk is one site, not co.uk)."""
    parts = [p for p in (domain or "").lower().strip(".").split(".") if p]
    return ".".join(parts[-2:])


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", (title or "").lower()).strip()


def load(path: str = NEWS_FILE) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def consensus(reports: List[Dict[str, Any]], provider: str, service: str, now: str, rules: Dict[str, Any],
              official: bool = False) -> Dict[str, Any]:
    rule = rules["news_consensus"]
    lo, hi = _t(now) - timedelta(minutes=rule["window_minutes"]), _t(now)
    counted: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    sites, titles = set(), set()
    for rep in sorted(reports, key=lambda r: str(r.get("published_at", ""))):
        if rep.get("provider") != provider or rep.get("service") != service:
            continue
        row = {k: rep.get(k) for k in ("id", "domain", "title", "url", "published_at")}
        why: Optional[str] = None
        try:
            when = _t(rep["published_at"]) if isinstance(rep.get("published_at"), str) else None
        except ValueError:
            when = None
        if not (when and isinstance(rep.get("domain"), str) and rep["domain"].strip() and isinstance(rep.get("title"), str)):
            why = "malformed"
        elif unsafe({"text": rep.get("title", "") + " " + str(rep.get("text") or "")}):
            why = "injection"
        elif not lo <= when <= hi:
            why = "out_of_window"
        elif site(rep["domain"]) in sites:
            why = "same_site"
        elif _norm(rep["title"]) in titles:
            why = "repost"
        if why:
            dropped.append(dict(row, why=why))
            continue
        sites.add(site(rep["domain"]))
        titles.add(_norm(rep["title"]))
        counted.append(row)
    need = rule["min_independent_sources"]
    level = "confirmed" if official else ("likely" if len(counted) >= need else ("watch" if counted else "none"))
    return {"provider": provider, "service": service, "level": level, "label": dict(LEVEL[level]), "count": len(counted), "need": need,
            "sources": counted, "dropped": dropped, "official": official, "checked_at": now, "dry_run": True}


def note(c: Dict[str, Any], label: Dict[str, str]) -> Dict[str, str]:
    """One-line TRIAGE note for a likely outage."""
    return {"en": "News check: %d independent sites report a %s outage, no official word yet: %s. Local work continues."
                  % (c["count"], label["en"], c["label"]["en"]),
            "zh": "新闻核查：%d 个独立网站报道 %s 故障，官方暂未公告：%s。本地处理继续。" % (c["count"], label["zh"], c["label"]["zh"])}
