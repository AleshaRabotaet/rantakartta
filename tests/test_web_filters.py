"""Playwright-проверка: ссылка с фильтрами в hash (issue #9) воспроизводит
вид карты — открытие URL с `#type=...&max=...` включает нужные фильтры, а
изменение фильтров в UI обновляет hash в адресной строке.
"""
import pytest

from conftest import open_map_page


def test_hash_max_price_and_exact_applied_on_load(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html#max=100&exact=1")
    try:
        assert page.eval_on_selector("#price", "el => el.value") == "100"
        assert page.inner_text("#priceOut") == "€100"
        assert page.eval_on_selector("#exact", "el => el.checked") is True

        prices = page.eval_on_selector_all(
            ".item .p", "els => els.map(el => el.textContent)"
        )
        for p in prices:
            digits = "".join(ch for ch in p if ch.isdigit())
            if not digits:  # цена неизвестна — фильтр по max её не трогает
                continue
            assert int(digits) <= 100, f"объект дороже 100 показан при max=100: {p}"
    finally:
        context.close()


def test_hash_type_filter_applied_on_load(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html#type=glamping")
    try:
        pressed = page.eval_on_selector_all(
            "#types .chip",
            "els => els.map(el => [el.textContent, el.getAttribute('aria-pressed')])",
        )
        matching = [state for label, state in pressed if "Глэмпинг" in label]
        if not matching:
            pytest.skip("в данных нет объектов типа glamping — чип не рендерится")
        assert "true" in matching
    finally:
        context.close()


def test_filter_change_updates_hash(browser, static_server):
    context, page = open_map_page(browser, static_server)
    try:
        chip = page.query_selector("#types .chip")
        if not chip:
            pytest.skip("нет чипов типов для клика")
        chip.click()
        hash_value = page.evaluate("() => location.hash")
        assert "type=" in hash_value
    finally:
        context.close()


def test_hash_id_selects_marker_and_opens_popup(browser, static_server):
    context, page = open_map_page(browser, static_server)
    try:
        marker_id = page.evaluate("() => markers.keys().next().value")
    finally:
        context.close()

    context, page = open_map_page(browser, static_server, f"index.html#id={marker_id}")
    try:
        active = page.eval_on_selector_all(
            ".item.active", "els => els.map(el => el.dataset.id)"
        )
        assert active == [marker_id]
        page.wait_for_selector(".leaflet-popup", timeout=10000)
    finally:
        context.close()
