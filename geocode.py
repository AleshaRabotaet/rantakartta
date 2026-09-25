"""Геокодинг: адрес -> координаты, с кэшем на диске и понятной точностью.

Порядок: улица с номером через Nominatim (exact) -> точка хозяина из sources.yaml (merchant)
-> центр муниципалитета из sources.yaml (area).
Nominatim: не больше 1 запроса в секунду и обязательный User-Agent.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import requests

from .johku import USER_AGENT, has_street
from .models import Listing

CACHE_PATH = Path("data/geocode_cache.json")
NOMINATIM = "https://nominatim.openstreetmap.org/search"


class Geocoder:
    def __init__(self, cache_path: Path = CACHE_PATH):
        self.cache_path = cache_path
        self.cache: dict[str, list[float] | None] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )

    def lookup(self, address: str) -> tuple[float, float] | None:
        if address in self.cache:
            hit = self.cache[address]
            return tuple(hit) if hit else None
        time.sleep(1.1)
        r = requests.get(
            NOMINATIM,
            params={"q": address, "countrycodes": "fi", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        res = r.json()
        point = [float(res[0]["lat"]), float(res[0]["lon"])] if res else None
        self.cache[address] = point
        return tuple(point) if point else None

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1))


def place(item: Listing, geo: Geocoder, merchants: dict, area: list[float] | None) -> None:
    if has_street(item.address):
        pt = geo.lookup(f"{item.address}, Finland")
        if pt:
            item.lat, item.lon, item.precision = pt[0], pt[1], "exact"
            return
    anchor = merchants.get(item.id.split(":", 1)[1].split("-")[0])
    if anchor:
        item.lat, item.lon, item.precision = anchor["lat"], anchor["lon"], "merchant"
    elif area:
        item.lat, item.lon, item.precision = area[0], area[1], "area"


def spread(items: list[Listing], radius_m: float = 180) -> None:
    """Разводит объекты с одинаковой точкой по маленькой спирали,
    чтобы на карте их можно было кликнуть по отдельности. Детерминированно по id."""
    groups: dict[tuple, list[Listing]] = {}
    for it in items:
        if it.lat is not None and it.precision != "exact":
            groups.setdefault((round(it.lat, 5), round(it.lon, 5)), []).append(it)
    for (lat, lon), group in groups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda x: hashlib.md5(x.id.encode()).hexdigest())
        for i, it in enumerate(group):
            r = radius_m * math.sqrt(i + 1) / math.sqrt(len(group))
            a = i * 2.39996  # золотой угол
            it.lat = lat + (r * math.cos(a)) / 111_320
            it.lon = lon + (r * math.sin(a)) / (111_320 * math.cos(math.radians(lat)))
