# Источники данных

| Источник | Статус | Заметки |
|---|---|---|
| visitpuumala.johku.com/en_US/majoitus | seed вручную, парсер готов | 57 карточек, из них 51 жильё |
| tervarumpu.fi/en_US/accommodation-in-repovesi-national-park | обход готов, 4/4 жильё | Johku на своём домене (Nuxt); хижины Repovesi без своего хозяина на карте — `merchant_name: Tervarumpu`. У 3 из 4 нет улицы в адресе, координаты — `overrides` в sources.yaml по POI из Nominatim (sammaltupa не нашлась, precision `area`) |
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
  POI `tourism=wilderness_hut` с точным совпадением по имени. **sammaltupa в Nominatim не нашлась** ни по одному
  варианту запроса (название, название + местность) — оставлена без override, точность `area` (центр Repovesi).
  Если у кого-то есть точные координаты — добавить в `sources.yaml: tervarumpu.overrides.sammaltupa`.
- Отдельная проблема, не в рамках этой задачи: `USER_AGENT` в `stays/johku.py` содержит плейсхолдер
  `CHANGE_ME@example.com`, и Nominatim блокирует такие запросы («Access denied»). Сейчас это не мешает —
  ни один объект Tervarumpu не долетает до `geo.lookup()` — но заблокирует геокодинг адресов с улицей
  у любой витрины при следующем полном прогоне. Нужен реальный контактный e-mail.
