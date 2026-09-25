# Схема объекта (`stays/models.py: Listing`)

| Поле | Тип | Откуда |
|---|---|---|
| id | `"<source>:<slug>"` | URL продукта |
| source | str | ключ в sources.yaml |
| merchant | str | sources.yaml или блок Merchant на странице |
| title | str | `<h1>` страницы |
| type | villa / cottage / room / hut / glamping / camping | `classify()` по «Holiday apartment type» и названию |
| url | str | ссылка на бронирование у хозяина |
| price_from | float? | «From €X» на карточке раздела |
| beds | int? | «Number of beds» |
| address | str? | последняя строка «Location» |
| lat, lon, precision | exact / merchant / area | `geocode.place()` |
| image | str? | og:image (ссылка, не копия) |
| tags | sauna, shore_sauna, lake, pets, no_pets, car_needed | Facilities, Shore, Restrictions, Accessibility |
| updated_at | ISO-дата | время сборки |
