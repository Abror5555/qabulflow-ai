"""assets/screenshots/ dagi haqiqiy ekran tasvirlaridan 7 ta yakuniy PNG kompozitsiya yaratadi.

    python showcase/render_showcase.py            # assets/showcase/*.png
    python showcase/render_showcase.py --keep-html # HTML manbalarni ham showcase/build/ ga saqlaydi

Kompozitsiyalar HTML/CSS bilan quriladi va Python Playwright (Chromium) orqali aniq
o'lchamda PNG ga eksport qilinadi. Grafik va panel qayta chizilmaydi — faqat
capture_screenshots.py olgan asl ekranlar kesiladi va joylashtiriladi. Telegram
uslubidagi maket esa ilovaning demo oqimidan olingan xabarlar (telegram_demo_conversation.json)
asosida kod orqali chiziladi va "Demo maket" belgisi bilan ko'rsatiladi.

Skript yakunda har bir PNG ning o'lchamini, ochilishini, rasm/shriftlar yuklanganini
va elementlar kadrdan chiqib ketmaganini tekshiradi.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "assets" / "screenshots"
OUT = ROOT / "assets" / "showcase"
FONTS = Path(__file__).resolve().parent / "fonts"

# Panel bilan bir xil ranglar
BG = "#F6F8FC"
LINE = "#E6EAF2"
ACCENT = "#4F46E5"
TEAL = "#14B8A6"
INK = "#0F172A"

LOGO = (
    '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#4F46E5"/>'
    '<path d="M9 11.5a2.5 2.5 0 0 1 2.5-2.5h9a2.5 2.5 0 0 1 2.5 2.5v6a2.5 2.5 0 0 1-2.5 2.5H15l-4 3v-3h0.5A2.5 2.5 0 0 1 9 17.5z" fill="#fff"/>'
    '<circle cx="21.5" cy="21.5" r="4.5" fill="#14B8A6" stroke="#4F46E5" stroke-width="1.5"/>'
    '<path d="m19.6 21.6 1.3 1.3 2.4-2.6" stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


# --------------------------------------------------------------------------- manbalar


@dataclass
class Shot:
    name: str
    path: Path
    dpr: int
    width: float  # CSS px
    height: float

    @property
    def uri(self) -> str:
        return self.path.resolve().as_uri()

    def pixel(self, x: float, y: float) -> tuple[int, int, int]:
        with Image.open(self.path) as im:
            return im.convert("RGB").getpixel((int(x * self.dpr), int(y * self.dpr)))


def load_shot(name: str) -> Shot:
    path = SHOTS / f"{name}.png"
    if not path.exists():
        raise SystemExit(f"{path} topilmadi. Avval: python showcase/capture_screenshots.py")
    dpr = 3 if name.endswith("_390") else 2
    with Image.open(path) as im:
        w, h = im.size
    return Shot(name, path, dpr, w / dpr, h / dpr)


def load_regions() -> dict:
    path = SHOTS / "regions.json"
    if not path.exists():
        raise SystemExit("assets/screenshots/regions.json topilmadi. Avval capture_screenshots.py ni ishga tushiring.")
    return json.loads(path.read_text(encoding="utf-8"))


def rgb_hex(c: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*c)


def is_dark(c: tuple[int, int, int]) -> bool:
    r, g, b = c
    return (0.299 * r + 0.587 * g + 0.114 * b) < 150


# --------------------------------------------------------------------------- umumiy uslub


def font_faces() -> str:
    faces = [
        (
            "inter-latin-wght-normal.woff2",
            "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        ),
        (
            "inter-latin-ext-wght-normal.woff2",
            "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        ),
        ("inter-cyrillic-wght-normal.woff2", "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116"),
    ]
    return "\n".join(
        f"@font-face{{font-family:'InterShow';font-style:normal;font-weight:100 900;font-display:block;src:url('{(FONTS / f).resolve().as_uri()}') format('woff2');unicode-range:{r};}}"
        for f, r in faces
    )


BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:var(--w);height:var(--h);overflow:hidden}
body{font-family:'InterShow',system-ui,sans-serif;color:%(ink)s;background:%(bg)s;position:relative;
  -webkit-font-smoothing:antialiased;font-feature-settings:'cv11','ss01'}
.bg{position:absolute;inset:0;overflow:hidden}
.bg::before{content:'';position:absolute;inset:0;
  background-image:radial-gradient(#D9DFEA 1.3px,transparent 1.4px);background-size:28px 28px;
  -webkit-mask-image:radial-gradient(ellipse at 50%% 40%%,rgba(0,0,0,.55),rgba(0,0,0,0) 72%%)}
.glow{position:absolute;border-radius:50%%;filter:blur(10px)}
.glow.a{background:radial-gradient(circle,rgba(79,70,229,.16),rgba(79,70,229,0) 68%%)}
.glow.t{background:radial-gradient(circle,rgba(20,184,166,.15),rgba(20,184,166,0) 68%%)}
.abs{position:absolute}
.hdr{position:absolute;display:flex;align-items:center;gap:calc(16px*var(--k))}
.brand{display:flex;align-items:center;gap:calc(12px*var(--k));font-weight:650;font-size:calc(26px*var(--k));letter-spacing:-.015em;white-space:nowrap}
.brand svg{width:calc(40px*var(--k));height:calc(40px*var(--k));flex:none}
.brand b{color:%(accent)s;font-weight:650}
.sep{width:1px;height:calc(26px*var(--k));background:#CFD6E3}
.screen{color:#475569;font-size:calc(19px*var(--k));font-weight:500;white-space:nowrap}
.spacer{flex:1}
.demo{display:inline-flex;align-items:center;gap:calc(8px*var(--k));height:calc(34px*var(--k));padding:0 calc(14px*var(--k));
  border-radius:999px;border:1px solid #FCD34D;background:#FFFBEB;color:#92400E;font-weight:600;font-size:calc(15px*var(--k));white-space:nowrap}
.demo i{width:calc(8px*var(--k));height:calc(8px*var(--k));border-radius:50%%;background:#F59E0B;flex:none}
.card{position:absolute;overflow:hidden;background:#fff;
  box-shadow:0 1px 2px rgba(15,23,42,.06),0 18px 48px -18px rgba(15,23,42,.24),0 2px 8px -2px rgba(15,23,42,.06)}
.card>img{position:absolute;display:block;max-width:none}
.frame{border:1px solid %(line)s}
.step{position:absolute;display:flex;align-items:center;gap:calc(10px*var(--k));font-size:calc(17px*var(--k));font-weight:600;color:#1E293B;white-space:nowrap}
.step .n{display:inline-flex;align-items:center;justify-content:center;width:calc(28px*var(--k));height:calc(28px*var(--k));border-radius:50%%;
  background:%(accent)s;color:#fff;font-size:calc(14px*var(--k));font-weight:700;flex:none}
.step .muted{color:#64748B;font-weight:500}
.arrow{position:absolute;color:#94A3B8}
/* telefon */
.phone{position:absolute;background:#0B1220;border-radius:calc(var(--pw)*0.118);padding:calc(var(--pw)*0.026);
  box-shadow:0 2px 4px rgba(15,23,42,.18),0 30px 70px -24px rgba(15,23,42,.45),inset 0 0 0 1.5px #334155}
.phone .scr{position:relative;width:100%%;height:100%%;overflow:hidden;border-radius:calc(var(--pw)*0.094);background:#fff}
.phone .island{position:absolute;left:50%%;transform:translateX(-50%%);top:calc(var(--pw)*0.022);width:calc(var(--pw)*0.27);height:calc(var(--pw)*0.068);
  border-radius:999px;background:#000;z-index:5}
.sbar{position:relative;display:flex;align-items:center;justify-content:space-between;padding:0 calc(var(--pw)*0.075);font-weight:600;
  font-size:calc(var(--pw)*0.036);letter-spacing:.01em}
.sbar .ic{display:flex;gap:calc(var(--pw)*0.012);align-items:center}
.sbar svg{height:calc(var(--pw)*0.03);width:auto}
.phone .shot{display:block;width:100%%}
"""


