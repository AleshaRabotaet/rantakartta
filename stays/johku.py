"""Парсер витрин на движке Johku.

Разбор идёт по текстовым меткам страницы (англ. локаль en_US), а не по CSS-классам:
метки вроде "Holiday apartment type" одинаковы у всех витрин и переживают смену вёрстки.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from .models import Listing

USER_AGENT = "SuomiStaysBot/0.1 (pet project; contact: bet4lulz@pm.me)"
REQUEST_DELAY_S = 2.0  # вежливая пауза между запросами

PRICE_RE = re.compile(r"€\s*([\d][\d\s]*(?:[.,]\d{1,2})?)")
# Финская локаль ставит € после суммы: "Alkaen 79,00 € / vrk".
PRICE_RE_FI = re.compile(r"([\d][\d\s]*[.,]\d{2})\s*€")

# Метки блока свойств на странице объекта (en_US).
LABELS = [
    "Location", "Holiday apartment type", "Living area", "Number of beds", "Extra beds",
    "Construction year", "Renovation year", "Website", "Facilities", "Feature description",
    "Entertainment", "Kitchen equipment", "Number of kitchen sets", "Kitchen description",
    "Garden equipment", "Yard description", "Shore", "Shore description", "Parking",
    "Accessibility", "Activities", "Activities description", "Restrictions", "Services",
    "Traffic connections", "Driving instructions",
]
SECTION_HEADINGS = {"General", "Properties", "Connections and services", "Distances", "Enquiries", "Images"}

# Часть Johku-витрин заводит объекты только на fi_FI и не переводит их (issue #6,
# docs/decisions.md) — метки одинаковы у всех витрин движка, но зависят от локали.
# Найдены на реальных страницах; "Connections and services"/"Distances" и часть
# LABELS пока не встретились на fi_FI — дописать по факту находки (сначала фикстура).
LABELS_FI = {
    "Sijainti": "Location",
    "Lomakohteen tyyppi": "Holiday apartment type",
    "Asuinpinta-ala": "Living area",
    "Vuoteiden määrä": "Number of beds",
    "Lisävuoteet": "Extra beds",
    "Remontointivuosi": "Renovation year",
    "Verkkosivusto": "Website",
    "Varustelu": "Facilities",
    "Varustelun kuvaus": "Feature description",
    "Keittiövälineet": "Kitchen equipment",
    "Astiastot": "Number of kitchen sets",
    "Keittiön kuvaus": "Kitchen description",
    "Pihan varusteet": "Garden equipment",
    "Pihan kuvaus": "Yard description",
    "Ranta": "Shore",
    "Rannan kuvaus": "Shore description",
    "Pysäköinti": "Parking",
    "Saavutettavuus": "Accessibility",
    "Aktiviteetit": "Activities",
    "Aktiviteettien kuvaus": "Activities description",
    "Rajoitukset": "Restrictions",
}
SECTION_HEADINGS_FI = {"Perustiedot", "Ominaisuudet", "Tiedustelut", "Kuvat"}
ALL_SECTION_HEADINGS = SECTION_HEADINGS | SECTION_HEADINGS_FI
# Метка -> канонический английский ключ, включая en_US (сама на себя).
LABEL_ALIASES = {label: label for label in LABELS} | LABELS_FI

# Всё, что продаётся в разделе жилья, но жильём не является.
EXCLUDE_TITLE_RE = re.compile(
    r"gift card|lahjakortti|paddling tour|canoeing tour|route|melontareitti", re.I
)


# ---------- сеть ----------

def _session() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def fetch(session: httpx.Client, url: str) -> str:
    # requests/stdlib http.client stops at HTTP 103 Early Hints (Johku's Nuxt
    # backend sends it) and returns an empty body; httpx handles 1xx correctly.
    time.sleep(REQUEST_DELAY_S)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text


# ---------- разбор страницы списка ----------

def parse_listing_page(html: str, page_url: str) -> list[dict]:
    """Карточки из раздела: ссылка на продукт + цена «от»."""
    soup = BeautifulSoup(html, "html.parser")
    base = urlparse(page_url)
    section_path = base.path.rstrip("/") + "/"
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"]).split("#")[0].split("?")[0]
        p = urlparse(url)
        if p.netloc != base.netloc or not p.path.startswith(section_path):
            continue
        slug = p.path[len(section_path):].strip("/")
        if not slug or "/" in slug:
            continue
        text = a.get_text(" ", strip=True)
        m = PRICE_RE.search(text)
        entry = seen.setdefault(url, {"url": url, "slug": slug, "price_from": None})
        if m and entry["price_from"] is None:
            entry["price_from"] = parse_price(m.group(1))
    return list(seen.values())


def parse_price(raw: str) -> float | None:
    s = raw.replace(" ", "").replace("\u00a0", "")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ---------- разбор страницы объекта ----------

def html_to_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]


def parse_properties(lines: list[str]) -> dict[str, str]:
    """Собирает значения по меткам: всё между меткой и следующей меткой/разделом.

    Метки распознаются только после первого заголовка раздела (General, Properties, ...) —
    иначе одноимённый декоративный подзаголовок в тексте описания (например, "Location"
    перед вступительным абзацем) перехватывает значение у настоящего поля."""
    props: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    in_section = False

    def flush():
        if current and current not in props:
            props[current] = "\n".join(buf).strip()

    for ln in lines:
        heading = ln.lstrip("#").strip()
        if heading in ALL_SECTION_HEADINGS:
            flush()
            current, buf = None, []
            in_section = True
        elif in_section and ln in LABEL_ALIASES:
            flush()
            current, buf = LABEL_ALIASES[ln], []
        elif current:
            buf.append(ln)
    flush()
    return props


def parse_meta(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")

    def meta(prop: str) -> str | None:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return tag.get("content") if tag else None

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (meta("og:title") or "")
    title = re.sub(r"\s+-\s+[^-]+$", "", title) if not h1 else title
    return {"title": title, "image": meta("og:image")}


def parse_merchant(lines: list[str]) -> str | None:
    """Имя хозяина — первая строка после заголовка Merchant/Enquiries (Kauppias/Tiedustelut)."""
    for marker in ("Merchant", "Enquiries", "Kauppias", "Tiedustelut"):
        for i, ln in enumerate(lines):
            if ln.lstrip("#").strip() == marker and i + 1 < len(lines):
                return re.split(r"[<\s]*[\w.+-]+@", lines[i + 1])[0].strip() or None
    return None


def classify(apartment_type: str | None, title: str) -> str:
    if apartment_type == "Cabin":
        return "hut"
    t = f"{apartment_type or ''} {title}".lower()
    if re.search(r"tent place|hammock|caravan|boat place|telttapaikka|venepaikka", t):
        return "camping"
    if re.search(r"glamping|tentsile|teltta", t):
        return "glamping"
    if re.search(r"b&b|\broom\b|huone|aitta", t):
        return "room"
    if re.search(r"tupa|torppa|tiny|kämppä|hut", t):
        return "hut"
    if re.search(r"villa|house", t):
        return "villa"
    return "cottage"


def extract_tags(props: dict[str, str]) -> list[str]:
    tags: set[str] = set()
    fac = props.get("Facilities", "").lower()
    if "sauna" in fac:
        tags.add("sauna")
    if "sauna on shore" in fac or "rantasauna" in fac:
        tags.add("shore_sauna")
    shore = props.get("Shore", "").lower()
    if shore in ("lake", "sea", "river", "järvi") or "lake" in shore:
        tags.add("lake")
    restr = props.get("Restrictions", "").lower()
    if "pets allowed" in restr or "lemmikit sallittu" in restr:
        tags.add("pets")
    elif "pets not allowed" in restr:
        tags.add("no_pets")
    access = props.get("Accessibility", "").lower()
    if "car necessary" in access or "auto tarvitaan" in access:
        tags.add("car_needed")
    return sorted(tags)


def parse_address(location: str | None) -> str | None:
    """'Puumala\\nLatukantie 118, 52200 Puumala' -> 'Latukantie 118, 52200 Puumala'."""
    if not location:
        return None
    lines = [ln for ln in location.splitlines() if ln.strip()]
    return lines[-1].strip() if lines else None


def has_street(address: str | None) -> bool:
    """Есть ли в адресе улица с номером, а не только индекс + город."""
    if not address:
        return False
    street = address.split(",")[0]
    return bool(re.search(r"[A-Za-zÄÖÅäöå]{3,}\s+\d", street))


def find_price(lines: list[str]) -> float | None:
    """Цена «от» видна и текстом на самой странице товара ('From €128.00 / d',
    'Alkaen 79,00 € / vrk') — используется, когда цену не удалось взять с карточки
    раздела (обход через sitemap не даёт текста карточки)."""
    text = "\n".join(lines)
    m = PRICE_RE.search(text) or PRICE_RE_FI.search(text)
    return parse_price(m.group(1)) if m else None


def parse_product(html: str, url: str, source: str, slug: str, price_from: float | None = None) -> Listing | None:
    lines = html_to_lines(html)
    props = parse_properties(lines)
    meta = parse_meta(html)
    title = meta["title"] or slug
    if EXCLUDE_TITLE_RE.search(title):
        return None
    if not any(k in props for k in ("Holiday apartment type", "Number of beds", "Location")):
        return None  # не жильё (тур, товар и т.п.)
    beds = props.get("Number of beds")
    return Listing(
        id=f"{source}:{slug}",
        source=source,
        merchant=parse_merchant(lines) or slug.split("-")[0],
        title=title,
        type=classify(props.get("Holiday apartment type"), title),
        url=url,
        price_from=price_from if price_from is not None else find_price(lines),
        beds=int(beds) if beds and beds.isdigit() else None,
        address=parse_address(props.get("Location")),
        image=meta["image"],
        tags=extract_tags(props),
    )


# ---------- обход витрины ----------

def discover_product_urls(sitemap_xml: str, base_url: str, prefixes: list[str]) -> list[str]:
    """Товарные URL из googlesitemap.xml под известными префиксами раздела жилья.

    Товарная страница — префикс плюс ровно один дополнительный сегмент пути
    (не сам раздел, не вложенные подстраницы)."""
    root = ElementTree.fromstring(sitemap_xml)
    host = urlparse(base_url).netloc
    prefixes = [p.rstrip("/") for p in prefixes]
    found: set[str] = set()
    # Namespace у sitemap.xml плавает между http:// и https:// в зависимости от витрины —
    # матчим тег <loc> по локальному имени, без завязки на конкретный URI.
    for loc in root.iter():
        if not loc.tag.rpartition("}")[2] == "loc":
            continue
        url = (loc.text or "").strip()
        parsed = urlparse(url)
        if parsed.netloc != host:
            continue
        path = parsed.path.rstrip("/")
        for prefix in prefixes:
            if path.startswith(prefix + "/") and "/" not in path[len(prefix) + 1:]:
                found.add(url)
    return sorted(found)


def dedup_by_slug(urls: list[str]) -> list[str]:
    """Одна и та же карточка на двух локалях обычно имеет одинаковый slug (последний
    сегмент пути) — оставляем первое вхождение, остальные считаем тем же объектом."""
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)
        out.append(url)
    return out


def crawl(source_key: str, section_paths: str | list[str], limit: int | None = None) -> list[Listing]:
    if isinstance(section_paths, str):
        section_paths = [section_paths]
    s = _session()
    first = urlparse(section_paths[0])
    domain = f"{first.scheme}://{first.netloc}"
    prefixes = [urlparse(p).path for p in section_paths]

    urls: list[str] = []
    try:
        sitemap_xml = fetch(s, domain + "/googlesitemap.xml")
        urls = discover_product_urls(sitemap_xml, domain, prefixes)
    except (httpx.HTTPError, ElementTree.ParseError) as e:
        print(f"  ! sitemap {domain}: {e}")

    if not urls:
        # Витрина без sitemap (не должно случаться у Johku, но дёшево подстраховаться) —
        # старый способ: ссылки с самой страницы раздела.
        cards: list[dict] = []
        for section_url in section_paths:
            cards += parse_listing_page(fetch(s, section_url), section_url)
        urls = [c["url"] for c in cards]

    urls = dedup_by_slug(urls)
    if limit:
        urls = urls[:limit]

    out: list[Listing] = []
    for url in urls:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        try:
            html = fetch(s, url)
        except httpx.HTTPError as e:
            print(f"  ! {url}: {e}")
            continue
        item = parse_product(html, url, source_key, slug)
        print(f"  {'+' if item else '-'} {slug}")
        if item:
            out.append(item)
    return out
