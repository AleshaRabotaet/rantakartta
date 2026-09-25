"""Сборка данных: обход витрин -> геокодинг -> data/listings.json -> web/data.js.

    python -m stays.build                        # все витрины
    python -m stays.build --source visitpuumala  # одна витрина
    python -m stays.build --source visitpuumala --limit 5   # быстрый прогон для отладки
    python -m stays.build --export-only          # только пересобрать web/data.js
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import yaml

from . import johku
from .geocode import Geocoder, place, spread
from .models import Listing

LISTINGS = Path("data/listings.json")
WEB_DATA = Path("web/data.js")


def load_listings() -> list[Listing]:
    if not LISTINGS.exists():
        return []
    return [Listing(**d) for d in json.loads(LISTINGS.read_text())]


def save(items: list[Listing]) -> None:
    items.sort(key=lambda x: (x.source, x.merchant, x.title))
    data = [i.to_dict() for i in items]
    LISTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    export(data)


def export(data: list[dict]) -> None:
    payload = [d for d in data if d["lat"] is not None]
    WEB_DATA.write_text(
        "// Сгенерировано stays.build — не редактировать руками\n"
        f"window.LISTINGS = {json.dumps(payload, ensure_ascii=False)};\n"
        f"window.LISTINGS_UPDATED = {json.dumps(date.today().isoformat())};\n"
    )
    print(f"web/data.js: {len(payload)} объектов на карте, {len(data) - len(payload)} без координат")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--export-only", action="store_true")
    args = ap.parse_args()

    if args.export_only:
        export([i.to_dict() for i in load_listings()])
        return

    sources = yaml.safe_load(Path("sources.yaml").read_text())
    keys = [args.source] if args.source else list(sources)
    existing = [i for i in load_listings() if i.source not in keys]
    geo = Geocoder()
    fresh: list[Listing] = []
    try:
        for key in keys:
            cfg = sources[key]
            print(f"== {key}: {cfg['section_url']}")
            items = johku.crawl(key, cfg["section_url"], args.limit)
            names = {k: v["name"] for k, v in (cfg.get("merchants") or {}).items()}
            for it in items:
                it.merchant = names.get(it.id.split(":", 1)[1].split("-")[0], it.merchant)
                it.updated_at = date.today().isoformat()
                place(it, geo, cfg.get("merchants") or {}, cfg.get("area"))
            fresh += items
    finally:
        geo.save()
    spread(fresh)
    save(existing + fresh)


if __name__ == "__main__":
    main()