def page_html(w: int, h: int, body: str, k: float = 1.0, extra_css: str = "") -> str:
    css = BASE_CSS % {"ink": INK, "bg": BG, "accent": ACCENT, "line": LINE}
    return (
        "<!doctype html><html lang='uz'><head><meta charset='utf-8'>"
        f"<style>{font_faces()}\n:root{{--w:{w}px;--h:{h}px;--k:{k}}}\n{css}\n{extra_css}</style></head>"
        f"<body><div class='bg'></div>{body}</body></html>"
    )


def glow(kind: str, x: int, y: int, size: int) -> str:
    return f"<div class='glow {kind}' style='left:{x - size // 2}px;top:{y - size // 2}px;width:{size}px;height:{size}px'></div>"


def demo_badge(label: str = "Demo ma'lumotlar") -> str:
    return f"<span class='demo' data-check><i></i>{html.escape(label)}</span>"


def header(label: str | None, *, left: int, top: int, right: int | None = None, badge: bool = True) -> str:
    style = f"left:{left}px;top:{top}px;" + (f"right:{right}px;" if right is not None else "")
    parts = [f"<div class='brand'>{LOGO}<span>QabulFlow <b>AI</b></span></div>"]
    if label:
        parts += ["<span class='sep'></span>", f"<span class='screen'>{html.escape(label)}</span>"]
    if right is not None:
        parts.append("<span class='spacer'></span>")
    if badge:
        parts.append(demo_badge())
    return f"<div class='hdr' data-check style='{style}'>{''.join(parts)}</div>"


