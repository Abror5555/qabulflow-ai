"""Qayta yaratiladigan sintetik demo dataset.

    python manage.py seed_demo [--seed 42] [--leads 160]

* Faqat DEMO_MODE=true bo'lganda ishlaydi (production'da demo parollar yaratilmaydi).
* Har ishga tushganda demo tashkilotlar to'liq o'chirilib, qaytadan yaratiladi — dublikat yo'q.
* Barcha ismlar, telefonlar (+998 00 ...), Telegram ID'lar va manzillar sintetik.
* Oxirida bir nechta suhbat HAQIQIY pipeline (inbound → demo agent → tool'lar → bron service) orqali o'tkaziladi.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.ai_agent.models import AICallLog, AISettings
from apps.ai_agent.texts import format_price, format_slot_time, level_label, t
from apps.bookings.models import BookingEvent, Enrollment, TrialBooking
from apps.conversations.models import Conversation, HumanHandoff, Message
from apps.core.models import AuditEvent
from apps.core.utils import org_tz
from apps.courses.models import Course, Group, TrialSlot
from apps.integrations.models import IntegrationStatus, ProcessedTelegramUpdate
from apps.knowledge.models import KnowledgeDocument
from apps.leads.models import Lead, LeadNote, LeadStatusChange
from apps.notifications.models import Notification, OutboxMessage, Reminder
from apps.organizations.models import Branch, Membership, Organization, WidgetSettings

DEMO_PASSWORD = "Demo12345!"
DEMO_SLUG = "demo-academy"
ISOLATION_SLUG = "isolation-center"
DEMO_WIDGET_KEY = "wk_demo_academy"
ISOLATION_WIDGET_KEY = "wk_isolation_center"

FIRST_NAMES = [
    "Aziza",
    "Dilnoza",
    "Madina",
    "Nilufar",
    "Sevara",
    "Shahnoza",
    "Zarina",
    "Malika",
    "Gulnora",
    "Kamila",
    "Laylo",
    "Mohira",
    "Nodira",
    "Ozoda",
    "Rayhona",
    "Sabina",
    "Umida",
    "Yulduz",
    "Feruza",
    "Barno",
    "Jasur",
    "Bekzod",
    "Doniyor",
    "Javohir",
    "Sardor",
    "Otabek",
    "Sherzod",
    "Ulug'bek",
    "Akmal",
    "Bobur",
    "Farrux",
    "Islom",
    "Jamshid",
    "Kamron",
    "Mirjalol",
    "Nodir",
    "Rustam",
    "Sanjar",
    "Temur",
    "Zafar",
    "Alisher",
    "Asadbek",
    "Azizbek",
    "Behruz",
    "Diyorbek",
    "Elyor",
    "Husan",
    "Ibrohim",
]
LAST_INITIALS = list("ABDEFGHIJKMNORSTUXYZ")
RU_FIRST = ["Анна", "Мария", "Екатерина", "Алина", "Дарья", "Ильдар", "Тимур", "Артём", "Руслан", "Камила", "Эльдар", "Диана"]
EN_FIRST = ["Emily", "Daniel", "Sofia", "Adam", "Lina", "Omar"]

KB_FAQ = """# QabulFlow Demo Academy — tez-tez beriladigan savollar

## To'lov tartibi
To'lov har oy boshida, darslar boshlanishidan oldin amalga oshiriladi. Naqd pul, plastik karta yoki bank o'tkazmasi qabul qilinadi.

## Chegirmalar
Oilaviy chegirma: bir oiladan ikki va undan ortiq o'quvchi o'qisa, har biriga 10% chegirma beriladi.
Oldindan to'lov: 3 oylik to'lovni birdaniga amalga oshirganlarga 5% chegirma.
Семейная скидка: если из одной семьи учатся двое и более, каждому скидка 10%. При оплате сразу за 3 месяца — скидка 5%.
Family discount: 10% for each student when two or more family members study with us; 5% off when paying for 3 months upfront.

## Pulni qaytarish
Birinchi to'liq hafta ichida kursni tark etsangiz, qolgan darslar uchun to'lov qaytariladi. Keyinchalik to'lov keyingi oyga o'tkaziladi.
Оплата производится в начале каждого месяца: наличными, картой или переводом.

## Darsga nima olib kelish kerak
Daftar va ruchka. IELTS va Python kurslari uchun noutbuk bo'lsa yaxshi, lekin markazda kompyuter xonasi bor.

## Avtoturargoh
Chilonzor filialida bepul avtoturargoh bor. Yunusobod filialida — ko'cha bo'ylab pullik turargoh.

## Onlayn darslar
Hozircha barcha guruhlar oflayn. Kasallik sababli dars qoldirilsa, video yozuv o'qituvchi orqali beriladi.
"""

KB_TRIAL = """Bepul sinov darsi haqida

Sinov darsi bepul va 60–90 daqiqa davom etadi. Siz haqiqiy guruh darsida qatnashasiz va o'qituvchi darajangizni og'zaki baholaydi.
Sinov darsiga 10 daqiqa oldin keling va administratorga ismingizni ayting.
Sinov darsidan keyin administrator sizga mos guruh va boshlanish sanasini tavsiya qiladi.
Agar kela olmasangiz, botga yoki chatga "bekor qilish" deb yozing — joyingiz boshqa mijozga beriladi.

Пробный урок бесплатный и длится 60–90 минут. Приходите за 10 минут до начала.
The trial lesson is free and lasts 60–90 minutes. Please arrive 10 minutes early.
"""

KB_INTERNAL = """# Ichki: operatorlar uchun eslatma (mijozga ko'rsatilmaydi)

