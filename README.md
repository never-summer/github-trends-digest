# GitHub Trends Digest

Еженедельный обзор самых звёздных репозиториев GitHub: топы за неделю, месяц и квартал и куда движется AI-индустрия.

**Страница:** https://never-summer.github.io/github-trends-digest/

## Как устроено

| файл | что делает |
|---|---|
| `data/issues/<дата>.json` | данные выпуска: топы, тренды, выводы |
| `data/snapshots/<дата>.json` | сырой срез GitHub Trending; из них считается квартальный топ |
| `fetch_trending.py` | `fetch` — снимает Trending и README проектов в срез (в GitHub Actions); `show` — печатает три топа из среза |
| `.github/workflows/fetch-trending.yml` | по понедельникам коммитит свежий срез и сразу запускает агента (routine) через API |
| `build.py` | проверяет JSON и собирает `index.html` (свежий выпуск) и `issues/<дата>/` (архив) |
| `style.css` | оформление |
| `WEEKLY.md` | инструкция для облачного агента, который раз в неделю готовит выпуск |

Собрать локально: `python3 build.py` (нужен только Python 3).
