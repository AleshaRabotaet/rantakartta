import re
from pathlib import Path

import requests

from stays import johku
from stays.geocode import Geocoder, place, spread
from stays.models import Listing

FIX = Path(__file__).parent / "fixtures"
SECTION = "https://visitpuumala.johku.com/en_US/majoitus"


def test_listing_page_finds_products_and_prices():
    cards = johku.parse_listing_page((FIX / "section.html").read_text(), SECTION)
    by_slug = {c["slug"]: c for c in cards}
    assert set(by_slug) == {"okkola-paulala", "nestorinranta-villa-hauki", "okkola-lahjakortti-okkolan-lomamokeille"}
    assert by_slug["okkola-paulala"]["price_from"] == 200.0
    assert by_slug["nestorinranta-villa-hauki"]["price_from"] == 187.0


def test_product_page_parsed_by_labels():
    html = (FIX / "product_latukka.html").read_text()
    item = johku.parse_product(html, SECTION + "/ukonhonka-latukka", "visitpuumala", "ukonhonka-latukka", 128.0)
    assert item.title == "Cottage: Latukka"
    assert item.merchant == "Ukonhonka Holiday Cottages"
    assert item.type == "cottage"
    assert item.beds == 4
    assert item.address == "Latukantie 118, 52200 Puumala"
    assert item.image.endswith("92.jpg")
    assert item.tags == ["car_needed", "lake", "no_pets", "sauna"]


def test_gift_cards_and_tours_skipped():
    html = "<html><body><h1>Gift card for Okkola holiday cottages 100 €</h1></body></html>"
    assert johku.parse_product(html, "u", "s", "okkola-lahjakortti", 100.0) is None


def test_classify():
    assert johku.classify("Villa", "Paulala") == "villa"
    assert johku.classify(None, 'B&B "Mari" for 2 people') == "room"
    assert johku.classify(None, "Tent place on the shore of Nestorinranta") == "camping"
    assert johku.classify(None, "Glamping-teltta Lake Saimaa") == "glamping"
    assert johku.classify(None, "Tiny Guest House") == "hut"
    assert johku.classify("Cabin", "Saarijärvi Forestry Hut") == "hut"
    assert johku.classify("Cottage", "Latukka") == "cottage"


def test_has_street():
    assert johku.has_street("Latukantie 118, 52200 Puumala")
    assert not johku.has_street("52200 Puumala")
    assert not johku.has_street(None)


def test_user_agent_has_real_contact():
    """Плейсхолдер CHANGE_ME@example.com отклоняется Nominatim ('Access denied') —
    geocode.py молча теряет exact-точность для всех адресов с улицей (см. docs/sources.md)."""
    assert "CHANGE_ME" not in johku.USER_AGENT
    assert "example.com" not in johku.USER_AGENT
    assert re.search(r"[\w.+-]+@[\w.-]+\.\w+", johku.USER_AGENT)


def test_parse_price_formats():
    assert johku.parse_price("1 250,00") == 1250.0
    assert johku.parse_price("26.00") == 26.0


def test_finnish_product_page_parsed_by_labels():
    """Часть Johku-витрин заводит объекты только на fi_FI и не переводит их (см.
    docs/decisions.md) — парсер должен понимать финские метки наравне с en_US."""
    html = (FIX / "product_verla_janis_fi.html").read_text()
    item = johku.parse_product(
        html,
        "https://tervarumpu.fi/fi_FI/majoittuminen-verlassa/verla-hirsniemen-janis",
        "tervarumpu", "verla-hirsniemen-janis", 79.0,
    )
    assert item.title == "Hirsniemen Jänis"
    assert item.merchant == "Verlan Mökit / Repovalkea Oy"
    assert item.type == "hut"
    assert item.beds == 2
    assert item.address == "Verlantie 287, 47850 Verla"
    assert johku.has_street(item.address)
    assert item.tags == ["car_needed", "lake", "pets", "sauna", "shore_sauna"]


