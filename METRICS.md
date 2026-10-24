# QabulFlow AI — statistik ta'riflar va hisoblash qoidalari

Barcha qiymatlar backend'da (`backend/apps/analytics/services.py`) haqiqiy DB yozuvlaridan
hisoblanadi. Frontend faqat API javobini ko'rsatadi; tasodifiy yoki dekorativ statistika yo'q.
Panel kartalari, grafiklar, drill-down jadvali va CSV eksport **bitta** `Analytics` klassidan va bir
xil filtrlardan foydalanadi (`/api/analytics/overview/`, `/api/analytics/details/`, `/api/analytics/export.csv`).

## 1. Davr va vaqt zonasi

- Filtr: `date_from`, `date_to` (YYYY-MM-DD, ikkalasi ham kiradi). Standart — bugundan oldingi 30 kun
  (`date_to` = tashkilot zonasidagi bugun, `date_from` = `date_to − 29`). Maksimal davr — 366 kun.
- Chegaralar tashkilot vaqt zonasida (standart `Asia/Tashkent`):
  `start = date_from 00:00`, `end = (date_to + 1 kun) 00:00`; oraliq yarim ochiq `[start, end)`.
- **Oldingi davr** — teng uzunlikdagi, bevosita oldingi oraliq: `prev_end = start`,
  `prev_start = start − (end − start)`. Masalan, 25-sen – 24-okt (30 kun) uchun oldingi davr 26-avg – 24-sen.
- Guruhlash (`granularity`): `day` yoki `week` (dushanbadan boshlanadigan hafta). 62 kundan uzun davr
  uchun standart — `week`. Birinchi va oxirgi hafta davr chegarasi bilan kesiladi (`bucket_start`, `bucket_end`).
- Test suhbatlar (AI test-chat) va `is_test` mijozlar hech bir ko'rsatkichga kirmaydi.

## 2. Filtrlar

| Filtr | Mijozlar | Suhbatlar | Bronlar | O'qishga yozilish |
| --- | --- | --- | --- | --- |
| `branch_id` | `lead.branch` | `lead.branch` | slot guruhining filiali | guruh filiali (guruh bo'lmasa lead filiali) |
| `course_id` | `lead.interested_course` | `lead.interested_course` | slot guruhining kursi | `enrollment.course` |
| `source` | `lead.source` | `lead.source` | `lead.source` | `lead.source` |

Filial cheklovi bo'lgan xodim (egasidan boshqa) faqat ruxsat etilgan filiallar statistikasini ko'radi;
ruxsatsiz `branch_id` — 403. Filtrlar KPI, sparkline, grafiklar, funnel, drill-down va CSV ga bir xil qo'llanadi.

## 3. KPI'lar

| Kalit | Nomi (panelda) | Formula (davr `[start, end)`) |
| --- | --- | --- |
| `new_leads` | Yangi mijozlar | `created_at` davrda bo'lgan noyob lead'lar soni |
| `new_conversations` | Yangi suhbatlar | `created_at` davrda bo'lgan Telegram/veb-chat suhbatlari |
| `confirmed_bookings` | Tasdiqlangan sinov bronlari | `confirmed_at` davrda bo'lgan bronlar (keyin bekor qilinganlar ham — "yangi bron" birinchi tasdiq vaqti bo'yicha) |
| `attended` | Sinov darsiga kelganlar | holati `attended`, slot boshlanishi davrda bo'lgan bronlar |
| `enrolled` | O'qishga yozilganlar | administrator tasdiqlagan (`confirmed`) enrollment, `confirmed_at` davrda |
| `conversion_rate` | Mijozdan bronga konversiya | pastda |
| `ai_first_response_median` | AI birinchi javob (median) | pastda |
| `operator_first_response_median` | Operator birinchi javob (median) | pastda |

**Bron va bekor qilish.** `confirmed_at` bron birinchi marta tasdiqlanganda yoziladi va o'zgarmaydi;
ko'chirish yangi bron hisoblanmaydi. Bekor qilish alohida voqea (`cancelled_at`, `BookingEvent`) —
grafikdagi "bekor qilingan" seriyasi `cancelled_at` bo'yicha sanaladi.

### Konversiya (kohorta)

```
maxraj  = davrda yaratilgan noyob lead'lar
surat   = shu lead'lardan davr oxirigacha (confirmed_at < end) kamida bitta tasdiqlangan sinov broni olganlar (noyob)
qiymat  = surat / maxraj × 100, 0.1 aniqlikda
```

