# QabulFlow AI

O'quv markazlari uchun murojaatlarni qabul qilish va sinov darsiga yozish tizimi. Mijoz Telegram yoki
veb-chat orqali (matn yoki ovozli xabar) yozadi; AI agent faqat bazadagi kurs, narx, jadval va bo'sh
joy ma'lumotlari bilan javob beradi, mijoz tasdig'idan keyin haqiqiy sinov darsi bronini va CRM
yozuvini yaratadi. Administrator panelda mijozlar, suhbatlar, bronlar, kurslar, bilim bazasi va
statistikani boshqaradi.

- Backend: Python 3.13, Django 5.2 LTS, Django REST Framework, PostgreSQL, Celery + Redis, aiogram 3
- Panel va veb-chat: React 19 + TypeScript + Vite 7, Tailwind CSS 4, Recharts 3
- Testlar: pytest (backend), ESLint + `tsc` (frontend), Python Playwright (brauzer E2E va showcase PNG)
- Docker Compose: db, redis, migrate (+demo seed), web, worker, beat, bot (profil)

Batafsil: [ARCHITECTURE.md](ARCHITECTURE.md) · [METRICS.md](METRICS.md) · [TEST_REPORT.md](TEST_REPORT.md) ·
API sxemasi: [docs/openapi.yaml](docs/openapi.yaml) (ishlayotgan serverda `/api/docs/`).

---

## 1. Talablar

| Vosita | Versiya | Izoh |
| --- | --- | --- |
| Python | 3.13 (3.12+) | backend, testlar, showcase skriptlari |
| Node.js / npm | 22 LTS / 10 | faqat panelni build qilish uchun |
| PostgreSQL | 16+ | `pg_trgm` kengaytmasi migratsiyada yoqiladi |
| Redis | 7+ | Celery broker va kesh (minimal lokal rejimda shart emas, 3.3-bo'lim) |
| ffmpeg | ixtiyoriy | Telegram `.ogg` ovozli xabarini real STT uchun o'girish |
| Docker Desktop | ixtiyoriy | `docker compose` bilan butun muhit |

## 2. Docker orqali ishga tushirish

```bash
python scripts/init_env.py          # .env yaratadi (tasodifiy DJANGO_SECRET_KEY)
docker compose up --build -d        # db → redis → migrate (+demo seed) → web, worker, beat
docker compose ps                   # web "healthy" bo'lishini kuting
```

Panel: <http://localhost:8000>. Tartib `depends_on` + healthcheck orqali boshqariladi: `migrate`
servisi DB tayyor bo'lgach migratsiyani bajaradi va `DEMO_MODE=true` bo'lsa bo'sh bazaga demo
ma'lumot yozadi (`seed_demo --if-empty` — qayta ishga tushirishda ma'lumot o'chirilmaydi).
`web`, `worker`, `beat` faqat `migrate` muvaffaqiyatli tugagach ishga tushadi.

Telegram bot (token kiritilgandan va `DEMO_MODE=false` qilingandan keyin):

```bash
docker compose --profile telegram up -d bot
```

To'xtatish: `docker compose down` (ma'lumotlar `pgdata` volume'da qoladi; o'chirish: `docker compose down -v`).

> Docker Compose fayli `docker compose config` bilan tekshirilgan, lekin image build va konteynerlar
> ishlab chiqish muhitida ishga tushirilmagan (Docker Hub'ga kirish yopiq edi) — [TEST_REPORT.md](TEST_REPORT.md).

## 3. Docker'siz lokal ishga tushirish

### 3.1. PostgreSQL bazasi

```sql
-- psql -U postgres
CREATE USER qabulflow WITH PASSWORD 'qabulflow' CREATEDB;
CREATE DATABASE qabulflow OWNER qabulflow;
```

`CREATEDB` huquqi backend testlari test bazasini yaratishi uchun kerak. Boshqa nom/parol
ishlatsangiz, `.env` dagi `POSTGRES_*` qiymatlarini moslang.

### 3.2. Linux / macOS

```bash
make setup        # .venv, Python va Node bog'liqliklari, Playwright Chromium, .env
make frontend     # panel build: frontend/dist
make migrate
make seed         # demo ma'lumotlar (DEMO_MODE=true)
make run          # http://127.0.0.1:8000
# alohida terminallarda (eslatmalar, outbox, bilim bazasi fon vazifalari):
make worker
make beat
```

`make help` — barcha buyruqlar ro'yxati.

### 3.3. Windows (PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.lock
python -m playwright install chromium
cd frontend; npm ci; npm run build; cd ..
python scripts\init_env.py
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

Fon vazifalari (alohida oynalarda, `backend` papkasida, venv faollashtirilgan holda):

```powershell
python -m celery -A config worker -l info --pool=solo
python -m celery -A config beat -l info --schedule ..\var\celerybeat-schedule
```

**Redis'siz minimal rejim.** Redis o'rnatilmagan bo'lsa, `.env` da `USE_LOCMEM_CACHE=true` va
`CELERY_TASK_ALWAYS_EAGER=true` qiling: kesh jarayon xotirasida, outbox va bilim bazasini qayta
ishlash so'rov ichida bajariladi, worker/beat kerak bo'lmaydi. Bu rejimda eslatmalar vaqtida
yuborilmaydi (buning uchun Redis + `celery beat` kerak).

### 3.4. Frontend development rejimi

```bash
cd frontend && npm run dev     # http://127.0.0.1:5173, /api so'rovlari 8000-portga proxy qilinadi
```

## 4. Demo hisoblar

Faqat `DEMO_MODE=true` bo'lganda yaratiladi va ishlaydi (`DEMO_MODE=false` bo'lsa demo hisoblar
bilan kirish bloklanadi, `seed_demo` ishlamaydi).

