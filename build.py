#!/usr/bin/env python3
"""Собирает сайт из data/issues/*.json.

index.html            — последний выпуск
issues/<date>/        — каждый выпуск отдельной страницей (архив)

Запуск: python3 build.py   (только стандартная библиотека)
Падает с ненулевым кодом, если данные выпуска не проходят проверку.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES = ROOT / "data" / "issues"
SITE_URL = "https://never-summer.github.io/github-trends-digest/"
METRIKA_ID = 113201778

PERIODS = [("week", "Неделя"), ("month", "Месяц"), ("quarter", "Квартал")]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]
REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")

e = html.escape


def ru_date(d):
    d = date.fromisoformat(d)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def rich(text):
    """Экранирует текст; `имя` превращается в плашку проекта."""
    return re.sub(r"`([^`]+)`", r'<span class="tag">\1</span>', e(text))


def validate(issue, path):
    errs = []
    def need(obj, key, where):
        if not isinstance(obj.get(key), str) or not obj[key].strip():
            errs.append(f"{where}: нет поля '{key}'")
    for k in ("date", "title", "lede", "skip"):
        need(issue, k, "выпуск")
    if issue.get("date") != path.stem:
        errs.append(f"date '{issue.get('date')}' не совпадает с именем файла '{path.stem}'")
    tops = issue.get("tops", {})
    for key, label in PERIODS:
        t = tops.get(key)
        if not t:
            errs.append(f"tops.{key}: нет топа '{label}'")
            continue
        need(t, "caption", f"tops.{key}")
        items = t.get("items", [])
        if not 1 <= len(items) <= 10:
            errs.append(f"tops.{key}: должно быть 1–10 репозиториев, сейчас {len(items)}")
        for i, it in enumerate(items, 1):
            where = f"tops.{key}[{i}]"
            if not REPO_RE.match(it.get("repo", "")):
                errs.append(f"{where}: repo должен быть вида owner/name, сейчас '{it.get('repo')}'")
            need(it, "description", where)
            need(it, "stars", where)
    for name in ("trends", "picks"):
        if not issue.get(name):
            errs.append(f"{name}: пусто")
        for i, t in enumerate(issue.get(name, []), 1):
            need(t, "title", f"{name}[{i}]")
            need(t, "body", f"{name}[{i}]")
    if errs:
        sys.exit(f"{path.name}:\n  " + "\n  ".join(errs))


def render_tops(tops):
    out = ['<div class="tops">']
    for i, (key, _) in enumerate(PERIODS):
        out.append(f'  <input type="radio" name="period" id="p-{key}"{" checked" if i == 0 else ""}>')
    out.append('  <div class="seg">')
    out += [f'    <label for="p-{key}">{label}</label>' for key, label in PERIODS]
    out.append('  </div>')
    for key, _ in PERIODS:
        t = tops[key]
        out.append(f'  <div class="panel" id="panel-{key}">')
        out.append(f'    <p class="caption">{e(t["caption"])}</p>')
        out.append('    <ol class="top">')
        for it in t["items"]:
            owner, name = it["repo"].split("/")
            cat = f' <span class="cat">{e(it["category"])}</span>' if it.get("category") else ""
            out.append(
                f'      <li><div class="repo"><a href="https://github.com/{e(it["repo"])}">'
                f'<span class="owner">{e(owner)}/</span>{e(name)}</a>{cat}'
                f'<p>{e(it["description"])}</p></div><span class="stars">{e(it["stars"])}</span></li>')
        out.append('    </ol>')
        out.append('  </div>')
    out.append('</div>')
    return "\n".join(out)


def render_page(issue, all_dates, prefix, is_latest):
    latest = all_dates[0]
    trends = "\n\n".join(
        f'<section class="trend">\n  <h3><span class="n">{i:02d}</span>{e(t["title"])}</h3>\n'
        f'  <p>{rich(t["body"])}</p>\n</section>'
        for i, t in enumerate(issue["trends"], 1))
    picks = "\n\n".join(
        f'<div class="pick{" radar" if p.get("radar") else ""}">\n  <strong>{e(p["title"])}</strong>\n'
        f'  <p>{rich(p["body"])}</p>\n</div>'
        for p in issue["picks"])
    def archive_item(d):
        if d == issue["date"]:
            link = f"<b>{ru_date(d)}</b>"
        else:
            href = prefix if d == latest else f"{prefix}issues/{d}/"
            link = f'<a href="{href}">{ru_date(d)}</a>'
        return f'  <li>{link}{" · свежий" if d == latest else ""}</li>'
    archive_items = "\n".join(archive_item(d) for d in all_dates)
    banner = "" if is_latest else (
        f'<p class="old-issue">Это архивный выпуск от {ru_date(issue["date"])}. '
        f'<a href="{prefix}">Свежий выпуск →</a></p>\n')
    canonical = SITE_URL if is_latest else f'{SITE_URL}issues/{issue["date"]}/'
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub Trends Digest</title>
<meta name="description" content="Куда движется AI-индустрия по трендингу GitHub: неделя, месяц, квартал. Выпуск {ru_date(issue["date"])}.">
<link rel="canonical" href="{canonical}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}style.css">
<!-- Yandex.Metrika counter -->
<script type="text/javascript">
    (function(m,e,t,r,i,k,a){{
        m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) {{if (document.scripts[j].src === r) {{ return; }}}}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    }})(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id={METRIKA_ID}', 'ym');

    ym({METRIKA_ID}, 'init', {{ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", referrer: document.referrer, url: location.href, accurateTrackBounce:true, trackLinks:true}});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/{METRIKA_ID}" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
</head>
<body>
<div class="wrap">

<header>
  <div class="eyebrow">
    <span>GitHub Trends · {ru_date(issue["date"])}</span>
    <button class="theme-btn" id="themeBtn" type="button" aria-label="Переключить тему">тема</button>
  </div>
  {banner}<h1>{e(issue["title"])}</h1>
  <p class="lede">{e(issue["lede"])}</p>
</header>

<main>

<h2>Топ по звёздам</h2>

{render_tops(issue["tops"])}

<h2>Главные сдвиги</h2>

{trends}

<h2>Что может пригодиться аналитической платформе</h2>

{picks}

<div class="skip">
  <b>Можно пропустить:</b> {rich(issue["skip"])}
</div>

<h2>Выпуски</h2>

<ul class="archive">
{archive_items}
</ul>

</main>

<footer>
  Источник: GitHub Trending и звёзды за неделю, месяц и квартал. Выходит еженедельно. Названия проектов даны как в трендинге; перед использованием проверяйте лицензию и активность репозитория.
</footer>

</div>
<script>
  (function () {{
    var root = document.documentElement, btn = document.getElementById('themeBtn');
    try {{ var saved = localStorage.getItem('theme'); if (saved) root.setAttribute('data-theme', saved); }} catch (e) {{}}
    btn.addEventListener('click', function () {{
      var dark = root.getAttribute('data-theme')
        ? root.getAttribute('data-theme') === 'dark'
        : window.matchMedia('(prefers-color-scheme: dark)').matches;
      var next = dark ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try {{ localStorage.setItem('theme', next); }} catch (e) {{}}
    }});
  }})();
</script>
</body>
</html>
"""


def main():
    paths = sorted(ISSUES.glob("*.json"), reverse=True)
    if not paths:
        sys.exit("нет ни одного выпуска в data/issues/")
    issues = []
    for p in paths:
        issue = json.loads(p.read_text(encoding="utf-8"))
        validate(issue, p)
        issues.append(issue)
    dates = [i["date"] for i in issues]
    (ROOT / "index.html").write_text(render_page(issues[0], dates, "", True), encoding="utf-8")
    for issue in issues:
        out = ROOT / "issues" / issue["date"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_page(issue, dates, "../../", False), encoding="utf-8")
    print(f"ok: {len(issues)} выпуск(ов), свежий — {dates[0]}")


if __name__ == "__main__":
    main()
