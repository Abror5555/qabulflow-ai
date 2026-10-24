# QabulFlow AI — arxitektura

Django asosidagi modular monolith. Biznes qoidalari har bir modulning `services.py` faylida; REST
view, Telegram handler, veb-chat API, AI tool'lari va demo seed shu service funksiyalarini chaqiradi.
Bron qoidasi bitta joyda (`apps/bookings/services.py`) yozilgan va kanallar bo'yicha takrorlanmaydi.

```
            Telegram (aiogram)          Veb-chat vidjeti / /chat/<key>          Panel (React SPA)
                   │                               │                                  │
     integrations/telegram/processor     integrations/webchat.py (public API)    DRF ViewSet'lar
                   └──────────────┬────────────────┘                                  │
                                  ▼                                                   │
                 conversations/inbound.py  ── record_customer_message (dedup)         │
                                  │                                                   │
                     handoff kalit so'zlari? ──ha──► request_handoff (AI to'xtaydi)   │
                                  │ yo'q                                              │
                                  ▼                                                   │
                ai_agent/engine.AgentRunner ── provider (demo | anthropic | openai)    │
                                  │  tool chaqiruvlari (validatsiya, tenant konteksti) │
                                  ▼                                                   ▼
        ai_agent/tools.ToolExecutor ──► courses / knowledge / leads / bookings services ◄──
                                  │
                       guards.py (chiqish tekshiruvi) ──► add_outbound_message ──► outbox (Celery)
```

## Modullar (`backend/apps/`)

| Modul | Vazifa | Asosiy modellar |
| --- | --- | --- |
| `core` | tenant middleware, ruxsat klasslari, xato formati, audit, health, SPA/vidjet, `seed_demo` | `AuditEvent` |
| `accounts` | email bilan login, sessiya, profil, parol, demo hisob bloki | `User` |
| `organizations` | tashkilot, filial, a'zolik va rol, jamoa, vidjet sozlamalari | `Organization`, `Branch`, `Membership`, `WidgetSettings` |
| `courses` | kurs (narx, valyuta), guruh (filial, o'qituvchi, jadval, sig'im), sinov slotlari | `Course`, `Group`, `TrialSlot` |
| `leads` | CRM: mijoz, manba, mas'ul, eslatmalar, holat tarixi, o'qishga yozilish | `Lead`, `LeadNote`, `LeadStatusChange` |
| `conversations` | kanal suhbatlari, xabarlar, ovozli fayllar, operatorga o'tkazish | `Conversation`, `Message`, `Attachment`, `HumanHandoff` |
| `bookings` | sinov darsi broni, ko'chirish, bekor qilish, qatnashish, enrollment | `TrialBooking`, `BookingEvent`, `Enrollment` |
| `knowledge` | PDF/TXT/MD yuklash, matn ajratish, chunklash, FTS + trigram qidiruv | `KnowledgeDocument`, `KnowledgeChunk` |
| `ai_agent` | provayder adapterlari, tool'lar, NLU, guard'lar, STT, AI sozlamalari, chaqiruv logi | `AISettings`, `AICallLog` |
| `analytics` | KPI, sparkline, grafiklar, funnel, drill-down, CSV ([METRICS.md](METRICS.md)) | — |
| `notifications` | eslatmalar, panel bildirishnomalari, tashqi xabarlar navbati (outbox) | `Reminder`, `Notification`, `OutboxMessage` |
| `integrations` | Telegram bot/webhook, public veb-chat API, integratsiya holati | `IntegrationStatus`, `ProcessedTelegramUpdate` |

Vaqt UTC'da saqlanadi; ko'rsatish va analitika kun chegaralari tashkilot zonasida (standart `Asia/Tashkent`).

## Asosiy ma'lumot oqimi: murojaatdan bron va CRM yozuvigacha

