"""Brauzer E2E testlari (Python Playwright). Ishga tushgan va seed qilingan serverga qarshi ishlaydi:

E2E_BASE_URL=http://127.0.0.1:8000 pytest e2e -q
"""

import os

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PASSWORD = os.environ.get("E2E_DEMO_PASSWORD", "Demo12345!")
WIDGET_KEY = os.environ.get("E2E_WIDGET_KEY", "wk_demo_academy")
ARTIFACTS = os.path.join(os.path.dirname(__file__), "artifacts")


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _new_page(browser: Browser, width=1440, height=900) -> Page:
    ctx = browser.new_context(viewport={"width": width, "height": height}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    page = ctx.new_page()
    page.set_default_timeout(15000)
    page.console_errors = []  # type: ignore[attr-defined]
    page.on("pageerror", lambda e: page.console_errors.append(str(e)))  # type: ignore[attr-defined]
    return page


def login(page: Page, email: str):
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Parol").fill(PASSWORD)
    page.get_by_role("button", name="Kirish").click()
    page.wait_for_url(f"{BASE_URL}/")
    page.get_by_role("heading", name="Umumiy ko'rinish").wait_for()


@pytest.fixture
def owner_page(browser):
    page = _new_page(browser)
    login(page, "owner@demo.qabulflow.local")
    yield page
    os.makedirs(ARTIFACTS, exist_ok=True)
    page.context.close()


@pytest.fixture
def new_page(browser):
    pages = []

    def factory(width=1440, height=900):
        page = _new_page(browser, width, height)
        pages.append(page)
        return page

    yield factory
    for p in pages:
        p.context.close()
