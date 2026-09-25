"""Модель объекта размещения. Одна запись = один бронируемый продукт."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Типы жилья, которые понимает фронтенд (web/index.html -> TYPES).
TYPES = ("villa", "cottage", "room", "hut", "glamping", "camping")

# Насколько точна точка на карте.
#   exact    — геокодирован реальный адрес объекта
#   merchant — точка хозяина (ресепшен/база), объект где-то рядом
#   area     — центр деревни/района, точность в пределах километров
PRECISIONS = ("exact", "merchant", "area")


@dataclass
class Listing:
    id: str                      # "<source>:<slug>", стабильный между прогонами
    source: str                  # ключ витрины из sources.yaml
    merchant: str                # отображаемое имя хозяина
    title: str
    type: str                    # один из TYPES
    url: str                     # страница бронирования у хозяина
    price_from: float | None = None
    currency: str = "EUR"
    beds: int | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    precision: str = "area"
    image: str | None = None     # ссылка на превью у источника, файлы не копируем
    tags: list[str] = field(default_factory=list)  # sauna, shore_sauna, lake, pets, no_pets, car_needed
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