1. **Qabul.** Telegram update yoki veb-chat xabari `inbound.process_text` / `process_voice` ga keladi.
   Suhbat tashkilot va kanal identifikatori (Telegram `chat_id`, veb-chat `visitor_id`) bo'yicha topiladi
   yoki yaratiladi. Lead faqat shu kanal identifikatori bo'yicha bog'lanadi — bir xil ism yoki
   tasdiqlanmagan telefon bo'yicha avtomatik birlashtirilmaydi. Telegram `update_id` va xabar
   `external_id` bo'yicha takroriy yetkazish e'tiborsiz qoldiriladi (`ProcessedTelegramUpdate`, unique constraint).
2. **Ovoz.** Hajm va davomiylik (`AUDIO_MAX_BYTES`, `AUDIO_MAX_SECONDS`) tekshiriladi, fayl `Attachment`
   sifatida saqlanadi, STT adapteri transkript qaytaradi. Provayder xatosida yoki past ishonchda xabar
   saqlanadi, mijozdan matn yozish so'raladi, bron yaratilmaydi.
3. **Operator rejimi.** Suhbat `human` rejimida bo'lsa yoki mijoz administrator so'rasa (deterministik
   kalit so'zlar), AI chaqirilmaydi; operatorga bildirishnoma ketadi. AI'ga qaytarish — alohida amal.
4. **AI navbati.** `AgentRunner` tarixni (oxirgi `AI_HISTORY_MESSAGES`) va tool ro'yxatini provayderga
   beradi, tool chaqiruvlarini `ToolExecutor` orqali bajaradi (`AI_MAX_TOOL_ITERATIONS` gacha), timeout,
   retry va suhbat bo'yicha kunlik token budjetini qo'llaydi, har chaqiruvni `AICallLog` ga yozadi
   (kalitlar va to'liq matnlar logga tushmaydi).
5. **Bron.** `create_trial_booking` ikki bosqichli: birinchi chaqiruv `confirmation_required` va xulosa
   qaytaradi va holatga `pending_booking = {slot_id, after_message_id}` yoziladi; bron faqat **keyingi**
   mijoz xabari aniq tasdiq (`Ha / Да / Yes`) bo'lsa yaratiladi. Shundan keyin
   `bookings.services.create_trial_booking` chaqiriladi.
6. **Natija.** Bron, `BookingEvent`, lead holati (`trial_booked`) va `LeadStatusChange`, audit,
   administrator bildirishnomasi bitta tranzaksiyada yoziladi. Mijoz roziligi bo'lsa eslatma (`Reminder`)
   rejalashtiriladi; Celery beat `dispatch_due_reminders` bekor qilingan bron uchun eslatma yubormaydi.
7. **Javob.** Chiqish `guards.py` dan o'tadi va `OutboxMessage` orqali kanalga yuboriladi (idempotent,
   retry, xato holati saqlanadi). `DEMO_MODE` yoki token yo'q bo'lsa outbox elementi `demo` holatida qoladi.

## Bron ishonchliligi (`apps/bookings/services.py`)

- Slot qatori `select_for_update()` bilan qulflanadi; band joylar shu tranzaksiyada qayta hisoblanadi.
- DB darajasida: `CHECK (seats_taken <= capacity)`, `UNIQUE (slot, lead) WHERE status <> 'cancelled'`,
  `UNIQUE (organization, idempotency_key)`. Idempotency kaliti qulfdan keyin qayta tekshiriladi:
  retry yoki parallel takror so'rov yangi bron yaratmaydi, mavjud bronni qaytaradi.
- O'tgan vaqt, faol bo'lmagan kurs/guruh, bekor qilingan yoki to'lgan slotga bron yaratilmaydi.
- Ko'p o'rinli slotga sig'im to'lguncha turli mijozlar yoziladi.
- Ko'chirish atomar: ikkala slot id tartibida qulflanadi; yangi joy olinmasa eski bron o'zgarmaydi.
- Bekor qilishda kutilayotgan eslatmalar bekor qilinadi va voqea alohida saqlanadi (`cancelled_at`).

## Ruxsatlar va tenant izolyatsiyasi

- `TenantMiddleware` sessiyadagi `active_org_id` bo'yicha foydalanuvchining `Membership` ini topadi.
  Tashkilot, rol va filial cheklovi faqat server tomonidagi autentifikatsiyadan olinadi — so'rov
  tanasidagi yoki AI tool argumentlaridagi `organization_id` ishlatilmaydi.
- Har bir queryset `OrganizationScopedMixin` orqali faol tashkilot bilan filtrlanadi; boshqa tashkilot
  obyekti ID'si 404 qaytaradi (yozuv, fayl yuklab olish va statistika uchun testlangan).
- Filial cheklovi: operatorga filiallar biriktirilgan bo'lsa, u faqat shu filiallar va filiali
  ko'rsatilmagan yozuvlarni ko'radi; bo'sh ro'yxat — barcha filiallar. Egasi har doim hammasini ko'radi.

| Amal | Egasi | Menejer | Operator |
| --- | :-: | :-: | :-: |
| Mijozlar, suhbatlar, operator javobi, sinov darslari (yaratish/ko'chirish/bekor/qatnashish) | ✓ | ✓ | ✓ (filial doirasida) |
| Kurslar, guruhlar, slotlar, filiallar, bilim bazasi, AI sozlamalari | ✓ | ✓ | ko'rish |
| Umumiy ko'rinish (dashboard KPI va grafiklar) | ✓ | ✓ | ✓ (filial doirasida) |
| Analitika sahifasi, CSV eksport, o'qishga yozilganini tasdiqlash, outbox, AI xarajati | ✓ | ✓ | — |
| Jamoa (taklif, rol, filial), vidjet, tashkilot sozlamalari | ✓ | ko'rish | — |
| Integratsiyalarni tekshirish (Telegram/AI) | ✓ | ko'rish | — |

Xavfsizlik: sessiya cookie `HttpOnly` + `SameSite=Lax`, CSRF majburiy, production'da `Secure`
cookie, HSTS, SSL redirect, `DEBUG=False`, majburiy `SECRET_KEY` va `ALLOWED_HOSTS`; login, veb-chat
va webhook uchun rate limit; fayllar `MEDIA_ROOT` da public URL'siz saqlanib faqat ruxsatli endpoint
orqali beriladi; yuklashlarda tur/hajm tekshiruvi; loglarda kalit va telefonlar maskalanadi (`core/logging.py`).

## AI agent va tool chegaralari (`apps/ai_agent/`)

Provayder, model va kalit `.env` dan (`AI_PROVIDER`, `AI_MODEL`, `*_API_KEY`); model nomi kodda yo'q.
Adapterlar rasmiy `anthropic` va `openai` Python SDK'laridan foydalanadi. `demo` provayder —
deterministik dialog, xuddi shu tool'larni chaqiradi va javoblari `is_demo` bilan belgilanadi.

| Tool | Nima qiladi | Chegaralar |
| --- | --- | --- |
| `search_knowledge` | bilim bazasidan parchalar | faqat `customer` ko'rinishdagi hujjatlar; ko'rsatmaga o'xshash qatorlar olib tashlanadi |
| `list_courses`, `get_course_details`, `list_branches` | kurs, narx, guruh jadvali, filial | faqat faol yozuvlar; o'qituvchi va boshqa mijoz ma'lumoti qaytarilmaydi |
| `check_trial_availability` | bo'sh slotlar va qolgan joy | real vaqtda DB'dan; o'tgan/to'lgan slotlar chiqmaydi |
| `create_lead`, `update_lead` | joriy suhbat mijozini yaratish/yangilash | faqat ruxsat etilgan maydonlar; telefon normallashtiriladi |
| `create_trial_booking` | bron | ikki bosqichli tasdiq, service qatlamidagi barcha tekshiruvlar, idempotency kaliti |
| `list_my_bookings`, `cancel_trial_booking` | mijozning o'z bronlari | faqat shu lead'ga tegishli bron; bekor qilish ham tasdiq talab qiladi |
| `request_human_handoff` | operatorga o'tkazish | suhbat `human` rejimiga o'tadi, AI to'xtaydi |

Tool kontekstidagi tashkilot, suhbat va lead serverda aniqlanadi; model argumentidagi boshqa ID'lar
shu kontekst bo'yicha tekshiriladi. Chiqish tekshiruvlari (`guards.py`): muvaffaqiyatli bron/bekor
qilish tool natijasi bo'lmasa "yozildingiz/bekor qilindi" kabi da'volar xavfsiz javob bilan
almashtiriladi; tool natijalarida bo'lmagan pulga o'xshash raqamlar (narx, chegirma) bloklanadi.
Bilim bazasidagi hujjat matni tizim ko'rsatmasi sifatida bajarilmaydi (prompt'da ma'lumot sifatida
ajratiladi va sanitizatsiya qilinadi). AI sozlamalari sahifasi salomlashuv, tillar, ish vaqti va
handoff qoidalarini o'zgartiradi, lekin bu qoidalarni o'chirib qo'yadigan sozlama yo'q.

## Telegram va veb-chat

- `integrations/telegram/processor.py` — kanal mantig'i (aiogram'dan mustaqil, test qilinadi):
  `/start` (til tanlash, maxfiylik izohi, asosiy tugmalar), matn, ovoz, til almashtirish, update dedup.
