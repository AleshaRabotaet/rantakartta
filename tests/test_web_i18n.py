"""Playwright-проверка мультиязычного интерфейса (issue #16).

Definition of Done по issue: в FI/SV/EN не остаётся русских строк, язык
переключается в шапке, определяется по navigator.language и синхронизирован
с URL (#lang=...) и localStorage.
"""
import re

import pytest

from conftest import open_map_page

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")


@pytest.mark.parametrize("lang", ["fi", "sv", "en"])
def test_no_cyrillic_in_ui(browser, static_server, lang):
    context, page = open_map_page(browser, static_server, f"index.html#lang={lang}")
    try:
        assert page.eval_on_selector("html", "el => el.lang") == lang
        body_text = page.inner_text("body")
        assert not CYRILLIC.search(body_text), f"кириллица найдена в UI при lang={lang}: {body_text!r}"

        # открываем попап первого объекта — локализация должна дойти и туда
        page.click(".item")
        page.wait_for_selector(".leaflet-popup", timeout=10000)
        popup_text = page.inner_text(".leaflet-popup-content")
        assert not CYRILLIC.search(popup_text), f"кириллица найдена в попапе при lang={lang}: {popup_text!r}"
    finally:
        context.close()


def test_language_switch_updates_dom_and_hash(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html#lang=en")
    try:
        page.click('#langs button[data-lang="sv"]')
        assert page.eval_on_selector("html", "el => el.lang") == "sv"
        assert page.eval_on_selector(
            '#langs button[data-lang="sv"]', "el => el.getAttribute('aria-pressed')"
        ) == "true"
        assert "lang=sv" in page.evaluate("() => location.hash")
    finally:
        context.close()


def test_language_persists_via_local_storage(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html#lang=en")
    try:
        page.click('#langs button[data-lang="fi"]')
        assert page.evaluate("() => localStorage.getItem('rantakartta:lang')") == "fi"
    finally:
        context.close()


def test_default_lang_falls_back_to_en_for_unsupported_locale(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html", locale="ru-RU")
    try:
        assert page.eval_on_selector("html", "el => el.lang") == "en"
    finally:
        context.close()


def test_default_lang_detected_from_navigator_language(browser, static_server):
    context, page = open_map_page(browser, static_server, "index.html", locale="fi-FI")
    try:
        assert page.eval_on_selector("html", "el => el.lang") == "fi"
    finally:
        context.close()
