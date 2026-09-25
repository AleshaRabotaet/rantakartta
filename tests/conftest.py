"""Общие Playwright-фикстуры для тестов карты (web/index.html)."""
import functools
import http.server
import re
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"
CACHE_DIR = REPO_ROOT / "tests" / ".cache" / "vendor"

# Библиотеки грузим из локального кэша вместо cdnjs: страница ссылается на
# те же URL, что и в проде, но реальная сеть в песочнице/CI нестабильна,
# а тест должен быть детерминированным.
VENDOR_ASSETS = {
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js":
        ("leaflet.min.js", "application/javascript"),
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css":
        ("leaflet.min.css", "text/css"),
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.min.js":
        ("leaflet.markercluster.min.js", "application/javascript"),
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.min.css":
        ("MarkerCluster.min.css", "text/css"),
}
SKIP_HOSTS = re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|tile\.openstreetmap\.org)/")

# В headless Chromium CSS-переход зумовой анимации Leaflet иногда не
# добивает transitionend, из-за чего map._animatingZoom навсегда
# остаётся true и все дальнейшие setZoom() молча игнорируются. Отключаем
# анимацию зума только для теста — это не влияет на логику, которую мы
# проверяем.
DISABLE_ZOOM_ANIMATION = b"\nL.Map.mergeOptions({zoomAnimation:false, markerZoomAnimation:false, fadeAnimation:false});\n"


def _cached_asset(url, filename):
    import requests

    path = CACHE_DIR / filename
    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


@pytest.fixture(scope="module")
def static_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    playwright_sync_api = pytest.importorskip("playwright.sync_api")
    with playwright_sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # браузер playwright не установлен
            pytest.skip(f"chromium недоступен: {exc}")
        yield b
        b.close()


def open_map_page(browser, port, path="index.html"):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    def serve_vendor(route):
        filename, content_type = VENDOR_ASSETS[route.request.url]
        vendor_path = _cached_asset(route.request.url, filename)
        body = vendor_path.read_bytes()
        if filename == "leaflet.min.js":
            body += DISABLE_ZOOM_ANIMATION
        route.fulfill(status=200, content_type=content_type, body=body)

    for url in VENDOR_ASSETS:
        page.route(url, serve_vendor)
    page.route(SKIP_HOSTS, lambda r: r.abort())

    page.goto(f"http://127.0.0.1:{port}/{path}", wait_until="load", timeout=30000)
    page.wait_for_selector(".list li", timeout=15000)  # .item — есть результаты, .empty — фильтры их обнулили
    return context, page
