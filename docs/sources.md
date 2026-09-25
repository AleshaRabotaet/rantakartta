# Источники данных

| Источник | Статус | Заметки |
|---|---|---|
| visitpuumala.johku.com/en_US/majoitus | seed вручную, парсер готов | 57 карточек, из них 51 жильё |
| tervarumpu.fi/en_US/accommodation-in-repovesi-national-park | обход готов, 4/4 жильё | Johku на своём домене (Nuxt); хижины Repovesi без своего хозяина на карте — `merchant_name: Tervarumpu`. У всех 4 нет улицы в адресе, координаты — `overrides` в sources.yaml: 3 сверены с точками OSM `tourism=wilderness_hut`, sammaltupa (в OSM не картографирована) — из structured data на странице продукта Johku (`latitude`/`longitude` в JSON-LD, публикует сам хозяин) |
| Другие Johku-витрины | TODO найти | искать по `johku.com/en_US` и `cdn.johku.com` |
| Visit Finland DataHub | TODO | бесплатный API, нужна регистрация публикатора; без цен и доступности |
| Johku REST API | ждём ответа | доступ только по запросу; маленькая компания (3 чел., оборот ~€0,4 млн) |

Контакт Johku: Ilkka Lariola, ilkka@johku.com (экосистема и новые клиенты).

## Tervarumpu: детали обхода (2026-09-25)

- Раздел отдаёт HTTP 103 Early Hints перед основным ответом — `requests`/stdlib `http.client` не пропускает
  1xx-ответы и получает пустое тело. Переключили сетевой слой `stays/johku.py` на `httpx`, который 1xx
  обрабатывает верно. Затрагивает все Johku-витрины (Puumala тоже отдаёт Early Hints), не только Tervarumpu.
- На страницах kuutinkamppa и pihkapirtti метка «Location» встречается дважды: как декоративный подзаголовок
  в начале текста и как настоящее поле в блоке General. `parse_properties()` брала первое совпадение и
  склеивала в адрес весь текст между ними. Поправили: метки распознаются только после первого заголовка
  раздела (General/Properties/...).
- Координаты трёх хижин без адреса с улицей (kuutinkamppa, pihkapirtti, savottakamppa) — из Nominatim,
  POI `tourism=wilderness_hut`; сверены напрямую с Overpass API (запрос по bbox вокруг Repovesi) — точки
  в OSM совпадают до 7-го знака. **sammaltupa в OSM не картографирована** — проверено и по имени, и полным
  перебором всех `tourism=wilderness_hut|hut|camp_site`, `building=hut|cabin`, `amenity=shelter` в парке —
  такого объекта там просто нет. Первая попытка (2026-09-25) — координаты по адресу Karhulahdentie, 47910
  Repovesi, введённые пользователем вручную (61°10'51.6"N 26°50'16.2"E) — оказались отклонены (не совпадают
  с реальным расположением на карте). Уточнили: страница продукта на tervarumpu.fi отдаёт в structured data
  (schema.org, JSON-LD) точные `latitude`/`longitude` для каждого объекта — это координаты, которые указывает
  сам хозяин через Johku, а не геокодинг адреса. Для sammaltupa: `61.1810749, 26.8378699` (в пределах 10 м от
  введённых пользователем вручную — те были в целом верны). Используем координаты из JSON-LD —
  `sources.yaml: tervarumpu.overrides.sammaltupa`, precision `exact`.
- **Идея на будущее** (не сделано в этом заходе): Johku явно отдаёт `latitude`/`longitude` в JSON-LD на
  каждой странице продукта — если это есть у всех витрин движка, можно вместо `overrides`/Nominatim
  доверять этим координатам напрямую в `johku.py::parse_product()` для объектов без адреса с улицей. Нужно
  сначала проверить на нескольких источниках, насколько эти координаты вообще точны (Sammaltupa совпала
  с независимой ручной оценкой в пределах 10 м — обнадёживает, но выборка = 1).
- Отдельная проблема, не в рамках этой задачи: `USER_AGENT` в `stays/johku.py` содержит плейсхолдер
  `CHANGE_ME@example.com`, и Nominatim блокирует такие запросы («Access denied»). Сейчас это не мешает —
  ни один объект Tervarumpu не долетает до `geo.lookup()` — но заблокирует геокодинг адресов с улицей
  у любой витрины при следующем полном прогоне. Нужен реальный контактный e-mail.
