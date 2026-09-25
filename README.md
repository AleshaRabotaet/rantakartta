# Rantakartta

Карта жилья у небольших хозяев Финляндии с фильтрами. Бронирование на сайте хозяина.

```bash
pip install -r requirements.txt
python -m pytest -q
python -m stays.build --source visitpuumala --limit 5   # пробный прогон
python -m http.server -d web 8000                       # карта на http://localhost:8000
```

В `web/data.js` уже лежат 51 объект Puumala, собранные вручную, так что карта работает сразу.
Первый настоящий прогон парсера их перезапишет.

Подробности для разработки в `CLAUDE.md`, план и решения в `docs/`.
