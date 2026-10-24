import re
import time

from conftest import BASE_URL, WIDGET_KEY, login
from playwright.sync_api import expect


def kpi_value(page, label):
    card = page.locator("div.rounded-\\[14px\\]", has=page.get_by_text(label, exact=True)).first
    return card.locator("p.text-\\[26px\\]").inner_text()


def test_login_dashboard_filter_and_chart(owner_page):
    page = owner_page
    expect(page.get_by_text("Demo ma'lumotlar").first).to_be_visible()
    before = kpi_value(page, "Yangi mijozlar")
    with page.expect_response(lambda r: "/api/analytics/overview/" in r.url and r.status == 200) as resp:
        page.get_by_role("button", name=re.compile("Sana oralig'i")).click()
        page.get_by_role("menu").get_by_role("button", name="7 kun").click()
    assert "date_from" in resp.value.url
    page.wait_for_timeout(400)
    after = kpi_value(page, "Yangi mijozlar")
    assert before != after, "Davr filtri KPI qiymatini o'zgartirishi kerak"
    # Haftalik guruhlash grafikni qayta so'raydi
    with page.expect_response(lambda r: "granularity=week" in r.url):
        page.get_by_role("radio", name="Hafta").click()
    # Grafik nuqtasini bosish — filtrlangan tafsilotlar
    page.get_by_role("radio", name="Kun").click()
    page.wait_for_timeout(500)
    chart = page.get_by_role("img", name=re.compile("Chiziqli grafik")).first
    box = chart.bounding_box()
    x, y = box["x"] + box["width"] * 0.9, box["y"] + box["height"] * 0.5
    page.mouse.move(x - 20, y)
    page.mouse.move(x, y, steps=4)
    page.wait_for_timeout(250)
    page.mouse.click(x, y)
    drawer = page.get_by_role("dialog")
    expect(drawer).to_be_visible()
    expect(drawer.get_by_text(re.compile("Yangi mijozlar —"))).to_be_visible()
    # Jadval ko'rinishi (grafik ma'nosi faqat rangga bog'liq emas)
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Jadval").first.click()
    expect(page.get_by_role("columnheader", name="Yangi mijozlar")).to_be_visible()
    assert not page.console_errors


def test_lead_create_status_and_details(owner_page):
    page = owner_page
    name = f"Sinovjon Avtotest {int(time.time()) % 100000}"
    page.get_by_role("link", name="Mijozlar").first.click()
    page.get_by_role("button", name="Yangi mijoz").first.click()
    dialog = page.get_by_role("dialog", name="Yangi mijoz")
    dialog.get_by_label("Ism").fill(name)
    dialog.get_by_label("Telefon").fill("+998 00 765 11 22")
    dialog.get_by_role("button", name="Qo'shish").click()
    drawer = page.get_by_role("dialog", name=name)
    expect(drawer).to_be_visible()
    expect(page.get_by_text("Mijoz qo'shildi")).to_be_visible()
    drawer.get_by_label("Holat").select_option("qualified")
    expect(page.get_by_text("Holat o'zgartirildi")).to_be_visible()
    drawer.get_by_role("tab", name=re.compile("Tarix")).click()
    expect(drawer.get_by_text("Yangi →")).to_be_visible()
    drawer.get_by_label("Yangi eslatma").fill("E2E: ertaga qo'ng'iroq qilish")
    drawer.get_by_role("button", name="Eslatma qo'shish").click()
    expect(drawer.get_by_text("E2E: ertaga qo'ng'iroq qilish")).to_be_visible()
    page.keyboard.press("Escape")
    page.get_by_label("Qidirish", exact=True).fill(name)
    row = page.get_by_role("row", name=re.compile(name))
    expect(row).to_be_visible()
    expect(row.get_by_text("Ehtiyoj aniqlandi")).to_be_visible()
    # Kanban ko'rinishi
    page.get_by_role("radio", name="Kanban").click()
    expect(page.get_by_role("region", name=re.compile("Ehtiyoj aniqlandi"))).to_be_visible()
    page.get_by_role("radio", name="Jadval").click()


BUBBLES = "[aria-live=polite] .whitespace-pre-wrap"


def _chat(page, text):
    before = page.locator(BUBBLES).count()
    page.get_by_label(re.compile("Xabaringizni yozing")).fill(text)
    page.get_by_role("button", name="Yuborish").click()
    page.wait_for_function("(n) => document.querySelectorAll('[aria-live=polite] .whitespace-pre-wrap').length >= n", arg=before + 2)
    page.wait_for_timeout(250)
    return page.locator(BUBBLES).last.inner_text()