- `bot.py` — aiogram 3 dispatcher; polling (`run_telegram_bot`) yoki himoyalangan webhook
  (`/api/integrations/telegram/webhook/<path_token>/` + `X-Telegram-Bot-Api-Secret-Token`). Ikkalasi bir vaqtda ishlatilmaydi.
- Veb-chat: `widget.js` (sayt uchun vidjet, iframe) va `/chat/<public_key>` (alohida sahifa) —
  `/api/public/widget/<key>/...` endpointlari, imzolangan tashrif buyuruvchi tokeni, rate limit,
  ruxsat etilgan domenlar bo'yicha `frame-ancestors`. Mantiq Telegram bilan bir xil `inbound` qatlami.

## Bilim bazasi

Yuklash (PDF/TXT/MD, hajm va tur tekshiruvi) → Celery vazifasi: matn ajratish (`pypdf`), sahifa
metadatasi, ~900 belgilik chunklar (overlap 120) → PostgreSQL `SearchVector` (prefix moslik) va
`pg_trgm` o'xshashligi bilan qidiruv. Matni olinmaydigan PDF `no_text` holatida qoladi va panel buni
ko'rsatadi. Hujjat ko'rinishi: `customer` (AI mijozga ishlatishi mumkin) yoki `staff` (faqat xodimlar).

