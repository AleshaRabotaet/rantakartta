"""Playwright-проверка: после отдаления карты не должно оставаться
«осиротевших» иконок-ценников (.pill-icon) без реального маркера на карте.

Баг: popupclose дёргал marker.setIcon() во время removeLayer() у
markercluster, когда marker._map ещё не обнулён (событие remove у
Leaflet срабатывает до этого), и setIcon вызывал _initIcon(), который
добавлял в markerPane новую иконку — убрать её было уже некому.

Сценарий: кликаем по объекту в списке, дожидаемся попапа, отдаляем
карту зум за зумом до 4 (как это делает пользователь колесом мыши) и
сравниваем число .pill-icon в DOM с числом реально видимых отдельных
маркеров на карте.
"""
import functools
import http.server
import re
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

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
# анимацию зума только для теста — это не влияет на логику удаления
# маркеров, которую мы проверяем.
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
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # браузер playwright не установлен
            pytest.skip(f"chromium недоступен: {exc}")
        yield b
        b.close()


def _open_map_page(browser, port):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    def serve_vendor(route):
        filename, content_type = VENDOR_ASSETS[route.request.url]
        path = _cached_asset(route.request.url, filename)
        body = path.read_bytes()
        if filename == "leaflet.min.js":
            body += DISABLE_ZOOM_ANIMATION
        route.fulfill(status=200, content_type=content_type, body=body)

    for url in VENDOR_ASSETS:
        page.route(url, serve_vendor)
    page.route(SKIP_HOSTS, lambda r: r.abort())

    page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=30000)
    page.wait_for_selector(".item", timeout=15000)
    return context, page


def _zoom_to(page, zoom):
    page.evaluate(
        """(z) => new Promise(resolve => {
            if (map.getZoom() === z) return resolve();
            map.once('zoomend', () => setTimeout(resolve, 60));
            map.setZoom(z, { animate: false });
        })""",
        zoom,
    )


def _find_marker_that_gets_clustered(page):
    """Отдаляем карту зум за зумом и берём первый маркер, ушедший в кластер."""
    start = page.evaluate("() => map.getZoom()")
    for z in range(start, 3, -1):
        _zoom_to(page, z)
    return page.evaluate(
        """() => {
            for (const [id, m] of markers) if (!m._map) return id;
            return null;
        }"""
    )


def _isolate_marker(page, marker_id):
    """Приближаем карту к маркеру, пока он не станет отдельной (некластерной) иконкой."""
    for z in (16, 17, 18, 19):
        page.evaluate(
            """([id, z]) => new Promise(resolve => {
                const m = markers.get(id);
                map.once('zoomend', () => setTimeout(resolve, 60));
                map.setView(m.getLatLng(), z, { animate: false });
            })""",
            [marker_id, z],
        )
        if page.evaluate("(id) => !!markers.get(id)._icon", marker_id):
            return True
    return False


def test_no_orphan_pill_after_zooming_out(browser, static_server):
    context, page = _open_map_page(browser, static_server)
    try:
        candidate = _find_marker_that_gets_clustered(page)
        if not candidate:
            pytest.skip("в данных нет объектов, которые группируются в кластер при отдалении")
        if not _isolate_marker(page, candidate):
            pytest.skip("не удалось показать выбранный объект отдельным маркером")

        page.click(f'.item[data-id="{candidate}"]')
        page.wait_for_selector(".leaflet-popup", timeout=10000)

        # Отдаляем карту до зума 4 шаг за шагом — так же, как это делает
        # колесо мыши пользователя. Активный маркер по пути уходит в
        # кластер, что и вызывает popupclose на ещё не до конца удалённом слое.
        start = page.evaluate("() => map.getZoom()")
        for z in range(start - 1, 3, -1):
            _zoom_to(page, z)

        pill_count = page.eval_on_selector_all(".pill-icon", "els => els.length")
        visible_individual = page.evaluate(
            "() => [...markers.values()].filter(m => m._map).length"
        )

        assert pill_count == visible_individual, (
            f"в DOM {pill_count} .pill-icon, а реальных отдельных маркеров на карте "
            f"{visible_individual} — есть осиротевшие иконки"
        )
    finally:
        context.close()
