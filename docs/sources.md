# Источники данных

| Источник | Статус | Заметки |
|---|---|---|
| visitpuumala.johku.com (en_US + fi_FI) | обход готов, геокодинг проверен | 60 жильё (было 51); 48 exact, 8 merchant, 4 area. **+9 объектов бэкфилла (issue #6, 2026-09-25)**: мерчанты Metsäsydän (5) и B&B Rönölä (4) существовали только на fi_FI — см. ниже |
| tervarumpu.fi (Repovesi + Verla) | обход готов, 20/20 жильё | Johku на своём домене (Nuxt); 4 хижины Repovesi без своего хозяина — `merchant_name: Tervarumpu`, координаты — `overrides` (3 сверены с OSM `tourism=wilderness_hut`, sammaltupa — из JSON-LD на странице продукта). **+16 объектов бэкфилла (issue #6, 2026-09-25)**: 5-я хижина Repovesi (`harjulanmokit-jakalatupa`) и весь раздел «Majoittuminen Verlassa» (14 домиков) существовали только на fi_FI, не были переведены на en_US — см. ниже |
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

## Tervarumpu: бэкфилл fi_FI-only объектов (2026-09-25, issue #6)

При поиске новых Johku-витрин для issue #6 выяснилось: часть разделов сайта существует только
на fi_FI и никогда не была переведена на en_US, поэтому обход (который до сих пор ходил только
по `/en_US/accommodation-in-repovesi-national-park`) их не видел:

- **5-я хижина Repovesi** — `harjulanmokit-jakalatupa` (Harjulan Mökit), есть только на
  `/fi_FI/majoittuminen-repovedella` (тот же раздел, что и остальные 4 хижины на английском —
  просто эта одна не переведена).
- **Целый раздел «Majoittuminen Verlassa»** — 14 домиков в усадьбе Verla (объект Всемирного
  наследия ЮНЕСКО, ~30 мин от Repovesi, отдельная локация), хозяин — Verlan Mökit / Repovalkea Oy.
  Раздела на en_US для Verla нет вообще, ни одной ссылки.

Для этого в `stays/johku.py` добавлен разбор финских меток (`LABELS_FI`, маркеры мерчанта
`Kauppias`/`Tiedustelut`) — метки те же самые, что и на en_US, просто на другом языке, страница
устроена идентично. Обход переведён с парсинга ссылок одной HTML-страницы на
`googlesitemap.xml` витрины — так все fi_FI-only разделы становятся видны обходу наравне с
en_US, без ручного угадывания nav-ссылок (`sources.yaml: tervarumpu.section_paths` — теперь
список из 3 URL: en_US Repovesi + fi_FI Repovesi + fi_FI Verla).

**Геокодинг**: у всех 14 домиков Verla есть честный адрес с улицей (`Verlantie NNN, 47850 Verla`
и т.п.) — 18/20 итоговых объектов (считая старые 4 Repovesi) получили `exact` с первого/второго
прогона (Nominatim иногда отдаёт `429` на этой сети — повторный прогон добирает недостающее из
кэша/повторных попыток, тот же паттерн, что и в issue #3). Добавлен `merchants.verla` — точка
центра усадьбы Verla (геокодирована по названию) как запасной якорь на случай сбоя geocode для
конкретного домика, а не area-точка Repovesi (другой нацпарк, соврать точку на карте нечестно).
Два исключения, оба честно не `exact`:
- `harjulanmokit-jakalatupa` — адрес `Ukkolammentie 151, 52920 Voikoski` Nominatim не находит
  (тот же паттерн: частные лесные дороги не всегда картографированы) — остаётся на area-точке
  Repovesi (Voikoski — часть того же нацпарка, географически честно).
- `verla-verlan-uittotupa` — адрес `Kartisapolku, 47850 Verla` без номера дома — остаётся на
  merchant-точке `verla`.

Имя хозяина `Harjulan Mökit` (для 5-й хижины Repovesi) не выделено отдельно в `merchants` —
без адреса-якоря отдельная запись не нужна, объект и так получает честную area-точку; хозяин
отображается общим `merchant_name: Tervarumpu`, как и остальные хижины парка (сознательное
упрощение, не искажение данных).

## Visit Puumala: бэкфилл fi_FI-only мерчантов (2026-09-25, issue #6)

Тот же паттерн, что и у Tervarumpu: `sources.yaml: visitpuumala.section_paths` дополнен
`https://visitpuumala.johku.com/fi_FI/majoitus` — раздел жилья тот же самый URL, что и
en_US (`/majoitus`), просто на другом языке, отдаёт совсем других мерчантов:

- **Metsäsydän** (5 домиков) — адрес без номера дома (`Junninmäentie, 52200 Puumala`),
  `has_street()` честно `False`, объекты на `merchant`-точке (геокодирована сама улица
  без номера — `merchants.metsasydan` в sources.yaml).
- **B&B Rönölä** (4 объекта, «Aamiaiskori» — не жильё, доп. услуга, сам отсеялся по меткам)
  — честный адрес с улицей и номером (`Matikkalantie 731, 58720 Kaartilankoski`), но
  Nominatim его не находит (тот же паттерн, что и у части домиков Puumala/Tervarumpu) —
  остаются на `area`.

**Дубликаты, которые НЕ добавлены** — та же карточка внутри уже существующих мерчантов
(okkola/pistohiekka/nestorinranta) на fi_FI иногда получает совсем другой slug (не
машинный перевод, а другое читаемое имя), из-за чего простой дедуп по slug их не ловит:
`okkola-kalliola` (= `okkola-https-www-okkolanlomamokit-com-en`, Kalliola — то же фото,
те же места), `pistohiekka-mokki-pistohiekka-resort` (= `...cottage-pistohiekka-resort`),
`nestorinranta-mari-aittahuone`/`ville-aittahuone` (= `nestorinranta-mari-ja-ville-aittahuone`
и `-2`). Все подтверждены по совпадению `image` (тот же файл на `cdn.johku.com`) — обход
теперь дедуплицирует по фото, когда slug не совпал (`stays/johku.py: dedup_by_image`),
оставляя версию с более точными координатами (у английских уже были ручные `overrides`).

Заодно на объекте `ronola-lammaspaimeneksi` нашлась метка `Rakentamisvuosi` (Construction
year) и заголовок `Välimatkat` (Distances), не встретившиеся раньше на выборке страниц —
без них значение `Location` "проглатывало" год постройки и список расстояний как свой
текст. Добавлены в `LABELS_FI`/`SECTION_HEADINGS_FI`.