def crop(
    shot: Shot,
    region: tuple[float, float, float, float],
    *,
    left: float,
    top: float,
    scale: float,
    radius: float = 14,
    frame: bool = False,
    z: int = 1,
    extra: str = "",
) -> str:
    """Ekran tasvirining (x, y, w, h) CSS-px qismini scale bilan joylashtiradi."""
    x, y, w, h = region
    if x < 0 or y < 0 or x + w > shot.width + 0.5 or y + h > shot.height + 0.5:
        raise ValueError(f"{shot.name}: kesish hududi rasm chegarasidan tashqarida: {region}")
    cls = "card frame" if frame else "card"
    return (
        f"<div class='{cls}' data-check style='left:{left:.1f}px;top:{top:.1f}px;width:{w * scale:.1f}px;height:{h * scale:.1f}px;border-radius:{radius * scale:.1f}px;z-index:{z};{extra}'>"
        f"<img src='{shot.uri}' style='width:{shot.width * scale:.1f}px;left:{-x * scale:.1f}px;top:{-y * scale:.1f}px' alt=''></div>"
    )


def card_region(r: dict, pad: float = 0) -> tuple[float, float, float, float]:
    return (r["x"] - pad, r["y"] - pad, r["w"] + 2 * pad, r["h"] + 2 * pad)


SIGNAL = '<svg viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1" fill="currentColor"/><rect x="5" y="5.5" width="3" height="6.5" rx="1" fill="currentColor"/><rect x="10" y="3" width="3" height="9" rx="1" fill="currentColor"/><rect x="15" y="0" width="3" height="12" rx="1" fill="currentColor"/></svg>'
WIFI = '<svg viewBox="0 0 16 12"><path d="M8 11.5 5.6 8.9a3.4 3.4 0 0 1 4.8 0z" fill="currentColor"/><path d="M3.4 6.7a6.5 6.5 0 0 1 9.2 0l-1.3 1.4a4.6 4.6 0 0 0-6.6 0z" fill="currentColor"/><path d="M1.2 4.4a9.6 9.6 0 0 1 13.6 0l-1.3 1.4a7.7 7.7 0 0 0-11 0z" fill="currentColor"/></svg>'
BATTERY = '<svg viewBox="0 0 27 12"><rect x=".5" y=".5" width="23" height="11" rx="3.2" fill="none" stroke="currentColor" opacity=".45"/><rect x="2" y="2" width="17" height="8" rx="2" fill="currentColor"/><rect x="24.6" y="4" width="1.8" height="4" rx=".9" fill="currentColor" opacity=".45"/></svg>'


def status_bar(time_text: str, height: float, bg: str, fg: str) -> str:
    return f"<div class='sbar' style='height:{height:.1f}px;background:{bg};color:{fg}'><span>{time_text}</span><span class='ic'>{SIGNAL}{WIFI}{BATTERY}</span></div>"