| Rol | Email | Parol | Kirish doirasi |
| --- | --- | --- | --- |
| Egasi | `owner@demo.qabulflow.local` | `Demo12345!` | hamma narsa |
| Menejer | `manager@demo.qabulflow.local` | `Demo12345!` | kurslar, bilim bazasi, AI, analitika, eksport |
| Operator | `operator@demo.qabulflow.local` | `Demo12345!` | faqat Chilonzor filiali |
| Operator 2 | `operator2@demo.qabulflow.local` | `Demo12345!` | barcha filiallar |
| Izolyatsiya tashkiloti egasi | `owner@isolation.demo.qabulflow.local` | `Demo12345!` | boshqa tashkilot (izolyatsiya tekshiruvi) |

Demo seed: "QabulFlow Demo Academy", 2 filial, 4 kurs, 8 guruh, 90 kun oldindan 14 kun keyingacha
slotlar, 160 sintetik mijoz (suhbatlar, bronlar, bekor qilish, qatnashish, o'qishga yozilish),
uz/ru/en bilim bazasi hujjatlari va ikkinchi (izolyatsiya) tashkilot. Seed belgilangan `--seed`
(standart 42) bilan qayta tiklanadi va qayta ishga tushganda dublikat yaratmaydi.
Uchta suhbat haqiqiy service qatlami orqali o'tkaziladi: Telegram orqali bron, rus tilidagi
veb-chat va operatorga o'tkazilgan suhbat.

Mijoz tomoni:

- Veb-chat (alohida sahifa): <http://127.0.0.1:8000/chat/wk_demo_academy>
- Vidjet o'rnatilgan demo sayt: <http://127.0.0.1:8000/demo-site/>
- Vidjet kodi: `<script src="http://127.0.0.1:8000/widget.js" data-key="wk_demo_academy" async></script>`

## 5. Kalitsiz demo rejimi nima qiladi

- **AI:** `AI_PROVIDER=demo` — deterministik dialog. U haqiqiy LLM emas, lekin xuddi shu tool'lar
  (kurs qidirish, bo'sh joy, lead, bron, bekor qilish, operatorga o'tkazish) va bir xil bron
  qoidalari orqali ishlaydi. Suhbatlarda «Demo AI» deb belgilanadi.
- **Ovoz:** `STT_PROVIDER=demo` — ovozli xabar qabul qilinadi, hajm/davomiylik tekshiriladi, lekin
  transkript haqiqiy emas va «Demo transkript» deb belgilanadi; past ishonchli transkriptdan bron yaratilmaydi.
- **Telegram:** token bo'lmasa yoki `DEMO_MODE=true` bo'lsa tashqi xabarlar `demo` holatida
  outbox'da qoladi (panel → Integratsiyalar → «Tashqi xabarlar navbati (outbox)»). Real foydalanuvchiga hech narsa yuborilmaydi.
- Integratsiyalar sahifasi haqiqiy holatni ko'rsatadi: «Sozlanmagan», «Demo rejim», «Sozlangan, tekshirilmagan», «Ulangan» yoki «Xato».

## 6. Real integratsiyalarni yoqish

`.env` faylida (o'zgartirgandan keyin web, worker, beat va botni qayta ishga tushiring):

**AI (Anthropic yoki OpenAI):**

```env
AI_PROVIDER=anthropic          # yoki openai
AI_MODEL=claude-haiku-5-5      # misol; provayder hujjatidagi amaldagi model nomini yozing
ANTHROPIC_API_KEY=...          # yoki OPENAI_API_KEY=...
```

Model nomi kodda qattiq yozilmagan. Panel → Integratsiyalar → AI kartasidagi «Ulanishni tekshirish» kalit va
model mavjudligini provayder API orqali tekshiradi. Timeout, cheklangan retry, javob token limiti va
suhbat bo'yicha kunlik token budjeti `.env` da sozlanadi (`AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`,
`AI_MAX_OUTPUT_TOKENS`, `AI_DAILY_TOKEN_BUDGET_PER_CONVERSATION`).

**Ovozli xabar (OpenAI STT):**

```env
STT_PROVIDER=openai
STT_MODEL=whisper-1
OPENAI_API_KEY=...
```

Telegram `.ogg` fayllari uchun serverda `ffmpeg` bo'lishi kerak (Docker image'da bor).

**Telegram bot:**

```env
DEMO_MODE=false
TELEGRAM_BOT_TOKEN=123456:ABC...   # @BotFather
TELEGRAM_ORGANIZATION_SLUG=demo-academy
```

