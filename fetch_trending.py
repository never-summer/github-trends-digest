#!/usr/bin/env python3
"""Срезы GitHub Trending для дайджеста.

  python3 fetch_trending.py fetch [YYYY-MM-DD]
      Снимает Trending за неделю и месяц, скачивает README репозиториев из топов
      и сохраняет всё в data/snapshots/<дата>.json. Нужен доступ к github.com —
      запускается в GitHub Actions (.github/workflows/fetch-trending.yml).

  python3 fetch_trending.py show [YYYY-MM-DD]
      Ничего не скачивает. Читает срез за дату и печатает JSON с тремя топами
      и README проектов — это вход для агента, который пишет выпуск:
        week    — прирост звёзд за 7 дней (github.com/trending?since=weekly)
        month   — прирост за 30 дней (github.com/trending?since=monthly)
        quarter — сумма недельных приростов по срезам текущего календарного квартала

Дата по умолчанию — сегодня (UTC). Только стандартная библиотека.
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "data" / "snapshots"
TOP_N = 10
README_CHARS = 3000


def get(url, accept=None):
    headers = {"User-Agent": "github-trends-digest", "Accept-Language": "en-US"}
    if accept:
        headers["Accept"] = accept
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


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


def readme(repo):
    """Начало README без картинок и бейджей; пустая строка, если README нет."""
    try:
        raw = get(f"https://api.github.com/repos/{repo}/readme", "application/vnd.github.raw")
    except urllib.error.HTTPError:
        return ""
    raw = re.sub(r"<img[^>]*>|!\[[^\]]*\]\([^)]*\)|\[!\[.*?\]\(.*?\)\]\(.*?\)", "", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
    return raw[:README_CHARS]


def quarter_start(d):
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def quarter_top(day):
    start = quarter_start(day)
    sums, info, weeks = {}, {}, 0
    for p in sorted(SNAPSHOTS.glob("*.json")):
        d = date.fromisoformat(p.stem)
        if not start <= d <= day:
            continue
        weeks += 1
        for r in json.loads(p.read_text(encoding="utf-8"))["weekly"]:
            sums[r["repo"]] = sums.get(r["repo"], 0) + r["stars_gained"]
            info[r["repo"]] = r
    top = sorted(sums, key=lambda k: -sums[k])[:TOP_N]
    return {
        "from": start.isoformat(), "to": day.isoformat(), "snapshots": weeks,
        "items": [{**info[k], "stars_gained": sums[k]} for k in top],
    }


def snapshot_path(day):
    return SNAPSHOTS / f"{day.isoformat()}.json"


def cmd_fetch(day):
    weekly = parse(get("https://github.com/trending?since=weekly"), "week")
    monthly = parse(get("https://github.com/trending?since=monthly"), "month")
    if not weekly or not monthly:
        sys.exit(f"Trending пустой (weekly={len(weekly)}, monthly={len(monthly)}): разметка GitHub поменялась?")
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = {"date": day.isoformat(), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "weekly": weekly, "monthly": monthly, "readmes": {}}
    snapshot_path(day).write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # README — для всех, кто попадает в любой из трёх топов (квартал считается с учётом нового среза)
    repos = [r["repo"] for r in weekly[:TOP_N] + monthly[:TOP_N] + quarter_top(day)["items"]]
    snap["readmes"] = {repo: readme(repo) for repo in dict.fromkeys(repos)}
    snapshot_path(day).write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ok: {snapshot_path(day).relative_to(ROOT)} — weekly={len(weekly)}, monthly={len(monthly)}, "
          f"readmes={sum(1 for v in snap['readmes'].values() if v)}/{len(snap['readmes'])}")


def cmd_show(day):
    path = snapshot_path(day)
    if not path.exists():
        sys.exit(f"нет среза {path.relative_to(ROOT)}: GitHub Action fetch-trending ещё не отработал за эту дату")
    snap = json.loads(path.read_text(encoding="utf-8"))
    quarter = quarter_top(day)
    readmes = {}
    for p in sorted(SNAPSHOTS.glob("*.json")):  # README из более ранних срезов — для квартальных старожилов
        readmes.update(json.loads(p.read_text(encoding="utf-8")).get("readmes", {}))
    tops = {"week": snap["weekly"][:TOP_N], "month": snap["monthly"][:TOP_N], "quarter": quarter}
    repos = [r["repo"] for r in tops["week"] + tops["month"] + quarter["items"]]
    print(json.dumps({"date": snap["date"], "fetched_at": snap["fetched_at"], **tops,
                      "readmes": {r: readmes.get(r, "") for r in dict.fromkeys(repos)}},
                     ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "show"):
        sys.exit("использование: fetch_trending.py fetch|show [YYYY-MM-DD]")
    day = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.now(timezone.utc).date()
    {"fetch": cmd_fetch, "show": cmd_show}[sys.argv[1]](day)


if __name__ == "__main__":
    main()
