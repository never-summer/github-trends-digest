#!/usr/bin/env python3
"""Снимает GitHub Trending (неделя и месяц) и считает квартальный топ.

Сохраняет срез в data/snapshots/<дата>.json и печатает JSON с тремя топами:
  week    — прирост звёзд за 7 дней (github.com/trending?since=weekly)
  month   — прирост за 30 дней (github.com/trending?since=monthly)
  quarter — сумма недельных приростов по всем срезам текущего календарного квартала

Запуск: python3 fetch_trending.py [YYYY-MM-DD]   (по умолчанию — сегодня, UTC)
Только стандартная библиотека. Падает, если Trending не отдал ни одного репозитория.
"""
import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "data" / "snapshots"
TOP_N = 10


def fetch(since):
    req = urllib.request.Request(
        f"https://github.com/trending?since={since}",
        headers={"User-Agent": "github-trends-digest", "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse(page, period):
    repos = []
    for art in re.findall(r'<article class="Box-row.*?</article>', page, re.S):
        name = re.search(r'<h2[^>]*>.*?href="/([^"/]+/[^"/]+)"', art, re.S)
        gained = re.search(r"([\d,]+) stars this " + period, art)
        if not name or not gained:
            continue
        desc = re.search(r"<p(?:\s[^>]*)?>(.*?)</p>", art, re.S)
        total = re.search(r'/stargazers"[^>]*>.*?</svg>\s*([\d,]+)', art, re.S)
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        repos.append({
            "repo": name.group(1),
            "description": text(desc.group(1)) if desc else "",
            "language": lang.group(1) if lang else "",
            "stars_total": int(total.group(1).replace(",", "")) if total else None,
            "stars_gained": int(gained.group(1).replace(",", "")),
        })
    return sorted(repos, key=lambda r: -r["stars_gained"])


def quarter_start(d):
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def quarter_top(today):
    start = quarter_start(today)
    sums, info, weeks = {}, {}, 0
    for p in sorted(SNAPSHOTS.glob("*.json")):
        d = date.fromisoformat(p.stem)
        if not start <= d <= today:
            continue
        weeks += 1
        for r in json.loads(p.read_text(encoding="utf-8"))["weekly"]:
            sums[r["repo"]] = sums.get(r["repo"], 0) + r["stars_gained"]
            info[r["repo"]] = r
    top = sorted(sums, key=lambda k: -sums[k])[:TOP_N]
    return {
        "from": start.isoformat(), "to": today.isoformat(), "snapshots": weeks,
        "items": [{**info[k], "stars_gained": sums[k]} for k in top],
    }


def main():
    today = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(timezone.utc).date()
    weekly, monthly = parse(fetch("weekly"), "week"), parse(fetch("monthly"), "month")
    if not weekly or not monthly:
        sys.exit(f"Trending пустой (weekly={len(weekly)}, monthly={len(monthly)}): разметка GitHub поменялась?")
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = {"date": today.isoformat(), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "weekly": weekly, "monthly": monthly}
    (SNAPSHOTS / f"{today.isoformat()}.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"date": today.isoformat(), "week": weekly[:TOP_N], "month": monthly[:TOP_N],
                      "quarter": quarter_top(today)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