def shot_clock(shot: Shot) -> str:
    """Telefon holat qatori uchun vaqt: ekran tasviri olingan payt (Toshkent vaqti)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.fromtimestamp(shot.path.stat().st_mtime, ZoneInfo("Asia/Tashkent")).strftime("%H:%M")


def phone_height(shot: Shot, width: float) -> float:
    bezel = width * 0.026
    scale = (width - 2 * bezel) / shot.width
    return 46 * scale + shot.height * scale + 2 * bezel


def phone_with_shot(shot: Shot, *, left: float, width: float, top: float | None = None, bottom: float | None = None, z: int = 3) -> str:
    """Mobil ekran tasvirini telefon ramkasiga joylaydi (top yoki bottom — kanvas koordinatasi)."""
    bezel = width * 0.026
    inner = width - 2 * bezel
    scale = inner / shot.width
    bar_h = 46 * scale
    total_h = phone_height(shot, width)
    if top is None:
        top = bottom - total_h
    top_color = shot.pixel(4, 4)
    fg = "#fff" if is_dark(top_color) else INK
    return (
        f"<div class='phone' data-check style='--pw:{width:.1f}px;left:{left:.1f}px;top:{top:.1f}px;width:{width:.1f}px;height:{total_h:.1f}px;z-index:{z}'>"
        f"<div class='scr'><div class='island'></div>{status_bar(shot_clock(shot), bar_h, rgb_hex(top_color), fg)}"
        f"<img class='shot' src='{shot.uri}' alt=''></div></div>"
    )


# --------------------------------------------------------------------------- Telegram uslubidagi maket

TG_CSS = """
.tg{position:relative;display:flex;flex-direction:column;height:100%;background:#fff;font-size:calc(var(--pw)*0.0335);line-height:1.36}
.tg .top{display:flex;align-items:center;gap:calc(var(--pw)*0.028);padding:calc(var(--pw)*0.018) calc(var(--pw)*0.035);background:#fff;border-bottom:1px solid #E5E9F0}
.tg .back{color:#3390EC;font-size:calc(var(--pw)*0.05);font-weight:400;width:calc(var(--pw)*0.04)}
.tg .ava{width:calc(var(--pw)*0.092);height:calc(var(--pw)*0.092);flex:none}
.tg .ava svg{width:100%;height:100%}
.tg .ttl{display:flex;flex-direction:column;min-width:0}
.tg .ttl b{font-weight:600;font-size:calc(var(--pw)*0.036);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tg .ttl span{color:#8A96A8;font-size:calc(var(--pw)*0.029)}
.tg .demo-bar{display:flex;align-items:center;justify-content:center;gap:calc(var(--pw)*0.014);height:calc(var(--pw)*0.062);
  background:#FFFBEB;border-bottom:1px solid #FDE68A;color:#92400E;font-weight:600;font-size:calc(var(--pw)*0.028)}
.tg .demo-bar i{width:calc(var(--pw)*0.016);height:calc(var(--pw)*0.016);border-radius:50%;background:#F59E0B}
.tg .chat{position:relative;flex:1;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;gap:calc(var(--pw)*0.012);
  padding:calc(var(--pw)*0.02) calc(var(--pw)*0.03) calc(var(--pw)*0.028);
  background:linear-gradient(160deg,#DCE8D2 0%,#E7EED5 45%,#D3E3DA 100%)}
.tg .chat::before{content:'';position:absolute;inset:0;opacity:.35;
  background-image:radial-gradient(rgba(255,255,255,.9) 1.2px,transparent 1.4px);background-size:22px 22px}
.tg .date{align-self:center;position:relative;background:rgba(74,99,84,.42);color:#fff;font-weight:600;font-size:calc(var(--pw)*0.028);
  padding:calc(var(--pw)*0.006) calc(var(--pw)*0.022);border-radius:999px;margin-bottom:calc(var(--pw)*0.006)}
.tg .m{position:relative;max-width:80%;padding:calc(var(--pw)*0.016) calc(var(--pw)*0.026) calc(var(--pw)*0.012);border-radius:calc(var(--pw)*0.036);
  white-space:pre-wrap;word-wrap:break-word;box-shadow:0 1px 1px rgba(16,35,47,.12)}
.tg .m.in{align-self:flex-start;background:#fff;border-bottom-left-radius:calc(var(--pw)*0.01)}
.tg .m.out{align-self:flex-end;background:#EEFFDE;border-bottom-right-radius:calc(var(--pw)*0.01)}
.tg .m .t{float:right;margin:calc(var(--pw)*0.012) 0 calc(var(--pw)*-0.004) calc(var(--pw)*0.022);font-size:calc(var(--pw)*0.024);color:#8A96A8;line-height:1.6;white-space:nowrap}
.tg .m.out .t{color:#5DAF5B}
.tg .input{display:flex;align-items:center;gap:calc(var(--pw)*0.03);padding:calc(var(--pw)*0.022) calc(var(--pw)*0.035) calc(var(--pw)*0.05);background:#fff;border-top:1px solid #E5E9F0;color:#8A96A8}
.tg .input .field{flex:1;font-size:calc(var(--pw)*0.034)}
.tg .input svg{width:calc(var(--pw)*0.055);height:calc(var(--pw)*0.055);flex:none}
"""

CLIP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.4 3.4 0 0 1 4.8 4.8l-8.4 8.4a1.7 1.7 0 0 1-2.4-2.4L15.5 7.3"/></svg>'
MIC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>'


def telegram_phone(data: dict, *, left: float, top: float, width: float, height: float) -> str:
    messages = [m for m in data["messages"] if m.get("text")]
    bezel = width * 0.026
    inner = width - 2 * bezel
    last_time = re.search(r"T(\d{2}:\d{2})", messages[-1]["created_at"]).group(1)
    day = re.search(r"\d{4}-(\d{2})-(\d{2})", messages[-1]["created_at"])
    months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    date_text = f"{int(day.group(2))}-{months[int(day.group(1)) - 1]}"
    bubbles = []
    for m in messages:
        t = re.search(r"T(\d{2}:\d{2})", m["created_at"]).group(1)
        out = m["sender"] == "customer"
        tick = " ✓✓" if out else ""
        bubbles.append(f"<div class='m {'out' if out else 'in'}'>{html.escape(m['text'])}<span class='t'>{t}{tick}</span></div>")
    bar_h = inner * 0.118
    return (
        f"<div class='phone' data-check style='--pw:{inner:.1f}px;left:{left:.1f}px;top:{top:.1f}px;width:{width:.1f}px;height:{height:.1f}px;z-index:3;padding:{bezel:.1f}px'>"
        f"<div class='scr' style='display:flex;flex-direction:column'><div class='island'></div>{status_bar(last_time, bar_h, '#ffffff', INK)}"
        "<div class='tg' style='flex:1;min-height:0'>"
        f"<div class='top'><span class='back'>‹</span><span class='ava'>{LOGO}</span><span class='ttl'><b>QabulFlow Demo Academy</b><span>bot</span></span></div>"
        "<div class='demo-bar'><i></i>Demo maket · ilovaning demo oqimidagi xabarlar</div>"
        f"<div class='chat' id='tgchat'><div class='date'>{date_text}</div>{''.join(bubbles)}</div>"
        f"<div class='input'>{CLIP}<span class='field'>Xabar</span>{MIC}</div>"
        "</div></div></div>"
    )


# Sig'magan eng eski xabarlarni olib tashlaydi (chat pastga "aylantirilgan" holat), sana belgisi qoladi
FIT_TG_JS = """() => {
  const chat = document.getElementById('tgchat');
  if (!chat) return 0;
  // flex-end holatida yuqoriga toshgan qism scrollHeight'da ko'rinmaydi — o'lchash vaqtida flex-start
  chat.style.justifyContent = 'flex-start';
  let removed = 0;
  while (chat.scrollHeight > chat.clientHeight + 1) {
    const first = chat.querySelector('.m');
    if (!first) break;
    first.remove(); removed++;
  }
  chat.style.justifyContent = '';
  return removed;
}"""


# --------------------------------------------------------------------------- kompozitsiyalar


def comp_dashboard(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1920, 1080
    dash = shots["dashboard_1440"]
    body = glow("a", 1780, 80, 900) + glow("t", 120, 1040, 800)
    body += header("Asosiy panel", left=240, top=40, right=240)
    body += crop(dash, (0, 0, 1440, 900), left=240, top=116, scale=1.0, radius=16, frame=True)
    return w, h, body, ""


def kanban_crop(regions: dict, key: str, n_cards: int) -> tuple[float, float, float, float]:
    """Kanban ustunini sarlavha + n ta to'liq karta bilan kesadi (karta o'rtasidan kesilmaydi)."""
    r = regions["leads_kanban_1440"]
    col = r[key]
    cards = [c for c in r[f"{key}_cards"] if c["y"] + c["h"] <= col["y"] + col["h"]]
    n = min(n_cards, len(cards))
    bottom = cards[n - 1]["y"] + cards[n - 1]["h"] + 8
    return (col["x"], col["y"], col["w"], bottom - col["y"])


def stitched_card(shot: Shot, parts: list[tuple[float, float, float, float]], *, left: float, top: float, scale: float, radius: float = 14) -> str:
    """Bitta drawer'ning bir nechta vertikal qismini (masalan sarlavha + tarix) bitta kartada ketma-ket ko'rsatadi."""
    width = parts[0][2] * scale
    total = sum(p[3] for p in parts) * scale
    inner, y = [], 0.0
    for i, (x, py, _pw, ph) in enumerate(parts):
        inner.append(
            f"<div style='position:absolute;left:0;top:{y:.1f}px;width:{width:.1f}px;height:{ph * scale:.1f}px;overflow:hidden'>"
            f"<img src='{shot.uri}' style='position:absolute;display:block;max-width:none;width:{shot.width * scale:.1f}px;left:{-x * scale:.1f}px;top:{-py * scale:.1f}px' alt=''></div>"
        )
        if i:
            inner.append(f"<div style='position:absolute;left:0;right:0;top:{y:.1f}px;height:1px;background:{LINE}'></div>")
        y += ph * scale
    return f"<div class='card frame' data-check style='left:{left:.1f}px;top:{top:.1f}px;width:{width:.1f}px;height:{total:.1f}px;border-radius:{radius * scale:.1f}px'>{''.join(inner)}</div>"


def step(n: str, text: str, muted: str = "", *, left: float, top: float, k: float = 1.0) -> str:
    extra = f" <span class='muted'>· {html.escape(muted)}</span>" if muted else ""
    return f"<div class='step' data-check style='left:{left:.0f}px;top:{top:.0f}px;--k:{k}'><span class='n'>{n}</span>{html.escape(text)}{extra}</div>"


def comp_telegram(shots: dict, regions: dict, tg: dict) -> tuple[int, int, str, str]:
    w, h = 1600, 1200
    booking = shots["booking_drawer_1440"]
    kanban = shots["leads_kanban_1440"]
    aziza = shots["lead_drawer_aziza_1440"]
    rb = regions["booking_drawer_1440"]
    ra = regions["lead_drawer_aziza_1440"]
    margin = 64
    body = glow("a", 1500, 120, 800) + glow("t", 200, 1100, 760)
    body += header("Telegram suhbatdan bron va CRM yozuvigacha", left=margin, top=36, right=margin)

    top = 168
    phone_w, phone_h = 468, h - 40 - top
    body += step("1", "Telegram suhbat", "demo maket", left=margin, top=118)
    body += telegram_phone(tg, left=margin, top=top, width=phone_w, height=phone_h)

    s = 1.2
    col_left = margin + phone_w + 52
    # 2) Panel: bron yozuvi (sarlavha → hodisalar tarixi)
    d = rb["drawer"]
    reg_booking = (d["x"] + 1, 0, d["w"] - 1, rb["history"]["y"] + 76)
    body += step("2", "Bron tasdiqlandi", "Sinov darslari", left=col_left, top=118)
    body += crop(booking, reg_booking, left=col_left, top=top, scale=s, radius=14, frame=True)
    booking_bottom = top + reg_booking[3] * s

    # 3) CRM: Kanban "Sinovga yozildi" ustuni
    k_left = col_left + reg_booking[2] * s + 24
    reg_k = kanban_crop(regions, "trial_booked", 3)
    body += step("3", "CRM holati", left=k_left, top=118)
    body += crop(kanban, reg_k, left=k_left, top=top, scale=s, radius=14, extra="max-height:none")

    # 3) Mijoz kartasi: sarlavha + holat o'zgarishlari tarixi (bitta drawer'ning ikki qismi)
    a = ra["drawer"]
    hy = ra["history"]["y"]
    parts = [(a["x"] + 1, 0, a["w"] - 1, 84), (a["x"] + 1, hy - 16, a["w"] - 1, 188)]
    body += stitched_card(aziza, parts, left=col_left, top=booking_bottom + 24, scale=s)
    return w, h, body, TG_CSS


def comp_crm(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1920, 1080
    conv = shots["conversation_operator_1440"]
    kanban = shots["leads_kanban_1440"]
    dil = shots["lead_drawer_history_1440"]
    rc = regions["conversation_operator_1440"]
    rd = regions["lead_drawer_history_1440"]
    top, bottom_margin, gap = 132, 44, 32
    # Suhbat + mijoz kartasi balandlik bo'yicha sig'diriladi
    cx, cy = rc["chat"]["x"], rc["chat"]["y"]
    cw = rc["info"]["x"] + rc["info"]["w"] - cx + 1
    ch = rc["chat"]["h"] + 1
    s = (h - top - bottom_margin) / ch
    # Chap: CRM holatlari (Kanban'ning ikki ustuni, to'liq kartalar bilan)
    k1 = kanban_crop(regions, "new", 4)
    k2 = kanban_crop(regions, "qualified", 4)
    kx, ky = k1[0] - 1, k1[1] - 1
    kw = k2[0] + k2[2] - k1[0] + 2
    kh = max(k1[3], k2[3]) + 2
    total_w = kw * s + gap + cw * s
    margin = (w - total_w) / 2
    body = glow("a", 1800, 100, 900) + glow("t", 100, 1000, 800)
    body += header("Suhbatlar va CRM", left=int(margin), top=40, right=int(margin))
    body += crop(kanban, (kx, ky, kw, kh), left=margin, top=top, scale=s, radius=14)
    # Kanban ostida: Dilnoza R. holat tarixi (mijoz kartasidan)
    hx = rd["history"]["x"] - 21
    hist = (hx, rd["history"]["y"] - 18, kw, 90)  # sarlavha + oxirgi holat o'zgarishi
    hist_top = top + kh * s + 22
    if hist_top + hist[3] * s <= h - bottom_margin:
        body += crop(dil, hist, left=margin, top=hist_top, scale=s, radius=14, frame=True)
    body += crop(conv, (cx, cy, cw, ch), left=margin + kw * s + gap, top=top, scale=s, radius=14, frame=True)
    return w, h, body, ""


def comp_analytics(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1920, 1080
    an = shots["analytics_full_1440"]
    r = regions["analytics_full_1440"]
    s, gap = 1.0, 18
    left_w = r["filters"]["w"] * s
    right_w = r["funnel"]["w"] * s
    x0 = (w - (left_w + gap + right_w)) / 2
    body = glow("a", 1820, 120, 900) + glow("t", 120, 1000, 800)
    body += header("Analitika", left=int(x0), top=40, right=int(x0))
    y0 = 124
    # Chap: sana/filtr paneli, chiziqli grafik, kanallar · manbalar · bronlar holati
    y = y0
    for key in ("filters", "trend"):
        body += crop(an, card_region(r[key]), left=x0, top=y, scale=s)
        y += r[key]["h"] * s + gap
    x = x0
    inner_gap = (r["sources"]["x"] - r["channels"]["x"] - r["channels"]["w"]) * s
    for key in ("channels", "sources", "statuses"):
        body += crop(an, card_region(r[key]), left=x, top=y, scale=s)
        x += r[key]["w"] * s + inner_gap
    # O'ng: konversiya KPI'lari, funnel va kurslar
    xr = x0 + left_w + gap
    y = y0
    body += crop(an, card_region(r["kpi_conversion"]), left=xr, top=y, scale=s)
    body += crop(an, card_region(r["kpi_ai_first"]), left=xr + right_w - r["kpi_ai_first"]["w"] * s, top=y, scale=s)
    y += r["kpi_conversion"]["h"] * s + gap
    for key in ("funnel", "courses"):
        body += crop(an, card_region(r[key]), left=xr, top=y, scale=s)
        y += r[key]["h"] * s + gap
    return w, h, body, ""


def comp_instagram(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1080, 1350
    mob = shots["dashboard_mobile_390"]
    web = shots["webchat_booking_mobile_390"]
    k = 1.2
    body = glow("a", 960, 160, 820) + glow("t", 100, 1250, 760)
    # Yuqori qism (~300px) keyingi matn uchun bo'sh qoldiriladi
    phone_w, gap, bottom = 410, 44, h - 56
    left1 = (w - 2 * phone_w - gap) / 2
    ph = phone_height(mob, phone_w)
    body += f"<div class='hdr' data-check style='left:{left1:.0f}px;right:{left1:.0f}px;top:{bottom - ph - 84:.0f}px;--k:{k}'><div class='brand'>{LOGO}<span>QabulFlow <b>AI</b></span></div><span class='spacer'></span>{demo_badge()}</div>"
    body += phone_with_shot(mob, left=left1, width=phone_w, bottom=bottom)
    body += phone_with_shot(web, left=left1 + phone_w + gap, width=phone_w, bottom=bottom)
    return w, h, body, ""


def comp_story(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1080, 1920
    web = shots["webchat_booking_mobile_390"]
    booking = shots["booking_drawer_webchat_1440"]
    rb = regions["booking_drawer_webchat_1440"]
    k = 1.3
    safe_top, margin = 250, 48  # yuqori/pastki 250px — Story xavfsiz bo'sh zonasi
    body = glow("a", 960, 380, 900) + glow("t", 120, 1540, 900)
    body += f"<div class='hdr' data-check style='left:{margin}px;right:{margin}px;top:{safe_top + 16}px;--k:{k}'><div class='brand'>{LOGO}<span>QabulFlow <b>AI</b></span></div><span class='spacer'></span>{demo_badge()}</div>"
    phone_w = 520
    phone_top = safe_top + 112
    body += phone_with_shot(web, left=margin, top=phone_top, width=phone_w)
    # Panel: o'sha bron yozuvi (sarlavha + Mijoz ... Vaqt qatorlari)
    d = rb["drawer"]
    reg = (d["x"] + 1, 0, d["w"] - 1, rb["row_kanal"]["y"] + rb["row_kanal"]["h"] + 2)
    s = 1.02
    card_w, card_h = reg[2] * s, reg[3] * s
    card_left = w - 36 - card_w
    # Karta telefon o'rtasiga (bron tasdig'i xabari sathiga) tekislanadi
    card_top = phone_top + phone_height(web, phone_w) / 2 - card_h / 2 + 40
    body += crop(booking, reg, left=card_left, top=card_top, scale=s, radius=16, frame=True, z=4)
    body += step("✓", "Panelda bron yozuvi", left=margin + phone_w + 28, top=card_top - 54, k=1.25)
    return w, h, body, ""


def comp_cover(shots: dict, regions: dict) -> tuple[int, int, str, str]:
    w, h = 1280, 769
    dash = shots["dashboard_1440"]
    web = shots["webchat_booking_mobile_390"]
    k = 1.05
    body = glow("a", 1180, 60, 700) + glow("t", 120, 720, 600)
    body += f"<div class='hdr' data-check style='left:52px;top:44px;right:52px;--k:{k}'><div class='brand'>{LOGO}<span>QabulFlow <b>AI</b></span></div><span class='sep'></span><span class='screen'>Panel va mijoz chati</span><span class='spacer'></span>{demo_badge()}</div>"
    s = 0.64
    body += crop(dash, (0, 0, 1440, 900), left=w - 52 - 1440 * s, top=128, scale=s, radius=16, frame=True)
    body += phone_with_shot(web, left=52, width=256, bottom=h - 30)
    return w, h, body, ""


# --------------------------------------------------------------------------- eksport va tekshiruv

CHECK_JS = """([W, H]) => {
  const problems = [];
  for (const img of document.images) {
    if (!img.complete || img.naturalWidth === 0) problems.push('rasm yuklanmadi: ' + img.src);
  }
  if (!document.fonts.check("16px InterShow")) problems.push('shrift yuklanmadi');
  for (const el of document.querySelectorAll('[data-check]')) {
    const r = el.getBoundingClientRect();
    if (r.left < -0.5 || r.top < -0.5 || r.right > W + 0.5 || r.bottom > H + 0.5)
      problems.push(`kadrdan chiqdi: ${el.className} (${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)})`);
  }
  for (const el of document.querySelectorAll('.brand span, .screen, .demo, .step')) {
    if (el.scrollWidth > el.clientWidth + 1) problems.push('matn kesildi: ' + el.textContent.trim());
  }
  return problems;
}"""


def build_all() -> list[tuple[str, int, int, str, str]]:
    names = [
        "dashboard_1440",
        "dashboard_full_1440",
        "analytics_full_1440",
        "conversation_operator_1440",
        "leads_kanban_1440",
        "booking_drawer_1440",
        "booking_drawer_webchat_1440",
        "lead_drawer_aziza_1440",
        "lead_drawer_history_1440",
        "webchat_booking_mobile_390",
        "dashboard_mobile_390",
    ]
    shots = {n: load_shot(n) for n in names}
    regions = load_regions()
    tg = json.loads((SHOTS / "telegram_demo_conversation.json").read_text(encoding="utf-8"))
    comps = [
        ("01-dashboard-desktop", comp_dashboard(shots, regions)),
        ("02-telegram-booking", comp_telegram(shots, regions, tg)),
        ("03-crm-conversations", comp_crm(shots, regions)),
        ("04-analytics-detail", comp_analytics(shots, regions)),
        ("05-instagram-portrait", comp_instagram(shots, regions)),
        ("06-story-vertical", comp_story(shots, regions)),
        ("07-portfolio-cover", comp_cover(shots, regions)),
    ]
    return [(name, w, h, body, css) for name, (w, h, body, css) in comps]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-html", action="store_true", help="HTML manbalarni showcase/build/ ga saqlash")
    parser.add_argument("--only", help="faqat shu nomdagi rasm (masalan 02-telegram-booking)")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="qf-showcase-"))
    expected = {}
    failures: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, w, h, body, css in build_all():
                if args.only and args.only != name:
                    continue
                k = 1.0
                src = work / f"{name}.html"
                src.write_text(page_html(w, h, body, k, css), encoding="utf-8")
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                page.goto(src.as_uri())
                page.evaluate("document.fonts.ready.then(() => true)")
                page.wait_for_function("() => [...document.images].every(i => i.complete)")
                removed = page.evaluate(FIT_TG_JS)
                problems = page.evaluate(CHECK_JS, [w, h])
                target = OUT / f"{name}.png"
                page.screenshot(path=str(target), clip={"x": 0, "y": 0, "width": w, "height": h}, animations="disabled")
                page.close()
                expected[name] = (w, h)
                note = f" (Telegram maketida sig'magan {removed} ta eski xabar yashirildi)" if removed else ""
                print(f"  {target.relative_to(ROOT)}  {w}×{h}{note}")
                failures += [f"{name}: {x}" for x in problems]
            browser.close()
        if args.keep_html:
            dest = Path(__file__).resolve().parent / "build"
            dest.mkdir(exist_ok=True)
            for f in work.glob("*.html"):
                shutil.copy(f, dest / f.name)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Yakuniy fayl tekshiruvi: ochiladi, o'lcham aniq, bo'sh emas
    for name, (w, h) in expected.items():
        path = OUT / f"{name}.png"
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if im.size != (w, h):
                failures.append(f"{name}: o'lcham {im.size}, kutilgan {(w, h)}")
            extrema = im.convert("L").getextrema()
            if extrema[1] - extrema[0] < 40:
                failures.append(f"{name}: rasm deyarli bir xil rangda (bo'sh?)")
    if failures:
        print("\nMUAMMOLAR:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"\nTayyor: {len(expected)} ta PNG tekshirildi (o'lcham, ochilish, rasm/shrift yuklanishi, kadr chegarasi).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