## Fon vazifalari (Celery)

- `deliver_outbox_message` — tashqi xabar yuborish (idempotent, retry bilan).
- `retry_pending_outbox` (beat) — osilib qolgan navbatni qayta urinish.
- `dispatch_due_reminders` (beat, `REMINDER_DISPATCH_INTERVAL`) — vaqti kelgan, bron hali tasdiqlangan eslatmalar.
- `process_knowledge_document` — hujjatni indekslash.

## Frontend (`frontend/src/`)

- `lib/` — API klient (CSRF, xato formati), turlar, formatlash (tashkilot zonasida), react-query hook'lar.
- `contexts/` — autentifikatsiya va rol, mavzu (light/dark, server profilida saqlanadi), global filtrlar (sana, filial), toast.
- `components/ui` — dizayn tizimi: tugma, forma, badge, karta, dialog/drawer (focus trap, Esc), tablar, pagination.
- `components/charts` — sparkline, KPI karta, chiziqli grafik, gorizontal bar, funnel; har grafikda jadval ko'rinishi.
- `pages/` — 10 ta panel sahifasi + login + veb-chat. 1440/1024/390 px kengliklar E2E'da tekshiriladi.

## Docker

`backend/Dockerfile` — ikki bosqich (Node'da panel build → Python runtime, ffmpeg, `collectstatic`,
non-root foydalanuvchi, healthcheck). `docker-compose.yml`: `db` va `redis` (healthcheck) → `migrate`
(bir martalik; `DEMO_MODE=true` bo'lsa `seed_demo --if-empty`) → `web` (gunicorn), `worker`, `beat`;
`bot` — `telegram` profili bilan alohida yoqiladi.