- Menejer maxsus holatlarda qo'shimcha chegirma berishi mumkin — faqat menejer tasdig'i bilan.
- O'qituvchilar ish jadvali va shaxsiy telefonlari mijozlarga berilmaydi.
- Kechikib to'lov qilganlar ro'yxati buxgalteriyada yuritiladi.
"""


@dataclass
class CourseSpec:
    name: str
    level: str
    price: int
    months: int
    lessons: int
    minutes: int
    keywords: list
    description: str
    weight: float


COURSES = [
    CourseSpec(
        "IELTS Intensive",
        "intermediate",
        1_200_000,
        3,
        3,
        90,
        ["ielts", "айелтс", "иелтс", "aylets"],
        "IELTS 6.5+ ga tayyorlov: Listening, Reading, Writing va Speaking bo'yicha haftalik mock testlar.",
        0.35,
    ),
    CourseSpec(
        "General English",
        "beginner",
        650_000,
        6,
        3,
        90,
        ["general english", "ingliz tili", "ingliz", "english", "английский", "инглиз"],
        "Noldan B1 darajagacha ingliz tili: so'zlashuv, grammatika va tinglab tushunish.",
        0.30,
    ),
    CourseSpec(
        "Python asoslari",
        "beginner",
        900_000,
        4,
        2,
        120,
        ["python", "pyton", "piton", "питон", "dasturlash", "программирование", "programming"],
        "Dasturlashni noldan o'rganish: Python sintaksisi, algoritmlar va kichik loyihalar.",
        0.22,
    ),
    CourseSpec(
        "Matematika (DTM)",
        "all",
        550_000,
        8,
        3,
        90,
        ["matematika", "математика", "math", "dtm"],
        "Abituriyentlar uchun DTM test formatidagi matematika tayyorlovi.",
        0.13,
    ),
]

# (kurs indeksi, filial indeksi, guruh nomi, o'qituvchi, kunlar, boshlanish, tugash, slot sig'imi)
GROUPS = [
    (0, 0, "IELTS-CH-ertalab", "Aziza R. (demo)", [0, 2, 4], time(9, 0), time(10, 30), 4),
    (0, 0, "IELTS-CH-kechki", "Jasur T. (demo)", [1, 3, 5], time(18, 0), time(19, 30), 4),
    (0, 1, "IELTS-YU-kunduzgi", "Nodira S. (demo)", [0, 2, 4], time(15, 0), time(16, 30), 3),
    (1, 0, "GE-CH-ertalab", "Bekzod A. (demo)", [1, 3, 5], time(10, 0), time(11, 30), 5),
    (1, 1, "GE-YU-kechki", "Madina K. (demo)", [0, 2, 4], time(18, 30), time(20, 0), 5),
    (2, 0, "PY-CH-kunduzgi", "Otabek M. (demo)", [1, 3], time(16, 0), time(18, 0), 4),
    (2, 1, "PY-YU-dam-olish", "Sherzod N. (demo)", [5, 6], time(11, 0), time(13, 0), 6),
    (3, 1, "MATH-YU-kunduzgi", "Gulnora X. (demo)", [0, 2, 4], time(14, 0), time(15, 30), 4),
]

QUESTION = {
    "uz": [
        "Assalomu alaykum, {course} kursi narxi qancha?",
        "{course} bo'yicha ma'lumot bersangiz",
        "Salom! {course} guruhlari qachon bo'ladi?",
        "{course} kursiga yozilmoqchi edim",
    ],
    "ru": ["Здравствуйте, сколько стоит курс {course}?", "Подскажите расписание {course}", "Хочу записаться на {course}"],
    "en": ["Hi, how much is the {course} course?", "Could you tell me about {course}?"],
}
WANT_TRIAL = {"uz": "Sinov darsiga yozilsam bo'ladimi?", "ru": "Можно записаться на пробный урок?", "en": "Can I book a trial lesson?"}
YES = {"uz": "Ha", "ru": "Да", "en": "Yes"}
HANDOFF_ASK = {"uz": "Administrator bilan gaplashsam bo'ladimi?", "ru": "Можно поговорить с администратором?", "en": "Can I talk to an administrator?"}
OPERATOR_REPLY = {
    "uz": "Assalomu alaykum! Men administratorman. Savolingizga yordam beraman — qulay vaqtni ayting, guruhni birga tanlaymiz.",
    "ru": "Здравствуйте! Я администратор. Помогу с вашим вопросом — подскажите удобное время, подберём группу.",
    "en": "Hello! I'm the administrator. Tell me a convenient time and we'll pick a group together.",
}
GENERIC_Q = {
    "uz": ["Oilaviy chegirma bormi?", "Avtoturargoh bormi?", "To'lovni qanday qilsa bo'ladi?"],
    "ru": ["Есть ли семейная скидка?", "Как можно оплатить?"],
    "en": ["Is there a family discount?"],
}


def demo_phone(rng: random.Random) -> str:
    # +998 00 ... — O'zbekistonda mavjud bo'lmagan operator kodi (sintetik)
    return "+99800" + "".join(str(rng.randint(0, 9)) for _ in range(7))


class Command(BaseCommand):
    help = "Sintetik demo ma'lumotlarni (qayta) yaratadi. Faqat DEMO_MODE=true."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--leads", type=int, default=160)
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--skip-live", action="store_true", help="Haqiqiy pipeline orqali demo suhbatlarni o'tkazmaslik")
        parser.add_argument("--if-empty", action="store_true", help="Demo tashkilot allaqachon bo'lsa hech narsa qilmaslik (docker qayta ishga tushganda)")

    # ------------------------------------------------------------------ entry
    def handle(self, *args, **opts):
        if not settings.DEMO_MODE:
            raise CommandError("DEMO_MODE=false: demo hisoblar va sintetik ma'lumotlar faqat demo muhitida yaratiladi.")
        if opts["if_empty"] and Organization.objects.filter(slug=DEMO_SLUG).exists():
            self.stdout.write("Demo ma'lumotlar allaqachon mavjud — o'tkazib yuborildi (--if-empty).")
            return
        self.seed = opts["seed"]
        self.rng = random.Random(self.seed)
        self.days = opts["days"]
        with transaction.atomic():
            self.wipe()
            self.build_demo_org()
            self.build_history(opts["leads"])
            self.build_isolation_org()
        self.build_knowledge()
        if not opts["skip_live"]:
            self.run_live_scenarios()
        self.finalize()
        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar tayyor."))
        self.stdout.write(f"  Kirish: owner@{settings.DEMO_ACCOUNT_DOMAIN} / {DEMO_PASSWORD}")
        self.stdout.write(f"          manager@{settings.DEMO_ACCOUNT_DOMAIN} / {DEMO_PASSWORD}")
        self.stdout.write(f"          operator@{settings.DEMO_ACCOUNT_DOMAIN} / {DEMO_PASSWORD}")
        self.stdout.write(f"  Veb-chat: /chat/{DEMO_WIDGET_KEY}   Demo sayt: /demo-site/")

    # ------------------------------------------------------------------ wipe
    def wipe(self):
        orgs = list(Organization.objects.filter(slug__in=[DEMO_SLUG, ISOLATION_SLUG]))
        for org in orgs:
            Reminder.objects.filter(organization=org).delete()
            OutboxMessage.objects.filter(organization=org).delete()
            Notification.objects.filter(organization=org).delete()
            BookingEvent.objects.filter(organization=org).delete()
            TrialBooking.objects.filter(organization=org).delete()
            Enrollment.objects.filter(organization=org).delete()
            Conversation.objects.filter(organization=org).delete()
            Lead.objects.filter(organization=org).delete()
            TrialSlot.objects.filter(organization=org).delete()
            Group.objects.filter(organization=org).delete()
            Course.objects.filter(organization=org).delete()
            for doc in KnowledgeDocument.objects.filter(organization=org):
                doc.file.delete(save=False)
            KnowledgeDocument.objects.filter(organization=org).delete()
            AuditEvent.objects.filter(organization=org).delete()
            AICallLog.objects.filter(organization=org).delete()
            IntegrationStatus.objects.filter(organization=org).delete()
            ProcessedTelegramUpdate.objects.filter(organization=org).delete()
            org.delete()
        User.objects.filter(Q(email__iendswith="@" + settings.DEMO_ACCOUNT_DOMAIN) | Q(email__iendswith=".demo.qabulflow.local")).delete()

    # ------------------------------------------------------------------ structure
    def build_demo_org(self):
        rng = self.rng
        self.tz = org_tz(Organization(timezone="Asia/Tashkent"))
        self.now = timezone.now()
        self.today = timezone.localtime(self.now, self.tz).date()
        org = Organization.objects.create(
            name="QabulFlow Demo Academy", slug=DEMO_SLUG, timezone="Asia/Tashkent", is_demo=True, created_at=self.now - timedelta(days=self.days + 10)
        )
        self.org = org
        d = settings.DEMO_ACCOUNT_DOMAIN
        self.owner = User.objects.create_user(f"owner@{d}", DEMO_PASSWORD, full_name="Kamola Rahimova", is_demo=True)
        self.manager = User.objects.create_user(f"manager@{d}", DEMO_PASSWORD, full_name="Sardor Aliyev", is_demo=True)
        self.operator = User.objects.create_user(f"operator@{d}", DEMO_PASSWORD, full_name="Malika Yusupova", is_demo=True)
        self.operator2 = User.objects.create_user(f"operator2@{d}", DEMO_PASSWORD, full_name="Javohir Karimov", is_demo=True)
        self.owner.preferences = {"theme": "light"}
        self.owner.save(update_fields=["preferences"])
        self.branches = [
            Branch.objects.create(
                organization=org,
                name="Chilonzor filiali",
                address="Chilonzor tumani, Bunyodkor ko'chasi, 12 (sintetik manzil)",
                landmark="Novza metro bekati yaqinida",
            ),
            Branch.objects.create(
                organization=org, name="Yunusobod filiali", address="Yunusobod tumani, Amir Temur ko'chasi, 48 (sintetik manzil)", landmark="Minor metro bekati"
            ),
        ]
        Membership.objects.create(user=self.owner, organization=org, role="owner")
        Membership.objects.create(user=self.manager, organization=org, role="manager")
        op = Membership.objects.create(user=self.operator, organization=org, role="operator")
        op.branches.set([self.branches[0]])
        Membership.objects.create(user=self.operator2, organization=org, role="operator")
        self.staff = [self.manager, self.operator, self.operator2]

        self.courses = []
        for spec in COURSES:
            self.courses.append(
                Course.objects.create(
                    organization=org,
                    name=spec.name,
                    level=spec.level,
                    price=Decimal(spec.price),
                    duration_months=spec.months,
                    lessons_per_week=spec.lessons,
                    lesson_minutes=spec.minutes,
                    keywords=spec.keywords,
                    description=spec.description,
                    created_at=org.created_at,
                )
            )
        self.groups = []
        for ci, bi, name, teacher, days, st, et, cap in GROUPS:
            g = Group.objects.create(
                organization=org,
                course=self.courses[ci],
                branch=self.branches[bi],
                name=name,
                teacher_name=teacher,
                days=days,
                start_time=st,
                end_time=et,
                capacity=14,
                enrolled_count=rng.randint(6, 11),
                start_date=self.today - timedelta(days=120),
                created_at=org.created_at,
            )
            g._slot_capacity = cap
            self.groups.append(g)

        slots = []
        for g in self.groups:
            for offset in range(-self.days - 2, 15):
                day = self.today + timedelta(days=offset)
                if day.weekday() not in g.days:
                    continue
                starts = datetime.combine(day, g.start_time, tzinfo=self.tz)
                ends = datetime.combine(day, g.end_time, tzinfo=self.tz)
                slots.append(TrialSlot(organization=org, group=g, starts_at=starts, ends_at=ends, capacity=g._slot_capacity, created_at=org.created_at))
        TrialSlot.objects.bulk_create(slots)
        self.slots_by_course: dict[int, list[TrialSlot]] = {}
        for s in TrialSlot.objects.filter(organization=org).select_related("group__course", "group__branch").order_by("starts_at"):
            self.slots_by_course.setdefault(s.group.course_id, []).append(s)
        self.slot_seats: dict[int, int] = {}

        AISettings.objects.create(organization=org)
        WidgetSettings.objects.create(
            organization=org, public_key=DEMO_WIDGET_KEY, title="QabulFlow Demo Academy", allowed_origins=["http://localhost:8000", "http://127.0.0.1:8000"]
        )

    # ------------------------------------------------------------------ history
    def _pick_day(self) -> int:
        weights = []
        for d in range(self.days):
            day = self.today - timedelta(days=self.days - 1 - d)
            w = 1.0 + 0.9 * (d / max(1, self.days - 1))
            if day.weekday() < 4:
                w += 0.35
            if day.weekday() == 6:
                w -= 0.4
            weights.append(max(0.2, w))
        return self.rng.choices(range(self.days), weights=weights, k=1)[0]

    def _rand_time(self, day, lo=9, hi=22) -> datetime:
        return datetime.combine(day, time(self.rng.randint(lo, hi - 1), self.rng.randint(0, 59), self.rng.randint(0, 59)), tzinfo=self.tz)

    def _name(self, lang: str) -> str:
        if lang == "ru":
            return f"{self.rng.choice(RU_FIRST)} {self.rng.choice('АБВГДКМНРСТ')}."
        if lang == "en":
            return f"{self.rng.choice(EN_FIRST)} {self.rng.choice('ABCDKMRST')}."
        return f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_INITIALS)}."

    def _find_slot(self, course: Course, after: datetime, within_days: int = 7, branch_id=None) -> TrialSlot | None:
        candidates = [
            s
            for s in self.slots_by_course.get(course.id, [])
            if after + timedelta(hours=10) <= s.starts_at <= after + timedelta(days=within_days)
            and self.slot_seats.get(s.id, 0) < s.capacity
            and (branch_id is None or s.group.branch_id == branch_id)
        ]
        if not candidates:
            return None
        return self.rng.choice(candidates[:6])

    def build_history(self, total: int):
        rng = self.rng
        org = self.org
        msgs: list[Message] = []
        status_changes: list[LeadStatusChange] = []
        events: list[BookingEvent] = []
        audits: list[AuditEvent] = []
        reminders: list[Reminder] = []
        handoffs: list[HumanHandoff] = []
        notes: list[LeadNote] = []
        tg_id = 9_100_000_000

        def add_msg(conv, sender, text, at, author=None, **extra):
            msgs.append(
                Message(
                    organization=org,
                    conversation=conv,
                    sender=sender,
                    text=text,
                    created_at=at,
                    author=author,
                    language=conv.language,
                    is_demo=sender == "ai",
                    **extra,
                )
            )

        def status(lead, frm, to, at, via="ai", by=None, reason=""):
            status_changes.append(LeadStatusChange(lead=lead, from_status=frm, to_status=to, changed_via=via, changed_by=by, created_at=at, reason=reason))

        def audit(action, summary, at, actor=None, actor_type="system", obj=None):
            audits.append(
                AuditEvent(
                    organization=org,
                    action=action,
                    summary=summary[:255],
                    created_at=at,
                    actor=actor,
                    actor_type=actor_type,
                    object_type=obj.__class__.__name__ if obj else "",
                    object_id=str(obj.pk) if obj else "",
                )
            )

        for index in range(total):
            # Har bir mijoz o'z tasodifiy oqimiga ega: "hozirgi vaqt"ga bog'liq shartlar bitta
            # mijozning tarixini o'zgartirsa ham, qolgan mijozlar ketma-ketligi siljimaydi.
            self.rng = rng = random.Random(f"{self.seed}:lead:{index}")
            d = self._pick_day()
            day = self.today - timedelta(days=self.days - 1 - d)
            created = self._rand_time(day)
            if created > self.now:
                created = self.now - timedelta(minutes=rng.randint(30, 300))
            source = rng.choices(["telegram", "webchat", "manual", "referral", "walk_in"], weights=[55, 30, 8, 5, 2])[0]
            lang = rng.choices(["uz", "ru", "en"], weights=[70, 25, 5])[0]
            course = rng.choices(self.courses, weights=[c.weight for c in COURSES])[0] if rng.random() < 0.9 else None
            branch = rng.choice(self.branches) if (course and rng.random() < 0.8) else None
            lead = Lead.objects.create(
                organization=org,
                source=source,
                language=lang,
                created_at=created,
                last_activity_at=created,
                full_name=self._name(lang) if source not in ("telegram", "webchat") or rng.random() < 0.85 else "",
                phone=demo_phone(rng) if source not in ("telegram", "webchat") or rng.random() < 0.7 else "",
                telegram_user_id=(tg_id := tg_id + rng.randint(3, 900)) if source == "telegram" else None,
                telegram_username=f"demo_user_{rng.randint(1000, 99999)}" if source == "telegram" and rng.random() < 0.7 else "",
                interested_course=course,
                branch=branch,
                goal=rng.choice(["IELTS 7.0 olish", "Chet elda o'qish", "Ish uchun", "DTM imtihoni", "Dasturchi bo'lish", "So'zlashuvni yaxshilash", ""])
                if course
                else "",
                level=rng.choice(["boshlang'ich", "o'rta", "A2", "B1", ""]) if course else "",
                preferred_time=rng.choice(["ertalab", "tushdan keyin", "kechqurun", ""]),
                assigned_to=rng.choice(self.staff) if rng.random() < 0.7 else None,
            )
            status(lead, "", "new", created, via="ai" if source in ("telegram", "webchat") else "operator")
            audit(
                "lead.created",
                f"Yangi mijoz: {lead.display_name} ({lead.get_source_display()})",
                created,
                actor_type="customer" if source in ("telegram", "webchat") else "user",
                actor=None if source in ("telegram", "webchat") else self.manager,
                obj=lead,
            )

            conv = None
            t_cursor = created
            if source in ("telegram", "webchat"):
                conv = Conversation.objects.create(
                    organization=org,
                    lead=lead,
                    channel=source,
                    external_chat_id=str(lead.telegram_user_id) if source == "telegram" else f"web_demo_{lead.id}",
                    language=lang,
                    created_at=created,
                    last_message_at=created,
                )
                cname = course.name if course else "kurs"
                q = rng.choice(QUESTION[lang]).format(course=cname) if course else rng.choice(GENERIC_Q[lang])
                add_msg(conv, "customer", q, t_cursor)
                t_cursor += timedelta(seconds=rng.randint(2, 9))
                if course:
                    groups = "\n".join(f"• {g.branch.name}: {g.schedule_label}" for g in self.groups if g.course_id == course.id)
                    add_msg(
                        conv,
                        "ai",
                        t(
                            "course_card",
                            lang,
                            name=course.name,
                            level=level_label(course.level, lang),
                            price=format_price(course, lang),
                            months=course.duration_months,
                            lessons=course.lessons_per_week,
                            minutes=course.lesson_minutes,
                            groups=groups,
                        )
                        + "\n\n"
                        + t("course_offer_trial", lang),
                        t_cursor,
                        ai_status="ok",
                    )
                else:
                    add_msg(conv, "ai", t("clarify", lang), t_cursor, ai_status="ok")

            qualified = bool(course) and rng.random() < 0.88
            if qualified:
                q_at = t_cursor + timedelta(seconds=1) if conv else created + timedelta(minutes=rng.randint(5, 120))
                status(lead, "new", "qualified", q_at)
                lead.status = "qualified"

            # Handoff (operator) holatlari
            if conv and rng.random() < 0.14:
                t_cursor += timedelta(minutes=rng.randint(1, 20))
                add_msg(conv, "customer", HANDOFF_ASK[lang], t_cursor)
                h_at = t_cursor + timedelta(seconds=2)
                add_msg(conv, "ai", t("handoff", lang), h_at, ai_status="ok")
                taken = h_at + timedelta(minutes=rng.randint(2, 28), seconds=rng.randint(0, 59))
                operator = rng.choice(self.staff)
                if taken < self.now:
                    returned = taken + timedelta(minutes=rng.randint(10, 90))
                    handoffs.append(
                        HumanHandoff(
                            organization=org,
                            conversation=conv,
                            requested_via="customer",
                            reason="Mijoz administrator so'radi",
                            status="returned" if returned < self.now else "active",
                            taken_by=operator,
                            taken_at=taken,
                            returned_by=operator if returned < self.now else None,
                            returned_at=returned if returned < self.now else None,
                            created_at=h_at,
                        )
                    )
                    add_msg(conv, "system", t("operator_joined", lang), taken - timedelta(seconds=20), kind="event")
                    add_msg(conv, "operator", OPERATOR_REPLY[lang], taken, author=operator)
                    if returned >= self.now:
                        conv.mode, conv.assigned_to = "human", operator
                    else:
                        add_msg(conv, "system", t("ai_returned", lang), returned, kind="event")
                    t_cursor = taken + timedelta(minutes=1)
                    audit(
                        "conversation.taken_over",
                        f"{operator.full_name} suhbatni oldi: {lead.display_name}",
                        taken,
                        actor=operator,
                        actor_type="user",
                        obj=conv,
                    )
                else:
                    handoffs.append(
                        HumanHandoff(organization=org, conversation=conv, requested_via="customer", reason="Mijoz administrator so'radi", created_at=h_at)
                    )
                    conv.mode, conv.needs_attention = "human", True

            booked = qualified and rng.random() < (0.75 if created > self.now - timedelta(days=10) else 0.62)
            final_status = lead.status
            if booked:
                book_at = t_cursor + timedelta(minutes=rng.randint(1, 30)) if conv else created + timedelta(hours=rng.randint(1, 30))
                if book_at > self.now:
                    book_at = self.now - timedelta(minutes=5)
                window = 12 if created > self.now - timedelta(days=10) else 7
                slot = self._find_slot(course, book_at, window, branch_id=branch.id if branch else None) or self._find_slot(course, book_at, window)
                if slot:
                    if not lead.full_name:
                        lead.full_name = self._name(lang)
                    if not lead.phone:
                        lead.phone = demo_phone(rng)
                    if conv:
                        add_msg(conv, "customer", WANT_TRIAL[lang], book_at - timedelta(seconds=40))
                        add_msg(
                            conv,
                            "ai",
                            t("slots_header", lang, course=course.name, branch=slot.group.branch.name)
                            + f"\n1) {format_slot_time(slot.starts_at, org, lang)} — "
                            + t("seats_left", lang, n=slot.capacity - self.slot_seats.get(slot.id, 0))
                            + "\n"
                            + t("slots_pick", lang),
                            book_at - timedelta(seconds=35),
                            ai_status="ok",
                        )
                        add_msg(conv, "customer", "1", book_at - timedelta(seconds=25))
                        add_msg(
                            conv,
                            "ai",
                            t(
                                "confirm_booking",
                                lang,
                                course=course.name,
                                branch=slot.group.branch.name,
                                address="",
                                when=format_slot_time(slot.starts_at, org, lang),
                                name=lead.full_name,
                            ),
                            book_at - timedelta(seconds=20),
                            ai_status="ok",
                        )
                        add_msg(conv, "customer", YES[lang], book_at - timedelta(seconds=3))
                    booking = self._make_booking(lead, slot, book_at, conv, events, audits, status_changes, reminders)
                    final_status = "trial_booked"
                    if conv:
                        add_msg(
                            conv,
                            "ai",
                            t(
                                "booked",
                                lang,
                                course=course.name,
                                branch=slot.group.branch.name,
                                address="",
                                when=format_slot_time(slot.starts_at, org, lang),
                                booking_id=booking.id,
                            ),
                            book_at + timedelta(seconds=2),
                            ai_status="ok",
                        )
                    lead.branch = slot.group.branch
                    final_status = self._resolve_booking(lead, booking, slot, events, audits, status_changes, reminders, notes, course) or final_status
            if final_status in ("qualified", "new") and created < self.now - timedelta(days=12) and rng.random() < 0.38:
                lost_at = created + timedelta(days=rng.randint(7, 20))
                if lost_at < self.now:
                    status(lead, final_status, "lost", lost_at, via="operator", by=rng.choice(self.staff), reason="Javob bermadi")
                    final_status = "lost"
            lead.status = final_status
            lead.last_activity_at = max([created] + [m.created_at for m in msgs[-14:] if m.conversation_id == (conv.id if conv else None)])
            lead.save()
            if conv:
                conv_msgs = [m for m in msgs if m.conversation_id == conv.id]
                if conv_msgs:
                    last = max(conv_msgs, key=lambda m: m.created_at)
                    conv.last_message_at = last.created_at
                    conv.last_message_preview = last.text.replace("\n", " ")[:200]
                if conv.last_message_at < self.now - timedelta(days=21) and conv.mode == "ai":
                    conv.status = "closed"
                conv.save()

        Message.objects.bulk_create(msgs, batch_size=500)
        LeadStatusChange.objects.bulk_create(status_changes, batch_size=500)
        BookingEvent.objects.bulk_create(events, batch_size=500)
        AuditEvent.objects.bulk_create(audits, batch_size=500)
        Reminder.objects.bulk_create(reminders, batch_size=500)
        HumanHandoff.objects.bulk_create(handoffs, batch_size=500)
        LeadNote.objects.bulk_create(notes, batch_size=500)
        for slot_id, seats in self.slot_seats.items():
            TrialSlot.objects.filter(pk=slot_id).update(seats_taken=seats)
        # Tasdiqlangan bronlar soni slot sig'imidan oshmaganini tekshirish
        over = TrialSlot.objects.filter(organization=org).annotate(active=Count("bookings", filter=~Q(bookings__status="cancelled"))).filter(active__gt=0)
        for s in over:
            assert s.active == s.seats_taken <= s.capacity, f"slot {s.id} sig'imi buzildi"

    def _make_booking(self, lead, slot, at, conv, events, audits, status_changes, reminders) -> TrialBooking:
        booking = TrialBooking.objects.create(
            organization=self.org,
            lead=lead,
            slot=slot,
            conversation=conv,
            channel=conv.channel if conv else "panel",
            status="confirmed",
            confirmed_at=at,
            created_at=at,
            created_by=None if conv else self.rng.choice(self.staff),
        )
        self.slot_seats[slot.id] = self.slot_seats.get(slot.id, 0) + 1
        events.append(
            BookingEvent(organization=self.org, booking=booking, event_type="confirmed", to_slot=slot, actor_type="ai" if conv else "user", occurred_at=at)
        )
        status_changes.append(
            LeadStatusChange(lead=lead, from_status=lead.status, to_status="trial_booked", changed_via="ai" if conv else "operator", created_at=at)
        )
        lead.status = "trial_booked"
        audits.append(
            AuditEvent(
                organization=self.org,
                action="booking.confirmed",
                actor_type="ai" if conv else "user",
                summary=f"{lead.display_name} — {slot.group.course.name}, {timezone.localtime(slot.starts_at, self.tz):%d.%m %H:%M}",
                created_at=at,
                object_type="TrialBooking",
                object_id=str(booking.id),
            )
        )
        lead.consent_reminders = self.rng.random() < 0.6
        lead.consent_at = at if lead.consent_reminders else None
        return booking

    def _resolve_booking(self, lead, booking, slot, events, audits, status_changes, reminders, notes, course) -> str | None:
        rng = self.rng
        now = self.now
        if slot.starts_at > now:
            if rng.random() < 0.1:
                c_at = booking.confirmed_at + (now - booking.confirmed_at) * rng.random()
                self._cancel(lead, booking, slot, c_at, events, audits, status_changes)
                return "qualified"
            if lead.consent_reminders:
                hours = 3
                reminders.append(Reminder(organization=self.org, booking=booking, scheduled_for=max(now, slot.starts_at - timedelta(hours=hours))))
            return "trial_booked"
        outcome = rng.choices(["attended", "no_show", "cancelled"], weights=[62, 20, 18])[0]
        if outcome == "cancelled":
            c_at = booking.confirmed_at + (slot.starts_at - booking.confirmed_at) * rng.uniform(0.2, 0.9)
            self._cancel(lead, booking, slot, c_at, events, audits, status_changes)
            if rng.random() < 0.3:
                new_slot = self._find_slot(course, c_at + timedelta(hours=1), within_days=10)
                if new_slot and new_slot.starts_at > c_at:
                    b2 = self._make_booking(
                        lead, new_slot, c_at + timedelta(minutes=rng.randint(5, 90)), booking.conversation, events, audits, status_changes, []
                    )
                    return self._resolve_booking(lead, b2, new_slot, events, audits, status_changes, reminders, notes, course)
            return "qualified"
        mark_at = slot.starts_at + timedelta(minutes=rng.randint(30, 180))
        if mark_at > now:
            mark_at = now - timedelta(minutes=1)
        booking.status = outcome
        booking.attendance_marked_at = mark_at
        booking.save(update_fields=["status", "attendance_marked_at"])
        events.append(BookingEvent(organization=self.org, booking=booking, event_type=outcome, actor=self.operator, actor_type="user", occurred_at=mark_at))
        audits.append(
            AuditEvent(
                organization=self.org,
                action=f"booking.{outcome}",
                actor=self.operator,
                actor_type="user",
                created_at=mark_at,
                summary=f"{lead.display_name} — {'qatnashdi' if outcome == 'attended' else 'kelmadi'}",
                object_type="TrialBooking",
                object_id=str(booking.id),
            )
        )
        if outcome == "no_show":
            if rng.random() < 0.4:
                notes.append(
                    LeadNote(
                        lead=lead, author=self.operator, text="Sinov darsiga kelmadi, qayta qo'ng'iroq qilish kerak.", created_at=mark_at + timedelta(hours=2)
                    )
                )
            return "trial_booked"
        status_changes.append(
            LeadStatusChange(
                lead=lead, from_status="trial_booked", to_status="trial_attended", changed_via="operator", changed_by=self.operator, created_at=mark_at
            )
        )
        if rng.random() < 0.55:
            e_at = mark_at + timedelta(days=rng.randint(1, 5), hours=rng.randint(0, 6))
            if e_at < now:
                group = slot.group
                Enrollment.objects.create(
                    organization=self.org,
                    lead=lead,
                    course=course,
                    group=group,
                    status="confirmed",
                    confirmed_by=self.manager,
                    confirmed_at=e_at,
                    created_at=e_at,
                )
                status_changes.append(
                    LeadStatusChange(
                        lead=lead, from_status="trial_attended", to_status="enrolled", changed_via="operator", changed_by=self.manager, created_at=e_at
                    )
                )
                audits.append(
                    AuditEvent(
                        organization=self.org,
                        action="enrollment.confirmed",
                        actor=self.manager,
                        actor_type="user",
                        created_at=e_at,
                        summary=f"{lead.display_name} — {course.name} kursiga yozildi",
                    )
                )
                return "enrolled"
        return "trial_attended"

    def _cancel(self, lead, booking, slot, at, events, audits, status_changes):
        booking.status = "cancelled"
        booking.cancelled_at = at
        booking.cancel_reason = self.rng.choice(["Vaqt to'g'ri kelmadi", "Kasal bo'lib qoldi", "Boshqa kunga ko'chirmoqchi", "Mijoz suhbatda bekor qildi"])
        booking.save(update_fields=["status", "cancelled_at", "cancel_reason"])
        self.slot_seats[slot.id] -= 1
        events.append(
            BookingEvent(
                organization=self.org, booking=booking, event_type="cancelled", from_slot=slot, actor_type="ai", reason=booking.cancel_reason, occurred_at=at
            )
        )
        status_changes.append(
            LeadStatusChange(lead=lead, from_status="trial_booked", to_status="qualified", changed_via="system", reason="Bron bekor qilindi", created_at=at)
        )
        audits.append(
            AuditEvent(
                organization=self.org,
                action="booking.cancelled",
                actor_type="ai",
                created_at=at,
                summary=f"{lead.display_name} — bron bekor qilindi",
                object_type="TrialBooking",
                object_id=str(booking.id),
            )
        )
        lead.status = "qualified"

    # ------------------------------------------------------------------ isolation org
    def build_isolation_org(self):
        self.rng = random.Random(f"{self.seed}:isolation")
        org = Organization.objects.create(name="Izolyatsiya Test Markazi", slug=ISOLATION_SLUG, timezone="Asia/Tashkent", is_demo=True)
        owner = User.objects.create_user(f"owner@isolation.{settings.DEMO_ACCOUNT_DOMAIN}", DEMO_PASSWORD, full_name="Izolyatsiya Egasi", is_demo=True)
        Membership.objects.create(user=owner, organization=org, role="owner")
        branch = Branch.objects.create(organization=org, name="Markaziy filial", address="Sintetik manzil")
        course = Course.objects.create(
            organization=org, name="Maxfiy kurs", price=Decimal("999000"), keywords=["maxfiy"], description="Faqat izolyatsiya testi uchun."
        )
        group = Group.objects.create(
            organization=org,
            course=course,
            branch=branch,
            name="MAXFIY-1",
            teacher_name="Yashirin O'qituvchi",
            days=[0, 2],
            start_time=time(10),
            end_time=time(11, 30),
        )
        start = datetime.combine(self.today + timedelta(days=3), time(10), tzinfo=self.tz)
        TrialSlot.objects.create(organization=org, group=group, starts_at=start, ends_at=start + timedelta(minutes=90), capacity=2)
        for i in range(3):
            Lead.objects.create(organization=org, source="manual", full_name=f"Izolyatsiya mijozi {i + 1}", phone=demo_phone(self.rng))
        AISettings.objects.create(organization=org)
        WidgetSettings.objects.create(organization=org, public_key=ISOLATION_WIDGET_KEY, title="Izolyatsiya")

    # ------------------------------------------------------------------ knowledge
    def build_knowledge(self):
        from apps.knowledge.services import process_document

        org = Organization.objects.get(slug=DEMO_SLUG)
        docs = [
            ("Markaz qoidalari va FAQ", "faq.md", "md", KB_FAQ, "customer"),
            ("Bepul sinov darsi haqida", "sinov-darsi.txt", "txt", KB_TRIAL, "customer"),
            ("Ichki: operatorlar uchun eslatma", "ichki-eslatma.md", "md", KB_INTERNAL, "internal"),
        ]
        for title, filename, ftype, content, visibility in docs:
            data = content.encode("utf-8")
            doc = KnowledgeDocument(
                organization=org,
                title=title,
                file_type=ftype,
                original_filename=filename,
                size_bytes=len(data),
                visibility=visibility,
                uploaded_by=self.manager,
                created_at=self.now - timedelta(days=30),
            )
            doc.file.save(filename, ContentFile(data), save=False)
            doc.save()
            process_document(doc.id)

    # ------------------------------------------------------------------ live pipeline scenarios
    def run_live_scenarios(self):
        """Haqiqiy service qatlami orqali: Telegram uslubidagi to'liq bron oqimi, veb-chat va operator suhbati."""

        from apps.conversations import inbound
        from apps.conversations import services as conv_services

        org = Organization.objects.get(slug=DEMO_SLUG)
        tg_conv = inbound.get_telegram_conversation(org, chat_id=9_900_000_001, user_id=9_900_000_001, username="demo_aziza", language="uz")
        inbound.greeting_message(tg_conv)
        script = [
            "Assalomu alaykum",
            "IELTS kursi narxi qancha?",
            "Ha, sinov darsiga yozilmoqchiman",
            "Chilonzor",
            "Kechqurun",
            "1",
            "Aziza",
            "+998 00 123 45 67",
            "Ha",
            "Ha",
        ]
        for i, text in enumerate(script):
            result = inbound.process_text(tg_conv, text, external_id=f"tg:demo-{i}")
            for reply in result.replies:
                conv_services.deliver_to_channel(result.conversation, reply)
            tg_conv = result.conversation

        web = inbound.get_webchat_conversation(org, visitor_id="web_demo_live_ru", language="ru")
        for text in ["Здравствуйте! Сколько стоит курс Python?", "Есть ли семейная скидка?"]:
            inbound.process_text(web, text)

        op_conv = inbound.get_webchat_conversation(org, visitor_id="web_demo_live_handoff", language="uz")
        inbound.process_text(op_conv, "General English kursi bo'yicha savolim bor")
        inbound.process_text(op_conv, "Administrator bilan gaplashsam bo'ladimi?")
        conv_services.take_over(op_conv, self.operator2)
        # Operator CRM kartasini to'ldiradi (sintetik ma'lumot)
        from apps.leads import services as lead_services

        op_conv.refresh_from_db()
        lead_services.update_lead(
            op_conv.lead,
            {
                "full_name": "Dilnoza R.",
                "phone": "+998 00 987 65 43",
                "goal": "Ish uchun so'zlashuv",
                "level": "A2",
                "assigned_to": self.operator2,
                "branch": self.branches[1],
            },
            actor=self.operator2,
        )
        conv_services.operator_reply(op_conv, self.operator2, "Assalomu alaykum! Men administratorman. Qaysi vaqt sizga qulay — ertalabmi yoki kechqurun?")
        inbound.process_text(op_conv, "Kechqurun, ish tugagandan keyin")

    def finalize(self):
        org = Organization.objects.get(slug=DEMO_SLUG)
        owner = User.objects.get(email=f"owner@{settings.DEMO_ACCOUNT_DOMAIN}")
        # Panel bildirishnomalari: oxirgi bronlar va operator so'rovlari
        Notification.objects.filter(organization=org).delete()
        items = []
        for b in TrialBooking.objects.filter(organization=org).select_related("lead", "slot__group__course").order_by("-confirmed_at")[:5]:
            items.append(
                Notification(
                    organization=org,
                    user=owner,
                    kind="new_booking",
                    title="Yangi sinov darsi broni",
                    body=f"{b.lead.display_name} — {b.slot.group.course.name}",
                    link=f"/bookings?booking={b.id}",
                    created_at=b.confirmed_at,
                )
            )
        for h in HumanHandoff.objects.filter(organization_id=org.id, status="requested").select_related("conversation__lead")[:3]:
            items.append(
                Notification(
                    organization=org,
                    user=owner,
                    kind="handoff_requested",
                    title="Mijoz operator kutmoqda",
                    body=h.conversation.lead.display_name,
                    link=f"/conversations/{h.conversation_id}",
                    created_at=h.created_at,
                )
            )
        for i, n in enumerate(sorted(items, key=lambda x: x.created_at, reverse=True)):
            n.is_read = i >= 4
        Notification.objects.bulk_create(items)