- Development (long polling): `python manage.py run_telegram_bot` (yoki `docker compose --profile telegram up -d bot`).
- Production (webhook, HTTPS kerak): `TELEGRAM_MODE=webhook`, `TELEGRAM_WEBHOOK_BASE_URL=https://...`,
  `TELEGRAM_WEBHOOK_SECRET` va `TELEGRAM_WEBHOOK_PATH_TOKEN` (tasodifiy qatorlar), so'ng
  `python manage.py set_telegram_webhook`. Polling va webhook bir vaqtda ishlatilmaydi — buyruqlar buni tekshiradi.

`DEMO_MODE=false` bo'lganda demo hisoblar bilan kirib bo'lmaydi: haqiqiy egasi hisobini
`python manage.py createsuperuser` va Django admin (`/django-admin/`) orqali yarating hamda
tashkilot va a'zolik qo'shing yoki demo bazasiz alohida muhit tayyorlang.

**Production eslatmalari:** `DJANGO_ENV=production` (DEBUG o'chiq, maxfiy kalit va `DJANGO_ALLOWED_HOSTS`
majburiy), HTTPS reverse-proxy ortida `DJANGO_SECURE_SSL_REDIRECT=true`, `DJANGO_SECURE_COOKIES=true`,
`DJANGO_HSTS_SECONDS=31536000`, aniq `DJANGO_CSRF_TRUSTED_ORIGINS` va `CORS_ALLOWED_ORIGINS`.

## 7. Testlar

```bash
make test-backend      # cd backend && python -m pytest          (PostgreSQL kerak, Redis kerak emas)
make test-frontend     # npm run lint && npm run typecheck && npm run build
make e2e               # server ishlab turgan va seed qilingan bo'lishi kerak
```

Windows: `cd backend; python -m pytest` · `cd frontend; npm run lint; npm run typecheck; npm run build` ·
`$env:E2E_BASE_URL="http://127.0.0.1:8000"; python -m pytest e2e`.

Testlar hech qachon real AI/Telegram API'ga murojaat qilmaydi (test sozlamalari kalitlarni bo'shatadi).
Natijalar: [TEST_REPORT.md](TEST_REPORT.md).

## 8. Showcase rasmlari

`assets/screenshots/` — ishlayotgan ilovadan olingan asl ekranlar, `assets/showcase/` — 7 ta
yakuniy PNG kompozitsiya (HTML/CSS + Playwright). Qayta yaratish (server `DEMO_MODE=true` bilan ishlab turganda):

```bash
python showcase/render_all.py --base-url http://127.0.0.1:8000 --reseed   # yoki: make showcase
```

Skript demo ma'lumotni qayta yaratadi, ekranlarni oladi, kompozitsiyalarni aniq o'lchamda
eksport qiladi va har bir PNG ning o'lchami, ochilishi, rasm/shrift yuklanishi va kadrdan
chiqmaganini tekshiradi. Telegram uslubidagi rasm ilovaning demo oqimidagi haqiqiy xabarlardan
kod orqali chizilgan maket va "Demo maket" deb belgilangan — u real Telegram integratsiyasi sinovi emas.

## 9. API

- OpenAPI 3: `docs/openapi.yaml` (`make openapi` / `python manage.py export_openapi`), Swagger UI: `/api/docs/`.
- Autentifikatsiya: sessiya cookie + CSRF (`GET /api/auth/csrf/` → `X-CSRFToken` header).
- Xatolar: `{"error": {"code": "...", "message": "...", "fields": {...}}}`.
- Public veb-chat API: `/api/public/widget/<public_key>/...` (rate limit, sessiya tokeni).

## 10. Loyiha tuzilmasi

```
backend/            Django loyiha (config/) va modullar (apps/*), testlar (tests/), Dockerfile
frontend/           React + TypeScript panel va veb-chat
e2e/                Python Playwright brauzer testlari
showcase/           Ekran olish va PNG kompozitsiya skriptlari (+ Inter shrifti, OFL)
assets/             screenshots/ (asl ekranlar), showcase/ (7 ta tayyor PNG)
docs/openapi.yaml   API sxemasi
scripts/            init_env.py (.env), make_zip.py (topshirish arxivi)
docker-compose.yml, Makefile, .env.example
```

## 11. Cheklovlar

- Real Anthropic/OpenAI, OpenAI STT va Telegram Bot API kalitlar bilan sinab ko'rilmagan:
  adapterlar SDK/HTTP so'rovlari mock qilingan testlar bilan tekshirilgan.
- Docker image build va `docker compose up` ishlab chiqish muhitida bajarilmagan (registry yopiq);
  xuddi shu buyruqlar (gunicorn, celery, migrate, collectstatic) Docker'siz tekshirilgan.
- To'lov tizimi, telefon qo'ng'iroqlari, Instagram DM va SaaS billing doiradan tashqarida.
- Bilim bazasi qidiruvi PostgreSQL full-text + trigram (vektor qidiruv yo'q); skaner PDF'dan matn olinmaydi (OCR yo'q).
