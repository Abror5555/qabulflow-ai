"""Mijozga ko'rinadigan tizim matnlari (uz/ru/en). Narx va jadval qiymatlari bu yerda yo'q —
ular faqat bazadan formatlanadi."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.core.utils import org_tz

TEXTS: dict[str, dict[str, str]] = {
    "privacy": {
        "uz": "🔒 Ma'lumotlaringiz faqat sinov darsiga yozish va siz bilan bog'lanish uchun ishlatiladi. Ism va telefon faqat bron bosqichida so'raladi.",
        "ru": "🔒 Ваши данные используются только для записи на пробный урок и связи с вами. Имя и телефон спросим только при записи.",
        "en": "🔒 Your data is used only to book a trial lesson and contact you. We ask for your name and phone only at booking.",
    },
    "choose_language": {
        "uz": "Tilni tanlang / Выберите язык / Choose language",
        "ru": "Tilni tanlang / Выберите язык / Choose language",
        "en": "Tilni tanlang / Выберите язык / Choose language",
    },
    "language_set": {
        "uz": "Til o'zbekchaga o'zgartirildi.",
        "ru": "Язык переключён на русский.",
        "en": "Language switched to English.",
    },
    "menu_hint": {
        "uz": "Quyidagi tugmalardan foydalaning yoki savolingizni yozing (ovozli xabar ham mumkin).",
        "ru": "Используйте кнопки ниже или напишите вопрос (можно голосовым сообщением).",
        "en": "Use the buttons below or type your question (voice messages work too).",
    },
    "btn_courses": {"uz": "📚 Kurslar", "ru": "📚 Курсы", "en": "📚 Courses"},
    "btn_prices": {"uz": "💳 Narxlar", "ru": "💳 Цены", "en": "💳 Prices"},
    "btn_branches": {"uz": "📍 Filiallar", "ru": "📍 Филиалы", "en": "📍 Branches"},
    "btn_schedule": {"uz": "🗓 Jadval", "ru": "🗓 Расписание", "en": "🗓 Schedule"},
    "btn_trial": {"uz": "✅ Sinov darsiga yozilish", "ru": "✅ Записаться на пробный", "en": "✅ Book a trial lesson"},
    "btn_my_bookings": {"uz": "🎟 Mening bronlarim", "ru": "🎟 Мои записи", "en": "🎟 My bookings"},
    "btn_admin": {"uz": "👤 Administrator", "ru": "👤 Администратор", "en": "👤 Administrator"},
    "btn_language": {"uz": "🌐 Til", "ru": "🌐 Язык", "en": "🌐 Language"},
    "ask_trial": {
        "uz": "Qaysi kurs bo'yicha bepul sinov darsiga yozilmoqchisiz?",
        "ru": "На какой курс хотите записаться на бесплатный пробный урок?",
        "en": "Which course would you like a free trial lesson for?",
    },
    "courses_header": {"uz": "Bizdagi faol kurslar:", "ru": "Наши активные курсы:", "en": "Our active courses:"},
    "no_courses": {
        "uz": "Hozircha faol kurs topilmadi. Administrator bilan bog'lanishingiz mumkin.",
        "ru": "Сейчас нет активных курсов. Можете связаться с администратором.",
        "en": "There are no active courses right now. You can contact an administrator.",
    },
    "branches_header": {"uz": "Filiallarimiz:", "ru": "Наши филиалы:", "en": "Our branches:"},
    "course_offer_trial": {
        "uz": "Bepul sinov darsiga yozib qo'yaymi?",
        "ru": "Записать вас на бесплатный пробный урок?",
        "en": "Shall I book you a free trial lesson?",
    },
    "ask_branch": {
        "uz": "Qaysi filial sizga qulay?",
        "ru": "Какой филиал вам удобен?",
        "en": "Which branch is convenient for you?",
    },
    "ask_time": {
        "uz": "Qaysi vaqt qulay: ertalab, tushdan keyin yoki kechqurun?",
        "ru": "Какое время удобно: утро, день или вечер?",
        "en": "What time suits you: morning, afternoon or evening?",
    },
    "slots_header": {
        "uz": "Bo'sh sinov darslari ({course}, {branch}):",
        "ru": "Свободные пробные уроки ({course}, {branch}):",
        "en": "Available trial lessons ({course}, {branch}):",
    },
    "slots_pick": {
        "uz": "Raqamini yozing (masalan: 1).",
        "ru": "Напишите номер (например: 1).",
        "en": "Reply with a number (e.g. 1).",
    },
    "no_slots": {
        "uz": "Afsuski, bu tanlov bo'yicha yaqin kunlarda bo'sh joy yo'q. Boshqa vaqt yoki filialni tanlaysizmi? Yoki administratorga ulab qo'yaman.",
        "ru": "К сожалению, по этому выбору в ближайшие дни мест нет. Выберете другое время или филиал? Или соединю с администратором.",
        "en": "Unfortunately there are no free seats for this choice in the coming days. Try another time or branch? Or I can connect you to an administrator.",
    },
    "ask_name": {
        "uz": "Bron uchun ismingizni yozing.",
        "ru": "Для записи напишите, пожалуйста, ваше имя.",
        "en": "Please type your name for the booking.",
    },
    "ask_phone": {
        "uz": "Telefon raqamingizni yozing (masalan: +998 90 123 45 67). U faqat sinov darsi bo'yicha bog'lanish uchun.",
        "ru": "Напишите номер телефона (например: +998 90 123 45 67). Он нужен только для связи по пробному уроку.",
        "en": "Please type your phone number (e.g. +998 90 123 45 67). It's used only to contact you about the trial.",
    },
    "invalid_phone": {
        "uz": "Raqam noto'g'ri ko'rinadi. Iltimos, +998 XX XXX XX XX formatida yozing.",
        "ru": "Номер выглядит некорректно. Напишите в формате +998 XX XXX XX XX.",
        "en": "That number looks invalid. Please use the +998 XX XXX XX XX format.",
    },
    "confirm_booking": {
        "uz": "Iltimos, tasdiqlang:\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\n👤 {name}\n\nYozib qo'yaymi? (Ha / Yo'q)",
        "ru": "Пожалуйста, подтвердите:\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\n👤 {name}\n\nЗаписываю? (Да / Нет)",
        "en": "Please confirm:\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\n👤 {name}\n\nShall I book it? (Yes / No)",
    },
    "confirm_again": {
        "uz": "Tasdiqlash uchun «Ha», boshqa vaqt uchun «Yo'q» deb yozing.",
        "ru": "Напишите «Да» для подтверждения или «Нет», чтобы выбрать другое время.",
        "en": "Reply «Yes» to confirm or «No» to choose another time.",
    },
    "booked": {
        "uz": "✅ Siz sinov darsiga yozildingiz!\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\nBron raqami: #{booking_id}",
        "ru": "✅ Вы записаны на пробный урок!\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\nНомер записи: #{booking_id}",
        "en": "✅ You're booked for a trial lesson!\n📚 {course}\n📍 {branch}{address}\n🕒 {when}\nBooking number: #{booking_id}",
    },
    "ask_reminder": {
        "uz": "Dars oldidan eslatma yuboraylikmi? (Ha / Yo'q)",
        "ru": "Отправить напоминание перед уроком? (Да / Нет)",
        "en": "Shall we send you a reminder before the lesson? (Yes / No)",
    },
    "reminder_on": {
        "uz": "Yaxshi, dars oldidan eslatma yuboramiz. Yana savolingiz bo'lsa yozing.",
        "ru": "Хорошо, напомним перед уроком. Если есть вопросы — пишите.",
        "en": "Great, we'll remind you before the lesson. Ask anything else anytime.",
    },
    "reminder_off": {
        "uz": "Tushunarli, eslatma yuborilmaydi. Yana savolingiz bo'lsa yozing.",
        "ru": "Понятно, напоминание не отправим. Если есть вопросы — пишите.",
        "en": "Understood, no reminder. Ask anything else anytime.",
    },
    "booking_declined": {
        "uz": "Mayli. Boshqa vaqtni tanlaysizmi?",
        "ru": "Хорошо. Выберете другое время?",
        "en": "Okay. Would you like another time?",
    },
    "booking_failed": {
        "uz": "Bron yaratilmadi: {reason} Boshqa vaqtni tanlab ko'ring.",
        "ru": "Запись не создана: {reason} Попробуйте выбрать другое время.",
        "en": "The booking was not created: {reason} Please try another time.",
    },
    "already_booked": {
        "uz": "Siz bu sinov darsiga allaqachon yozilgansiz (#{booking_id}).",
        "ru": "Вы уже записаны на этот пробный урок (#{booking_id}).",
        "en": "You're already booked for this trial lesson (#{booking_id}).",
    },
    "my_bookings_header": {"uz": "Sizning faol bronlaringiz:", "ru": "Ваши активные записи:", "en": "Your active bookings:"},
    "no_bookings": {
        "uz": "Sizda faol bron yo'q. Sinov darsiga yozilmoqchimisiz?",
        "ru": "У вас нет активных записей. Хотите записаться на пробный урок?",
        "en": "You have no active bookings. Would you like to book a trial lesson?",
    },
    "cancel_which": {
        "uz": "Qaysi bronni bekor qilamiz? Raqamini yozing.",
        "ru": "Какую запись отменить? Напишите номер.",
        "en": "Which booking should I cancel? Reply with its number.",
    },
    "cancel_confirm": {
        "uz": "Bronni bekor qilaymi?\n{summary}\n(Ha / Yo'q)",
        "ru": "Отменить запись?\n{summary}\n(Да / Нет)",
        "en": "Cancel this booking?\n{summary}\n(Yes / No)",
    },
    "cancelled": {
        "uz": "Bron #{booking_id} bekor qilindi. Eslatma yuborilmaydi. Boshqa vaqtga yozilmoqchi bo'lsangiz yozing.",
        "ru": "Запись #{booking_id} отменена. Напоминание не придёт. Если хотите другое время — напишите.",
        "en": "Booking #{booking_id} is cancelled. No reminder will be sent. Message me if you'd like another time.",
    },
    "cancel_kept": {
        "uz": "Bron o'z kuchida qoldi.",
        "ru": "Запись сохранена.",
        "en": "Your booking stays as is.",
    },
    "handoff": {
        "uz": "Sizni administrator bilan bog'layapman. Tez orada shu yerda javob beradi.",
        "ru": "Соединяю вас с администратором. Он скоро ответит здесь.",
        "en": "I'm connecting you with an administrator. They'll reply here shortly.",
    },
    "handoff_outside_hours": {
        "uz": " Ish vaqti: {hours}. Ish vaqtidan tashqari javob biroz kechikishi mumkin.",
        "ru": " Рабочее время: {hours}. Вне рабочего времени ответ может задержаться.",
        "en": " Working hours: {hours}. Outside working hours replies may be delayed.",
    },
    "human_mode_ack": {
        "uz": "Xabaringiz administratorga yetkazildi.",
        "ru": "Ваше сообщение передано администратору.",
        "en": "Your message has been passed to an administrator.",
    },
    "clarify": {
        "uz": "Savolingizni aniqlashtira olasizmi? Men kurslar, narxlar, filiallar, jadval va bepul sinov darsiga yozish bo'yicha yordam beraman.",
        "ru": "Можете уточнить вопрос? Я помогаю с курсами, ценами, филиалами, расписанием и записью на бесплатный пробный урок.",
        "en": "Could you clarify? I can help with courses, prices, branches, schedule and booking a free trial lesson.",
    },
    "knowledge_answer": {
        "uz": "{snippet}\n\n📄 Manba: {source}",
        "ru": "{snippet}\n\n📄 Источник: {source}",
        "en": "{snippet}\n\n📄 Source: {source}",
    },
    "ai_error": {
        "uz": "Kechirasiz, hozir javob bera olmayapman. Xabaringiz saqlandi va administrator xabardor qilindi.",
        "ru": "Извините, сейчас не могу ответить. Ваше сообщение сохранено, администратор уведомлён.",
        "en": "Sorry, I can't answer right now. Your message is saved and an administrator has been notified.",
    },
    "budget_exceeded": {
        "uz": "Bugungi avtomatik javoblar limiti tugadi. Administrator sizga shu yerda javob beradi.",
        "ru": "Лимит автоматических ответов на сегодня исчерпан. Администратор ответит вам здесь.",
        "en": "Today's automatic reply limit is reached. An administrator will reply here.",
    },
    "voice_too_long": {
        "uz": "Ovozli xabar juda uzun yoki katta (maksimum {seconds} soniya). Iltimos, qisqaroq yuboring yoki matn bilan yozing.",
        "ru": "Голосовое сообщение слишком длинное или большое (максимум {seconds} сек). Отправьте короче или напишите текстом.",
        "en": "The voice message is too long or large (max {seconds} s). Please send a shorter one or type your question.",
    },
    "voice_bad_format": {
        "uz": "Bu audio formatni qabul qila olmadim. Iltimos, savolingizni matn bilan yozing.",
        "ru": "Не удалось принять этот аудиоформат. Пожалуйста, напишите вопрос текстом.",
        "en": "I couldn't accept this audio format. Please type your question.",
    },
    "voice_failed": {
        "uz": "Ovozli xabarni hozir matnga aylantira olmadim. Xabaringiz saqlandi — iltimos, savolingizni matn bilan yozing.",
        "ru": "Сейчас не удалось распознать голосовое сообщение. Оно сохранено — пожалуйста, напишите вопрос текстом.",
        "en": "I couldn't transcribe the voice message right now. It's saved — please type your question.",
    },
    "voice_unclear": {
        "uz": "Ovozli xabarni aniq tushuna olmadim. Siz shuni nazarda tutdingizmi: «{transcript}»? Iltimos, matn bilan aniqlashtiring.",
        "ru": "Не совсем разобрал голосовое сообщение. Вы имели в виду: «{transcript}»? Уточните, пожалуйста, текстом.",
        "en": "I couldn't hear the voice message clearly. Did you mean: «{transcript}»? Please clarify in text.",
    },
    "reminder": {
        "uz": "⏰ Eslatma: bugun/yaqinda sinov darsingiz bor.\n📚 {course}\n🕒 {when}\n📍 {branch} {address}\nKelolmasangiz, shu yerga yozing.",
        "ru": "⏰ Напоминание: скоро ваш пробный урок.\n📚 {course}\n🕒 {when}\n📍 {branch} {address}\nЕсли не сможете прийти — напишите сюда.",
        "en": "⏰ Reminder: your trial lesson is coming up.\n📚 {course}\n🕒 {when}\n📍 {branch} {address}\nIf you can't come, reply here.",
    },
    "operator_joined": {
        "uz": "Administrator suhbatga qo'shildi.",
        "ru": "Администратор подключился к диалогу.",
        "en": "An administrator has joined the chat.",
    },
    "ai_returned": {
        "uz": "Suhbat yana AI yordamchiga o'tkazildi.",
        "ru": "Диалог снова передан AI-помощнику.",
        "en": "The chat is back with the AI assistant.",
    },
    "test_mode_booking": {
        "uz": "🧪 Test rejimi: haqiqiy bron yaratilmadi (slot #{slot_id}).",
        "ru": "🧪 Тестовый режим: реальная запись не создана (слот #{slot_id}).",
        "en": "🧪 Test mode: no real booking was created (slot #{slot_id}).",
    },
    "course_card": {
        "uz": "📚 {name} — {level}\n💳 Narx: {price}\n⏱ Davomiyligi: {months} oy, haftasiga {lessons} dars ({minutes} daqiqa)\n🗓 Guruhlar:\n{groups}",
        "ru": "📚 {name} — {level}\n💳 Цена: {price}\n⏱ Длительность: {months} мес., {lessons} занятия в неделю ({minutes} мин)\n🗓 Группы:\n{groups}",
        "en": "📚 {name} — {level}\n💳 Price: {price}\n⏱ Duration: {months} months, {lessons} lessons a week ({minutes} min)\n🗓 Groups:\n{groups}",
    },
    "no_groups": {"uz": "• hozircha faol guruh yo'q", "ru": "• пока нет активных групп", "en": "• no active groups yet"},
    "which_course": {"uz": "Qaysi kurs sizni qiziqtiradi?", "ru": "Какой курс вас интересует?", "en": "Which course interests you?"},
    "seats_left": {"uz": "{n} ta joy", "ru": "мест: {n}", "en": "{n} seats"},
    "thanks_reply": {
        "uz": "Arzimaydi! Yana savolingiz bo'lsa, bemalol yozing.",
        "ru": "Пожалуйста! Если будут вопросы — пишите.",
        "en": "You're welcome! Message me anytime.",
    },
    "anything_else": {
        "uz": "Yana savolingiz bo'lsa, yozing.",
        "ru": "Если есть ещё вопросы — пишите.",
        "en": "Anything else I can help with?",
    },
    "booking_not_done": {
        "uz": "Bron hali yaratilmadi. Davom etish uchun vaqtni tanlang va tasdiqlang.",
        "ru": "Запись ещё не создана. Чтобы продолжить, выберите время и подтвердите.",
        "en": "The booking hasn't been created yet. Please choose a time and confirm to continue.",
    },
    "invalid_name": {
        "uz": "Ismingizni harflar bilan yozing (masalan: Aziza).",
        "ru": "Напишите имя буквами (например: Азиза).",
        "en": "Please type your name using letters (e.g. Aziza).",
    },
    "demo_label": {"uz": "Demo javob", "ru": "Демо-ответ", "en": "Demo reply"},
    "price_unavailable": {
        "uz": "Aniq narx ma'lumotini tasdiqlay olmadim. Administrator aniq ma'lumot beradi.",
        "ru": "Не могу подтвердить точную цену. Администратор уточнит.",
        "en": "I can't confirm the exact price. An administrator will clarify.",
    },
}

WEEKDAYS = {
    "uz": ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"],
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

CURRENCY_LABEL = {"uz": {"UZS": "so'm"}, "ru": {"UZS": "сум"}, "en": {"UZS": "UZS"}}
PERIOD_LABEL = {
    "uz": {"month": "oyiga", "course": "kurs uchun"},
    "ru": {"month": "в месяц", "course": "за курс"},
    "en": {"month": "per month", "course": "per course"},
}
LEVEL_LABEL = {
    "uz": {"beginner": "boshlang'ich", "intermediate": "o'rta", "advanced": "yuqori", "all": "barcha darajalar"},
    "ru": {"beginner": "начальный", "intermediate": "средний", "advanced": "продвинутый", "all": "все уровни"},
    "en": {"beginner": "beginner", "intermediate": "intermediate", "advanced": "advanced", "all": "all levels"},
}


def t(key: str, lang: str = "uz", **kwargs) -> str:
    entry = TEXTS.get(key, {})
    template = entry.get(lang) or entry.get("uz") or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def format_money(amount: Decimal | float | int, currency: str = "UZS", lang: str = "uz") -> str:
    value = Decimal(str(amount))
    if value == value.to_integral():
        text = f"{int(value):,}".replace(",", " ")
    else:
        text = f"{value:,.2f}".replace(",", " ")
    label = CURRENCY_LABEL.get(lang, {}).get(currency, currency)
    return f"{text} {label}"


def format_price(course, lang: str = "uz") -> str:
    period = PERIOD_LABEL.get(lang, PERIOD_LABEL["uz"]).get(course.price_period, "")
    return f"{format_money(course.price, course.currency, lang)} {period}".strip()


def format_slot_time(dt, organization, lang: str = "uz") -> str:
    local = timezone.localtime(dt, org_tz(organization))
    wd = WEEKDAYS.get(lang, WEEKDAYS["uz"])[local.weekday()]
    return f"{local:%d.%m} ({wd}) {local:%H:%M}"


def level_label(level: str, lang: str = "uz") -> str:
    return LEVEL_LABEL.get(lang, LEVEL_LABEL["uz"]).get(level, level)