def test_discover_product_urls_filters_by_prefix_and_depth():
    """Обход через googlesitemap.xml: берём только товарные страницы под известными
    префиксами (раздел жилья), не сам раздел и не посторонние страницы сайта."""
    xml = (FIX / "sitemap_sample.xml").read_text()
    urls = johku.discover_product_urls(
        xml,
        "https://tervarumpu.fi",
        ["/en_US/accommodation-in-repovesi-national-park", "/fi_FI/majoittuminen-verlassa"],
    )
    assert urls == [
        "https://tervarumpu.fi/en_US/accommodation-in-repovesi-national-park/kuutinkamppa",
        "https://tervarumpu.fi/en_US/accommodation-in-repovesi-national-park/sammaltupa",
        "https://tervarumpu.fi/fi_FI/majoittuminen-verlassa/verla-hirsniemen-janis",
        "https://tervarumpu.fi/fi_FI/majoittuminen-verlassa/verla-hirsniemen-mayra",
    ]


def test_dedup_by_slug_keeps_first_occurrence():
    urls = [
        "https://x.johku.com/en_US/majoitus/okkola-aapola",
        "https://x.johku.com/fi_FI/majoitus/okkola-aapola",
        "https://x.johku.com/fi_FI/majoitus/ronola-aitta",
    ]
    assert johku.dedup_by_slug(urls) == [
        "https://x.johku.com/en_US/majoitus/okkola-aapola",
        "https://x.johku.com/fi_FI/majoitus/ronola-aitta",
    ]


def test_dedup_by_image_keeps_first_occurrence():
    """Один и тот же товар на двух локалях иногда получает РАЗНЫЙ slug (перевод), но
    хозяин загружает одну и ту же фотографию для обеих версий — image остаётся
    стабильным идентификатором, когда slug совпасть уже не помог (issue #6, Kalliola/
    Pistohiekka/Nestorinranta в visitpuumala)."""
    a = Listing(id="s:okkola-https-www-okkolanlomamokit-com-en", source="s", merchant="m",
                title="Kalliola - hillside lake views", type="cottage", url="u",
                image="https://cdn.johku.com/okkola/largefiles/533.jpg")
    b = Listing(id="s:okkola-kalliola", source="s", merchant="m",
                title="Kalliola - mahtavat näkymät", type="cottage", url="u",
                image="https://cdn.johku.com/okkola/largefiles/533.jpg")
    c = Listing(id="s:okkola-paulala", source="s", merchant="m", title="Paulala",
                type="cottage", url="u", image="https://cdn.johku.com/okkola/largefiles/92.jpg")
    assert johku.dedup_by_image([a, b, c]) == [a, c]


def test_tervarumpu_product_parsed_with_cabin_type_and_no_street():
    html = (FIX / "product_tervarumpu_kuutinkamppa.html").read_text()
    item = johku.parse_product(
        html,
        "https://tervarumpu.fi/en_US/accommodation-in-repovesi-national-park/kuutinkamppa",
        "tervarumpu", "kuutinkamppa", 98.0,
    )
    assert item.merchant == "kuutinkamppa"
    assert item.type == "hut"
    assert item.beds == 6
    assert not johku.has_street(item.address)


def test_place_override_wins_and_is_exact():
    item = Listing(id="tervarumpu:kuutinkamppa", source="tervarumpu", merchant="m",
                    title="Kuutinkämppä", type="hut", url="u", address="52920 Voikoski")
    place(item, geo=None, merchants={}, area=[61.19, 26.88],
          overrides={"kuutinkamppa": {"lat": 61.1786093, "lon": 26.8470936}})
    assert (item.lat, item.lon) == (61.1786093, 26.8470936)
    assert item.precision == "exact"


def test_geocode_lookup_survives_network_error(monkeypatch, tmp_path):
    """Nominatim недоступен/блокирует (403 и т.п.) -> lookup возвращает None,
    а не роняет всю сборку исключением. Ошибка не кэшируется."""
    def boom(*a, **k):
        raise requests.HTTPError("403 Client Error: Forbidden")

    monkeypatch.setattr("stays.geocode.requests.get", boom)
    monkeypatch.setattr("stays.geocode.time.sleep", lambda *_: None)
    geo = Geocoder(cache_path=tmp_path / "cache.json")
    assert geo.lookup("Lintusalontie 1661, 52200 Puumala, Finland") is None
    assert geo.cache == {}


def test_spread_separates_same_point():
    items = [Listing(id=f"s:okkola-{i}", source="s", merchant="m", title=str(i), type="villa", url="u",
                     lat=61.45, lon=28.15, precision="merchant") for i in range(17)]
    spread(items)
    assert len({(round(i.lat, 6), round(i.lon, 6)) for i in items}) == 17
    assert all(abs(i.lat - 61.45) < 0.003 for i in items)
