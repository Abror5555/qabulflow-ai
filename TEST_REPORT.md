# QabulFlow AI — test hisoboti

Sana: 2026-10-24 (Asia/Tashkent). Bu hujjatda faqat **haqiqatda bajarilgan** tekshiruvlar va
ularning natijalari yozilgan. Bajarilmagan yoki real xizmatda sinalmagan qismlar 9-bo'limda alohida.

## Muhit

| Komponent | Versiya |
| --- | --- |
| OS | Linux (bulutdagi izolyatsiyalangan konteyner) |
| Python | 3.13.17 |
| Node.js / npm | 22.23.4 / 10.9.9 |
| PostgreSQL | 16.15 |
| Redis | 7.0.15 |
| Brauzer | Chromium (Python Playwright 1.63.0) |
| Docker CLI / Compose | 29.9.2 / v5.6.1 (daemon ishga tushdi, lekin Docker Hub yopiq — 8-bo'lim) |

## 1. Backend avtomatik testlari

```
cd backend && python -m pytest
86 passed in 14.10s
```

| Fayl | Testlar | Talab (prompt 11-bo'lim) |
| --- | :-: | --- |
| `test_auth_permissions.py` | 12 | 1 — login, CSRF, rollar, oxirgi egani pasaytirmaslik, ID orqali boshqa tashkilot yozuvi/fayli/statistikasiga kira olmaslik, filial cheklovi, Kanban/summary hisoblari |
| `test_booking_flow.py` | 13 | 2 — kurs/jadvaldan mijoz tasdig'i bilan bron (service va demo agent orqali), tasdiqsiz bron yo'q, noto'g'ri/o'tgan/to'lgan slot, takroriy bron, idempotency, ko'p o'rinli slot, begona bron egaligi |
| `test_concurrency.py` | 4 | 3 — oxirgi joyga parallel so'rovlar, ko'p o'rinli slot parallel, bir xil idempotency kaliti parallel, bir mijoz kalitsiz parallel (haqiqiy thread'lar, `select_for_update` + constraint) |
| `test_reschedule_cancel_reminders.py` | 10 | 4 — atomar ko'chirish, to'lgan/o'tgan slotga ko'chirish eski bronni saqlashi, bekor qilish joyni bo'shatishi va eslatmani bekor qilishi, bekor qilingandan keyin eslatma yuborilmasligi, roziliksiz eslatma yo'q, qatnashishni faqat dars boshlangach belgilash, API |
| `test_handoff.py` | 5 | 5 — operator olgandan keyin AI javob bermasligi va qaytarilgach davom etishi, operator javobi faqat olgandan keyin, mijoz so'rovi bilan handoff va bildirishnoma, Telegram operator javobi demo outbox'ga |
| `test_analytics.py` | 9 | 6 — tashkilot zonasidagi davr chegaralari, nol qiymat va "oldingi davrda ma'lumot yo'q", konversiya kohortasi, yangi bron birinchi tasdiq bo'yicha va bekor qilish alohida, AI/operator birinchi javob aralashmasligi, funnel noyob lead'lar, filtrlar KPI/grafik/CSV/drill-down'ga bir xil, hafta bucket'lari, noto'g'ri filtrlar |
| `test_ai_safety.py` | 10 | 7 — o'ylab topilgan narx/chegirma bloklanishi, tool natijasidagi narx ruxsat, tool muvaffaqiyatisiz "yozildingiz" bloklanishi, bitta navbatda ikki chaqiruv tasdiqni chetlab o'tmasligi, begona ID'lar, o'qituvchi/boshqa mijoz ma'lumoti chiqmasligi, ichki hujjat mijozga chiqmasligi, prompt-injection qatorlari, noma'lum kursda uydirmaslik |
| `test_provider_errors.py` | 9 | 8 — AI xatosida mijoz xabari saqlanib tushunarli javob, kalit yo'q bo'lsa yashirincha demo'ga o'tmaslik, STT xatosida ovozli xabar saqlanishi, past ishonchli transkriptda bron yo'q, demo transkript belgisi, audio hajm/davomiylik/format limiti, Anthropic va OpenAI adapterlarining tool sikli (SDK mijozlari mock), kalit+model talabi |
| `test_telegram_webchat_knowledge.py` | 14 | Telegram `/start`, matn, takroriy update, til callback, guruh chatini e'tiborsiz qoldirish, kanallar ism bo'yicha birlashmasligi, webhook (polling rejimida o'chiq, noto'g'ri secret), veb-chat sessiya/xabar/poll, token vidjetga bog'liqligi, Origin allowlist, bilim bazasi (yuklash, indekslash, qidiruv, skaner PDF), yuklash validatsiyasi, seed idempotentligi, DEMO_MODE'siz seed rad etilishi, `--if-empty` va seed determinizmi |

Testlar real AI/Telegram API'ga murojaat qilmaydi: `config/test_settings.py` provayderlarni `demo` ga,
kalitlarni bo'sh qiymatga o'rnatadi; adapter testlari SDK mijozlarini mock qiladi.

## 2. Statik tekshiruvlar va build

| Buyruq | Natija |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 140 files already formatted |
| `cd frontend && npm run lint` (ESLint, `--max-warnings=0`) | exit 0 |
| `npm run typecheck` (`tsc -b --noEmit`) | exit 0 |
| `npm run build` (`tsc -b && vite build`) | exit 0, build tayyor |
| `python manage.py export_openapi` (`spectacular --validate`) | 0 xato, 0 ogohlantirish; 72 path, 107 operatsiya → `docs/openapi.yaml` |
| `python manage.py check --deploy` (production, HTTPS sozlamalari bilan) | faqat lokal http uchun ataylab o'chirilgan `.env` qiymatlari bo'yicha 4 ta security ogohlantirishi (W004/W008/W012/W016); production qiymatlari README 6-bo'limda |

## 3. Brauzer E2E (Python Playwright, Chromium)

```
E2E_BASE_URL=http://127.0.0.1:8000 python -m pytest e2e -v
10 passed in 84.37s
```

| Test | Nima tekshiriladi |
| --- | --- |
| `test_login_dashboard_filter_and_chart` | login, sana/filial filtri KPI va grafikni yangilashi, grafik nuqtasidan drill-down |
| `test_lead_create_status_and_details` | mijoz yaratish, holatni o'zgartirish, kartani ochish, eslatma |
| `test_webchat_booking_appears_in_panel_and_operator_reply` | veb-chatda kurs tanlash → tasdiq → bron; bron panelda ko'rinishi; operator suhbatni olishi va javob berishi |
| `test_mobile_navigation_and_actions` | 390 px: mobil menyu, navigatsiya, asosiy amallar |
| `test_tablet_collapsed_sidebar` | 1024 px: yig'iladigan sidebar |
| `test_operator_cannot_open_analytics` | operator roli uchun cheklangan sahifa/amal |
| `test_pages_fit_viewport[1440-900]`, `[1024-768]`, `[390-844]` | 10 ta sahifada gorizontal overflow yo'qligi, sarlavha, konsol xatolari yo'qligi; har sahifa skrinshoti `e2e/artifacts/` |
| `test_webchat_mobile_fits` | 390 px veb-chat sahifasi |

Skrinshotlar ko'zdan kechirildi (1440/1024/390). Shu sessiyada topilib tuzatilgan UI xatolari:
Kanban ustunlarida hisob har doim 1 ko'rinishi (backend GROUP BY xatosi — regressiya testi qo'shildi),
"22 daq 18 s" KPI qiymatining ikki qatorga bo'linishi, mobil qidiruv placeholder'ining kesilishi.

## 4. Yangi nusxadan ishga tushirish (README buyruqlari)

Arxiv (`scripts/make_zip.py`) bo'sh papkaga ochildi va README 3.2-bo'lim buyruqlari alohida
`qabulflow_fresh` bazasi bilan bajarildi:

| Qadam | Natija |
| --- | --- |
| `python3 -m venv .venv` + `pip install -r backend/requirements-dev.lock` | OK (birinchi urinishda dev lock runtime paketlarisiz edi — **tuzatildi**: `requirements-dev.in` endi `-r requirements.in`; universal lock) |
| `cd frontend && npm ci` | 228 paket, OK |
| `python scripts/init_env.py` | `.env` tasodifiy `DJANGO_SECRET_KEY` bilan yaratildi |
| `make frontend` / `make migrate` / `make seed` | OK (barcha migratsiyalar, demo ma'lumotlar) |
| `make test-backend` | 86 passed |
| `make test-frontend` | lint, typecheck, build OK |
| `make lint` | birinchi urinishda 1 fayl formatlanmagan edi — **tuzatildi**, qayta tekshirildi |
| `runserver 127.0.0.1:8001` + `make e2e BASE_URL=http://127.0.0.1:8001` | health OK, **10 passed** |

`playwright install chromium` muhitda oldindan o'rnatilgan brauzer sabab ishga tushirilmadi.

## 5. Docker konteyner buyruqlarini Docker'siz takrorlash (production rejimi)

`DJANGO_ENV=production` va `docker-compose.yml` dagi qiymatlar bilan yangi nusxada:

| Buyruq (konteynerdagi kabi) | Natija |
| --- | --- |
| `manage.py collectstatic --noinput` | 155 fayl, whitenoise siqilgan storage |
| `manage.py migrate --noinput` + `seed_demo --if-empty` | migratsiya yo'q; mavjud demo ma'lumot saqlandi ("o'tkazib yuborildi") |
| `gunicorn config.wsgi:application --bind ... --workers 2` | `/api/health/` → `{"status": "ok", database ok, cache ok}` |
| SPA `/`, `/assets/index-*.js`, `/widget.js`, `/static/admin/css/base.css` | 200, to'g'ri content-type |
| `/api/nonexistent/` | umumiy 404 sahifa, debug ma'lumoti yo'q |
| CSRF + login (http, `DJANGO_SECURE_COOKIES=false`) → `/api/analytics/overview/` | owner sifatida kirildi, KPI qaytdi |
| `celery -A config worker` / `celery -A config beat --schedule ...` | worker Redis'ga ulandi, beat ishga tushdi |

## 6. Redis'siz minimal lokal rejim

`USE_LOCMEM_CACHE=true`, `CELERY_TASK_ALWAYS_EAGER=true`, Redis manzili ataylab yopiq portga:
health OK; veb-chat sessiya va xabar → AI javobi (kurs narxi bazadan); bilim bazasiga TXT yuklash
so'rov ichida `indexed` holatiga o'tdi.

## 7. Demo seed va showcase

- `seed_demo`: 160 mijoz, 90 kun; qayta ishga tushirishda dublikat yo'q (test).
  Determinizm: seed "hozirgi vaqt"ni 0, −25 va −180 daqiqaga surib uch marta bajarildi — mijozlar,
  holatlar va bronlar soni bir xil (160 / 24 `trial_booked` / 90). Har mijoz alohida tasodifiy oqimga
  ega bo'lishi uchun seed shu sessiyada tuzatildi.
- `python showcase/render_all.py --base-url http://127.0.0.1:8000 --reseed` — seed → 14 ta asl ekran
  (`assets/screenshots/`) → 7 ta PNG (`assets/showcase/`). Skript har PNG ni Pillow bilan ochib o'lchamini,
  rasm va shrift yuklanganini, elementlar kadrdan chiqmaganini tekshirdi:

| Fayl | O'lcham |
| --- | --- |
| `01-dashboard-desktop.png` | 1920 × 1080 |
| `02-telegram-booking.png` | 1600 × 1200 |
| `03-crm-conversations.png` | 1920 × 1080 |
| `04-analytics-detail.png` | 1920 × 1080 |
| `05-instagram-portrait.png` | 1080 × 1350 |
| `06-story-vertical.png` | 1080 × 1920 |
| `07-portfolio-cover.png` | 1280 × 769 |

Barcha 7 rasm ko'zdan kechirildi: matn o'qiladi, kesilgan/ustma-ust element yo'q, statistikali
rasmlarda "Demo ma'lumotlar" belgisi bor, Telegram uslubidagi maketda "Demo maket" belgisi bor,
real telefon/kalit/token/login yo'q (telefonlar sintetik `+998 00 ...`).

## 8. Docker

- `docker compose config` — fayl to'g'ri: 7 servis (`bot` — `telegram` profili), `migrate` →
  `db`/`redis` `service_healthy`; `web` → `db`, `redis` healthy + `migrate`
  `service_completed_successfully`; `worker`/`beat` → `migrate` completed. `DJANGO_SECRET_KEY`
  bo'lmasa compose tushunarli xato bilan to'xtaydi (tekshirildi).
- **Image build va `docker compose up` bajarilmadi**: Docker daemon ishga tushdi, lekin base image
  yuklab olish `registry-1.docker.io` uchun 403 (muhit tarmoq siyosati) bilan rad etildi. Dockerfile'dagi
  buyruqlar 5-bo'limda Docker'siz tekshirilgan, lekin image'ning o'zi va healthcheck'lar konteynerda sinalmagan.

## 9. Bajarilmagan / real xizmatda sinalmagan

| Qism | Holat |
| --- | --- |
| Anthropic Messages API (real kalit bilan) | sinalmagan — adapter mock qilingan SDK bilan testlangan |
| OpenAI Chat API (real kalit bilan) | sinalmagan — adapter mock bilan testlangan |
| OpenAI speech-to-text (`whisper-1` va b.) | sinalmagan — xato/limit yo'llari testlangan |
| Telegram Bot API: polling, webhook o'rnatish, `getMe`, xabar/ovoz yuborish va yuklab olish | sinalmagan — processor, dedup, webhook secret va outbox mantig'i testlangan; real bot token yo'q |
| ffmpeg orqali Telegram `.ogg` → STT formati | real faylda sinalmagan |
| Docker image build, konteynerlarda ishga tushirish | sinalmagan (8-bo'lim) |
| Windows'da Docker'siz ishga tushirish (README 3.3) | sinalmagan — buyruqlar Linux'da tekshirilgan, Windows'ga moslab yozilgan |
| Brauzerda mikrofon orqali ovozli xabar yozish (MediaRecorder) | avtomatik sinalmagan — ovoz API endpointi backend testlarida tekshirilgan |
| Firefox/Safari | sinalmagan (faqat Chromium) |
| HTTPS ortida production cookie/HSTS bilan real deploy | sinalmagan (topshiriq doirasida deploy yo'q) |