Keyinchalik bekor qilingan bron ham "bron olgan" deb hisoblanadi (tasdiq bo'lgan). Bir lead bir
nechta bron olsa ham bir marta sanaladi. Maxraj 0 bo'lsa qiymat `null` va panelda "—".
KPI kartasida `surat/maxraj mijoz` ko'rinadi; ta'rif kartadagi (i) tooltip'da yozilgan.
O'zgarish foiz punktda (`p.p.`): `joriy − oldingi`.

### Birinchi javob vaqti (median, soniya)

- **AI:** davrda yaratilgan suhbatlar; `t0` — mijozning birinchi xabari, `t1` — undan keyingi
  birinchi AI xabari. Qiymat `median(t1 − t0)`.
- **Operator:** davrda yaratilgan, mijoz yoki AI so'rovi bilan ochilgan operatorga o'tkazishlar
  (operator o'zi olgan holatlar kirmaydi); `t0` — o'tkazishdan oldingi oxirgi mijoz xabari
  (bo'lmasa o'tkazish vaqti), `t1` — undan keyingi birinchi operator xabari.
- AI va operator ko'rsatkichlari aralashtirilmaydi; javobsiz holatlar namunaga kirmaydi; namuna
  soni kartada ko'rsatiladi ("N ta suhbat"). Namuna bo'lmasa `null` ("—").
- Bu ko'rsatkichlar uchun pastroq qiymat yaxshi (`lower_is_better`), o'zgarish belgisi shunga mos ranglanadi.

### Oldingi davr bilan solishtirish

- Son va median ko'rsatkichlar: `change = (joriy − oldingi) / oldingi × 100` (0.1 aniqlik).
- Oldingi qiymat 0 yoki `null` bo'lsa foiz hisoblanmaydi: `no_previous_data = true`, panelda
  "oldingi davrda ma'lumot yo'q" (cheksiz yoki soxta foiz chiqmaydi).
- Konversiya: `change = joriy − oldingi` (p.p.); oldingi `null` bo'lsa — "ma'lumot yo'q".

### Sparkline

Har KPI uchun davr ichidagi har bir bucket (kun/hafta) qiymati, xuddi shu formula bilan:
sonlar — bucket ichidagi hodisalar; konversiya — bucket'da yaratilgan lead'lar kohortasi (bron
davr oxirigacha); medianlar — `t0` bucket'iga tushgan juftliklar. Hisoblab bo'lmaydigan bucket
(maxraj yoki namuna yo'q) `null` — 0 deb ko'rsatilmaydi, chiziq qo'shni nuqtalarni tutashtiradi.

## 4. Grafiklar

| Grafik | Ta'rif |
| --- | --- |
| Yangi mijozlar va tasdiqlangan bronlar | bucket bo'yicha `new_leads` (created_at) va `confirmed_bookings` (confirmed_at); jadval ko'rinishida `cancelled_bookings` ham |
| Kanallar | davrda yaratilgan suhbatlar: Telegram / veb-chat |
| Manbalar | davrda yaratilgan lead'lar manbasi (Telegram, veb-chat, qo'lda, tavsiya, tashrif) |
| Kurslar: qiziqish va bronlar | qiziqish — davrda yaratilgan lead'lar `interested_course` bo'yicha; bronlar — davrda tasdiqlangan bronlar slot kursi bo'yicha |
| Bronlar holati | davrda tasdiqlangan bronlarning **joriy** holati: tasdiqlangan, bekor qilingan, qatnashdi, kelmadi |
| Funnel | pastda |

### Funnel: mijozdan o'qishga yozilishgacha

Kohorta — davrda yaratilgan noyob lead'lar (konversiya bilan bir xil). Har lead uchun davr oxirigacha
(`< end`) **hodisalar tarixidan** erishilgan eng yuqori bosqich olinadi:

| Bosqich | Erishilgan deb hisoblanadi, agar |
| --- | --- |
| Murojaat | lead kohortada |
| Ehtiyoj aniqlandi | `LeadStatusChange.to_status ≥ qualified` |
| Sinovga yozildi | holat tarixi `trial_booked` yoki `confirmed_at < end` bo'lgan bron |
| Sinovga keldi | holat tarixi `trial_attended` yoki `attended` bron voqeasi |
| O'qishga yozildi | holat tarixi `enrolled` yoki tasdiqlangan enrollment |

Bosqich soni — shu bosqichga **yoki undan yuqoriga** yetgan lead'lar; ulush — kohortaga nisbatan foiz.
Qayta yozilish yoki bir nechta bron lead'ni takror sanamaydi; boshqa davrda yaratilgan lead'lar aralashmaydi.
Hozir bekor qilingan, lekin ilgari yozilgan lead "Sinovga yozildi" bosqichiga yetgan hisoblanadi.

## 5. Drill-down va CSV

- Grafik nuqtasi, funnel bosqichi, kanal, manba, kurs yoki holat segmentini bosish
  `/api/analytics/details/?metric=...&bucket=...` so'roviga aylanadi va pastdagi jadvalda aynan shu
  ko'rsatkichni tashkil etgan yozuvlar chiqadi (soni grafikdagi qiymatga teng; `new_leads` nuqtasi uchun avtomatik test bor).
- CSV (`export.csv`, egasi va menejer): filtrlar, KPI (joriy, oldingi, o'zgarish), vaqt qatori,
  kanallar, manbalar, bron holatlari, funnel va kurslar. Qiymatlar panel bilan bir xil service'dan
  olinadi; fayl UTF-8 BOM bilan (Excel uchun), eksport vaqti tashkilot zonasida.

## 6. Doiradan tashqari

To'lov tizimi yo'q, shuning uchun tushum/daromad ko'rsatkichi hisoblanmaydi va ko'rsatilmaydi.
Kurs narxi faqat ma'lumot sifatida (mijozga javob va kurs kartasi) ishlatiladi.
