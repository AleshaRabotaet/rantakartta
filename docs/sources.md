# Источники данных

| Источник | Статус | Заметки |
|---|---|---|
| visitpuumala.johku.com/en_US/majoitus | обход готов, геокодинг проверен | 57 карточек, 51 жильё; 48/51 precision exact, 3 — merchant (см. ниже) |
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
  **Решено (2026-09-25, issue #3)**: заменён на `bet4lulz@pm.me`, см. раздел Visit Puumala ниже — баг
  оказался общим для всех витрин, не только Tervarumpu.

## Visit Puumala: детали обхода (2026-09-25, issue #3)

Первый полный прогон `visitpuumala` с рабочими координатами. Отправная точка — все 51 объект висели
на precision `merchant`/`area` (47/4), хотя у 34 из 51 есть честный адрес с улицей и номером дома
(`has_street() == True`). Причина — тот же баг, что и у Tervarumpu (см. выше): плейсхолдер
`CHANGE_ME@example.com` в `USER_AGENT` отклонялся Nominatim, а `geocode.py` не кэширует и не роняет
сборку на сетевых ошибках, так что баг был незаметен во всех прогонах, на любой витрине.

**Шаг 1 — починили `USER_AGENT`** (`bet4lulz@pm.me`). Пересобрали `visitpuumala`: из 34 объектов с
улицей в адресе (16 уникальных адресных строк — `Geocoder` кэширует по адресу) получили geocode exact
для большинства; несколько адресов ловили `429 Too many requests` от Nominatim (нестабильно, похоже на
особенность исходящей сети этого окружения — сессии делят один IP; полученный `429` — не наша частота
запросов, `REQUEST_DELAY_S`/`time.sleep(1.1)` соблюдаются). Дожали оставшиеся точечным ретраем с более
длинным бэкоффом (5–10 с). Итог по адресным геокодингам: 25/34 объектов (16 уникальных адресов) —
`exact`; 2 адреса Nominatim честно не нашёл (`Mannilanniementie 169/193, 52270 Ryhälä` — 7 объектов
Mannilanniemi; `Pistohiekanraitti 33, 52200 Pistohiekanraitti 33` — сбой парсинга адреса, город задвоился
в поле улицы, вне рамок этой задачи); ещё 17 объектов вообще не имеют улицы в адресе (все — домики
Okkolan Lomamökit, только `"52200 Puumala"`).

**Шаг 2 — OSM-поиск POI для 26 оставшихся объектов** (17 Okkola + 7 Mannilanniemi + Pistohiekka +
`ukonhonka-jarvela`, у которого Nominatim не нашёл `Jänniementie 40, 52230 Hurissalo`). Искали каждое
имя домика через Nominatim (`viewbox`/`bounded` вокруг точки хозяина) — **ни одно из 24 имён не нашлось**
(Aapola, Hessula, Kalliola, Kotkala, Lahtela, Luotola, Mäntylä, Niemelä, Paulala, Rantala, Riihelä,
Salmela, Sivula, Syrjälä, Taijala, Tiirala, Tupula, Kurki, Myyrä, Mäyrä, Norppa, Koskelo, Metso,
Villa Mannilanniemi, Järvelä — 0 результатов). «Pistohiekka» нашёлся, но как общие POI пляжа/кемпинга
(`beach`, `caravan_site`, `camp_site`), не как конкретный домик. Вывод: частные домики на OSM в
Puumala не картографированы (тот же паттерн, что и с `sammaltupa` у Tervarumpu) — честно, не форсируем.

Задуманную сверку через Overpass API сделать не удалось: `overpass-api.de` (и альтернативный
`overpass.kumi.systems`) заблокированы сетевой политикой этого окружения — доступен только
`nominatim.openstreetmap.org`. Если понадобится Overpass, нужно добавить хост в allowed domains
окружения.

**Шаг 3 — JSON-LD вместо OSM.** По итогам Tervarumpu оставалась открытая идея: Johku отдаёт
`latitude`/`longitude` в structured data (schema.org) прямо на странице продукта. Проверили на
`ukonhonka-latukka` (Latukantie 118, 52200 Puumala) — у него есть И честный geocode по адресу
(`61.5940579, 28.3815492`), И JSON-LD (`61.5940125, 28.3815703`) — совпадение **в пределах ~5 м**.
Это независимое подтверждение (выборка теперь n=2 вместе с sammaltupa, ~10 м) — доверяем JSON-LD.

Забрали JSON-LD со всех 26 оставшихся страниц продуктов — **у всех 26 есть `latitude`/`longitude`**.
23 из них — уникальные точки, отличные от точки хозяина и правдоподобные (в пределах 1–3 км от анchor,
что нормально для хозяина с несколькими отдельно стоящими домиками) — записаны в
`sources.yaml: visitpuumala.overrides`, precision `exact`. **3 объекта Mannilanniemi (Myyrä, Mäyrä,
Metso) отдают одну и ту же точку на троих** (`61.6676038, 28.2550466`, до 12-го знака) — это явно не
индивидуальная точка каждого домика, а общая/дефолтная точка хозяина в JSON-LD. Override для них не
добавлен, честно оставлены на precision `merchant` (точка `mannilanniemi` в sources.yaml).

**Итог**: 48/51 объектов Puumala — precision `exact` (было 0), 3 — `merchant`. Полностью закрывает
issue #3 в части «найти координаты домиков»: способ оказался не OSM (домики там не картографированы),
а JSON-LD с самой страницы Johku — тот же источник, что уже использовался для `sammaltupa`, теперь
проверенный на независимом geocode-сравнении и применённый системно.