def test_webchat_booking_appears_in_panel_and_operator_reply(new_page):
    visitor = new_page(420, 820)
    visitor.goto(f"{BASE_URL}/chat/{WIDGET_KEY}")
    expect(visitor.get_by_text("Demo maket")).to_be_visible()
    visitor.get_by_role("combobox", name=re.compile("Til")).select_option("uz")
    reply = _chat(visitor, "IELTS sinov darsiga yozilmoqchiman")
    assert "filial" in reply.lower() or "vaqt" in reply.lower()
    if "filial" in reply.lower():
        reply = _chat(visitor, "Chilonzor")
    reply = _chat(visitor, "farqi yo'q")
    assert "Bo'sh sinov darslari" in reply, reply
    reply = _chat(visitor, "1")
    assert "ismingizni" in reply
    name = "Testbek Brauzerov"
    reply = _chat(visitor, name)
    assert "Telefon" in reply
    reply = _chat(visitor, "+998 00 321 54 76")
    assert "tasdiqlang" in reply.lower()
    reply = _chat(visitor, "Ha")
    assert "yozildingiz" in reply, reply
    booking_id = re.search(r"#(\d+)", reply).group(1)

    # Panelda (menejer) bron ko'rinadi
    panel = new_page()
    login(panel, "manager@demo.qabulflow.local")
    panel.goto(f"{BASE_URL}/bookings?booking={booking_id}")
    drawer = panel.get_by_role("dialog", name=f"Bron #{booking_id}")
    expect(drawer).to_be_visible()
    expect(drawer.get_by_text(name)).to_be_visible()
    expect(drawer.get_by_text("Veb-chat")).to_be_visible()
    conv_link = drawer.get_by_role("link", name=re.compile("suhbatni ochish"))
    conv_link.click()
    panel.wait_for_url(re.compile(r"/conversations/\d+"))

    # Operator suhbatni oladi va javob beradi
    panel.get_by_role("button", name="Suhbatni olish").first.click()
    expect(panel.get_by_text("Suhbat sizga o'tdi")).to_be_visible()
    panel.get_by_label("Javob matni").fill("Assalomu alaykum! Men administratorman, sizni kutamiz.")
    panel.get_by_role("button", name="Yuborish").click()
    expect(panel.get_by_text("Assalomu alaykum! Men administratorman, sizni kutamiz.")).to_be_visible()
    # Mijoz tomonida operator javobi ko'rinadi (polling)
    expect(visitor.get_by_text("Assalomu alaykum! Men administratorman, sizni kutamiz.")).to_be_visible(timeout=12000)
    # AI operator rejimida javob bermaydi
    visitor.get_by_label(re.compile("Xabaringizni yozing")).fill("Rahmat, kelaman")
    visitor.get_by_role("button", name="Yuborish").click()
    visitor.wait_for_timeout(1500)
    assert "Arzimaydi" not in visitor.locator("[aria-live=polite]").first.inner_text()
    # AI'ga qaytarish
    panel.get_by_role("button", name=re.compile("AI'ga qaytarish")).click()
    expect(panel.get_by_text("Suhbat AI'ga qaytarildi")).to_be_visible()


def test_mobile_navigation_and_actions(new_page):
    page = new_page(390, 844)
    login(page, "owner@demo.qabulflow.local")
    page.get_by_role("button", name="Menyuni ochish").click()
    page.get_by_role("dialog", name="Menyu").get_by_role("link", name="Sinov darslari").click()
    expect(page.get_by_role("heading", name="Sinov darslari")).to_be_visible()
    expect(page.get_by_role("button", name="Bron yaratish")).to_be_visible()
    page.get_by_role("button", name="Bron yaratish").click()
    expect(page.get_by_role("dialog", name="Sinov darsiga yozish")).to_be_visible()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Menyuni ochish").click()
    page.get_by_role("dialog", name="Menyu").get_by_role("link", name="Mijozlar").click()
    page.get_by_role("button", name=re.compile("^Filtr")).click()
    expect(page.get_by_label("Holat", exact=True)).to_be_visible()
    page.locator("ul.divide-y button").first.click()
    expect(page.get_by_role("button", name="Sinov darsiga yozish")).to_be_visible()
    # Gorizontal scroll yo'q
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_tablet_collapsed_sidebar(new_page):
    page = new_page(1024, 768)
    login(page, "owner@demo.qabulflow.local")
    page.locator("a[title='Analitika']").click()
    expect(page.get_by_role("heading", name="Analitika")).to_be_visible()
    expect(page.get_by_role("button", name="CSV eksport")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_operator_cannot_open_analytics(new_page):
    page = new_page()
    login(page, "operator@demo.qabulflow.local")
    page.goto(f"{BASE_URL}/analytics")
    expect(page.get_by_text("Bu bo'lim sizning rolingiz uchun yopiq")).to_be_visible()
