"""Vizual tartib tekshiruvi: 1440/1024/390 kenglikda har bir sahifa gorizontal scroll'siz,
JS xatosiz ochiladi; screenshot'lar e2e/artifacts/ ichida ko'zdan kechirish uchun saqlanadi."""

import os

import pytest
from conftest import ARTIFACTS, BASE_URL, login
from playwright.sync_api import expect

PAGES = [
    ("/", "Umumiy ko'rinish"),
    ("/leads", "Mijozlar"),
    ("/conversations", None),
    ("/bookings", "Sinov darslari"),
    ("/courses", "Kurslar va guruhlar"),
    ("/knowledge", "Bilim bazasi"),
    ("/ai", "AI sozlamalari"),
    ("/analytics", "Analitika"),
    ("/team", "Jamoa"),
    ("/settings", "Integratsiyalar va sozlamalar"),
]


@pytest.mark.parametrize("width,height", [(1440, 900), (1024, 768), (390, 844)])
def test_pages_fit_viewport(new_page, width, height):
    page = new_page(width, height)
    login(page, "owner@demo.qabulflow.local")
    os.makedirs(ARTIFACTS, exist_ok=True)
    for path, heading in PAGES:
        page.goto(f"{BASE_URL}{path}")
        page.wait_for_load_state("networkidle")
        if heading:
            expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
        page.wait_for_timeout(300)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, f"{path} @ {width}px: gorizontal scroll {overflow}px"
        name = (path.strip("/") or "overview") + f"_{width}.png"
        page.screenshot(path=os.path.join(ARTIFACTS, name))
    assert not page.console_errors, page.console_errors


def test_webchat_mobile_fits(new_page):
    page = new_page(390, 780)
    page.goto(f"{BASE_URL}/chat/wk_demo_academy")
    expect(page.get_by_text("Demo maket")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1
    page.screenshot(path=os.path.join(ARTIFACTS, "webchat_390.png"))
