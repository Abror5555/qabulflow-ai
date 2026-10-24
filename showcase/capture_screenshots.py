"""Ishlayotgan ilovadan (sintetik demo ma'lumotlar bilan) asl ekran tasvirlarini oladi.

    python showcase/capture_screenshots.py --base-url http://127.0.0.1:8000

Natija: assets/screenshots/*.png (2x zichlik) va telegram_demo_conversation.json
(Telegram uslubidagi maket uchun HAQIQIY demo oqim xabarlari).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "screenshots"
PASSWORD = "Demo12345!"


def login(page: Page, base: str, email: str = "owner@demo.qabulflow.local") -> None:
    page.goto(f"{base}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Parol").fill(PASSWORD)
    page.get_by_role("button", name="Kirish").click()
    page.wait_for_url(f"{base}/")
    page.get_by_role("heading", name="Umumiy ko'rinish").wait_for()
    # Mavzuni yorug' holatga keltirish (server tomonida saqlanadi)
    page.evaluate(
        """() => fetch('/api/auth/me/', {method: 'PATCH', headers: {'Content-Type': 'application/json',
        'X-CSRFToken': document.cookie.split('csrftoken=')[1].split(';')[0]}, body: JSON.stringify({preferences: {theme: 'light'}})})"""
    )
    page.evaluate("localStorage.setItem('qf-theme', 'light')")
    page.reload()
    page.get_by_role("heading", name="Umumiy ko'rinish").wait_for()


def settle(page: Page, ms: int = 900) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)
    # Avtofokus halqasi kompozitsiyada chalg'itmasligi uchun
    page.evaluate("() => document.activeElement && document.activeElement !== document.body && document.activeElement.blur()")


def api_json(page: Page, path: str):
    return page.evaluate(f"() => fetch('{path}').then(r => r.json())")


# Kompozitsiya skripti kesish uchun ishlatadigan element chegaralari (CSS px, hujjat koordinatasi)
REGION_JS = """(specs) => {
  const out = {};
  const rect = (el) => { const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + window.scrollX), y: Math.round(r.top + window.scrollY), w: Math.round(r.width), h: Math.round(r.height)}; };
  for (const spec of specs) {
    if (spec.all) { const els = [...document.querySelectorAll(spec.all)]; out[spec.name] = els.length ? els.map(rect) : null; continue; }
    let el = null;
    if (spec.selector) el = document.querySelector(spec.selector);
    if (spec.text) {
      const nodes = [...document.querySelectorAll(spec.tags || 'h1,h2,p,span')];
      const hit = nodes.find(n => spec.exact ? n.textContent.trim() === spec.text : n.textContent.trim().startsWith(spec.text));
      el = hit || null;
    }
    if (el && spec.closest) el = el.closest(spec.closest);
    if (!el) { out[spec.name] = null; continue; }
    out[spec.name] = rect(el);
  }
  return out;
}"""
REGIONS: dict = {}


def regions(page: Page, key: str, specs: list[dict]) -> None:
    found = page.evaluate(REGION_JS, specs)
    missing = [k for k, v in found.items() if v is None]
    if missing:
        raise RuntimeError(f"{key}: elementlar topilmadi: {missing}")
    REGIONS[key] = found


CARD = ".shadow-card"
KPI_GRID = {"name": "kpis", "text": "Yangi mijozlar", "exact": True, "tags": "p,span", "closest": ".grid"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900}, device_scale_factor=2, timezone_id="Asia/Tashkent", locale="uz-UZ", color_scheme="light"
        )
        page = ctx.new_page()
        login(page, base)

        # 1) Dashboard
        page.goto(f"{base}/")
        settle(page, 1200)
        page.screenshot(path=OUT / "dashboard_1440.png")
        page.screenshot(path=OUT / "dashboard_full_1440.png", full_page=True)
        regions(
            page,
            "dashboard_full_1440",
            [KPI_GRID, {"name": "trend", "text": "Yangi mijozlar va tasdiqlangan", "tags": "h2", "closest": CARD}, {"name": "main", "selector": "main"}],
        )

        # 2) Analitika
        page.goto(f"{base}/analytics")
        settle(page, 1200)
        page.screenshot(path=OUT / "analytics_full_1440.png", full_page=True)
        regions(
            page,
            "analytics_full_1440",
            [
                {"name": "header", "text": "Analitika", "exact": True, "tags": "h1"},
                {"name": "filters", "text": "Guruhlash", "exact": True, "tags": "span", "closest": CARD},
                KPI_GRID,
                {"name": "trend", "text": "Yangi mijozlar va tasdiqlangan", "tags": "h2", "closest": CARD},
                {"name": "courses", "text": "Kurslar bo'yicha", "tags": "h2", "closest": CARD},
                {"name": "funnel", "text": "Funnel:", "tags": "h2", "closest": CARD},
                {"name": "channels", "text": "Kanallar", "exact": True, "tags": "h2", "closest": CARD},
                {"name": "sources", "text": "Manbalar", "exact": True, "tags": "h2", "closest": CARD},
                {"name": "statuses", "text": "Bronlar holati", "exact": True, "tags": "h2", "closest": CARD},
                {"name": "details", "selector": "#analytics-details"},
                {"name": "kpi_conversion", "text": "Mijozdan bronga konversiya", "tags": "p,span", "closest": CARD},
                {"name": "kpi_ai_first", "text": "AI birinchi javob", "tags": "p,span", "closest": CARD},
            ],
        )

        # 3) Suhbatlar — operator javob bergan demo suhbat
        convs = api_json(page, "/api/conversations/?search=Dilnoza&page_size=5")
        conv_id = convs["results"][0]["id"]
        page.goto(f"{base}/conversations/{conv_id}")
        settle(page, 1500)
        page.screenshot(path=OUT / "conversation_operator_1440.png")
        regions(
            page,
            "conversation_operator_1440",
            [
                {"name": "list", "selector": 'aside[aria-label="Suhbatlar ro\'yxati"]'},
                {"name": "chat", "selector": 'section[aria-label="Suhbat"]'},
                {"name": "info", "selector": 'aside[aria-label="Mijoz ma\'lumotlari"]'},
            ],
        )

        # 4) Mijozlar — Kanban va mijoz kartasi
        page.goto(f"{base}/leads")
        settle(page)
        page.get_by_role("radio", name="Kanban").click()
        settle(page, 1200)
        page.screenshot(path=OUT / "leads_kanban_1440.png")
        regions(
            page,
            "leads_kanban_1440",
            [
                spec
                for key, label in [
                    ("new", "Yangi"),
                    ("qualified", "Ehtiyoj aniqlandi"),
                    ("trial_booked", "Sinovga yozildi"),
                    ("trial_attended", "Sinovga keldi"),
                ]
                for spec in ({"name": key, "selector": f'[aria-label^="{label}:"]'}, {"name": f"{key}_cards", "all": f'[aria-label^="{label}:"] article'})
            ],
        )
        page.get_by_role("radio", name="Jadval").click()
        settle(page)
        page.screenshot(path=OUT / "leads_table_1440.png")
        lead = api_json(page, "/api/leads/?search=Dilnoza%20R.&page_size=1")["results"][0]
        page.goto(f"{base}/leads?lead={lead['id']}")
        settle(page, 1200)
        page.get_by_role("tab", name=re.compile("Tarix")).click()
        settle(page, 600)
        page.screenshot(path=OUT / "lead_drawer_history_1440.png")
        regions(
            page,
            "lead_drawer_history_1440",
            [{"name": "drawer", "selector": "[role=dialog]"}, {"name": "history", "text": "Holat o'zgarishlari tarixi", "tags": "p,h3,span"}],
        )

        # 5) Telegram demo oqimi: haqiqiy xabarlar + yaratilgan bron
        tg = api_json(page, "/api/conversations/?channel=telegram&search=Aziza&page_size=5")["results"][0]
        msgs = api_json(page, f"/api/conversations/{tg['id']}/messages/?limit=100")["results"]
        detail = api_json(page, f"/api/conversations/{tg['id']}/")
        booking_id = detail["lead"]["bookings"][0]["id"]
        (OUT / "telegram_demo_conversation.json").write_text(
            json.dumps(
                {
                    "note": "Seed paytida haqiqiy service qatlami (inbound → demo agent → tool → bron) orqali yaratilgan demo suhbat.",
                    "lead": detail["lead"]["display_name"],
                    "booking_id": booking_id,
                    "messages": [{"sender": m["sender"], "text": m["text"], "created_at": m["created_at"]} for m in msgs if m["kind"] != "event"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        page.goto(f"{base}/leads?lead={detail['lead']['id']}")
        settle(page, 1200)
        page.get_by_role("tab", name=re.compile("Tarix")).click()
        settle(page, 600)
        page.screenshot(path=OUT / "lead_drawer_aziza_1440.png")
        regions(
            page,
            "lead_drawer_aziza_1440",
            [{"name": "drawer", "selector": "[role=dialog]"}, {"name": "history", "text": "Holat o'zgarishlari tarixi", "tags": "p,h3,span"}],
        )
        page.keyboard.press("Escape")
        page.goto(f"{base}/bookings?booking={booking_id}")
        settle(page, 1200)
        page.screenshot(path=OUT / "booking_drawer_1440.png")
        regions(
            page, "booking_drawer_1440", [{"name": "drawer", "selector": "[role=dialog]"}, {"name": "history", "text": "Hodisalar tarixi", "tags": "p,h3,span"}]
        )
        page.keyboard.press("Escape")
        settle(page, 600)
        page.screenshot(path=OUT / "bookings_week_1440.png")

        # 6) Mobil panel
        mctx = browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=3, timezone_id="Asia/Tashkent", locale="uz-UZ", color_scheme="light"
        )
        mpage = mctx.new_page()
        login(mpage, base)
        settle(mpage, 1200)
        mpage.screenshot(path=OUT / "dashboard_mobile_390.png")

        # 7) Veb-chat (mobil) — haqiqiy so'rov bilan
        vctx = browser.new_context(
            viewport={"width": 390, "height": 780}, device_scale_factor=3, timezone_id="Asia/Tashkent", locale="uz-UZ", color_scheme="light"
        )
        vpage = vctx.new_page()
        vpage.goto(f"{base}/chat/wk_demo_academy")
        vpage.get_by_text("Demo maket").wait_for()
        vpage.get_by_role("combobox", name=re.compile("Til")).select_option("uz")
        vpage.get_by_label(re.compile("Xabaringizni yozing")).fill("IELTS kursi narxi qancha?")
        vpage.get_by_role("button", name="Yuborish").click()
        vpage.wait_for_function("() => document.querySelectorAll('[aria-live=polite] .whitespace-pre-wrap').length >= 3")
        vpage.wait_for_timeout(1200)
        vpage.screenshot(path=OUT / "webchat_mobile_390.png")

        # 8) Veb-chat (mobil) — o'sha suhbatni haqiqiy bron tasdig'igacha davom ettirish
        bubbles = "() => document.querySelectorAll('[aria-live=polite] .whitespace-pre-wrap').length"
        for text in ["Ha, sinov darsiga yozilmoqchiman", "Chilonzor", "Kechqurun", "1", "Malika", "+998 00 765 43 21", "Ha", "Ha"]:
            before = vpage.evaluate(bubbles)
            vpage.get_by_label(re.compile("Xabaringizni yozing")).fill(text)
            vpage.get_by_role("button", name="Yuborish").click()
            vpage.wait_for_function(f"() => ({bubbles})() >= {before + 2}", timeout=20000)
            vpage.wait_for_timeout(500)
        vpage.get_by_text(re.compile("Siz sinov darsiga yozildingiz")).first.wait_for()
        vpage.set_viewport_size({"width": 390, "height": 844})
        vpage.wait_for_timeout(1200)
        vpage.screenshot(path=OUT / "webchat_booking_mobile_390.png")

        # 9) Veb-chatda yaratilgan bron panelda (o'sha bron yozuvi)
        web_booking = api_json(page, "/api/bookings/?search=Malika&channel=webchat&ordering=-confirmed_at&page_size=1")["results"][0]
        page.goto(f"{base}/bookings?booking={web_booking['id']}")
        settle(page, 1200)
        page.screenshot(path=OUT / "booking_drawer_webchat_1440.png")
        regions(
            page,
            "booking_drawer_webchat_1440",
            [
                {"name": "drawer", "selector": "[role=dialog]"},
                {"name": "history", "text": "Hodisalar tarixi", "tags": "p,h3,span"},
                {"name": "row_kanal", "text": "Kanal", "exact": True, "tags": "dt", "closest": "div"},
            ],
        )
        browser.close()
    (OUT / "regions.json").write_text(json.dumps(REGIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Screenshots:", ", ".join(sorted(f.name for f in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
