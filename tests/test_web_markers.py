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
import pytest

from conftest import open_map_page


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
    context, page = open_map_page(browser, static_server)
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
