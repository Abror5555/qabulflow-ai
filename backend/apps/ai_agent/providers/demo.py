"""DEMO_MODE uchun deterministik dialog agenti.

Bu haqiqiy LLM EMAS. U qat'iy qoidalar asosida ishlaydi, lekin real agent bilan bir xil
tool'lardan (ToolExecutor) foydalanadi — shuning uchun narx, jadval, bo'sh joy va bron
haqiqiy bazadan olinadi va bron qoidalari (tasdiq, sig'im, egalik) to'liq tekshiriladi.
Har bir javob Message.is_demo=True bilan belgilanadi.
"""

from __future__ import annotations

import difflib
import re

from apps.ai_agent import nlu
from apps.ai_agent.texts import t
from apps.ai_agent.tools import ToolExecutor
from apps.core.utils import extract_phone
from apps.courses.models import Course, Group

CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "j",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "x",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sh",
        "ъ": "",
        "ы": "i",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ў": "o'",
        "қ": "q",
        "ғ": "g'",
        "ҳ": "h",
    }
)
NAME_PREFIX = re.compile(r"^(mening ismim|ismim|men|меня зовут|моё имя|мое имя|я|my name is|i am|i'm|name)\s*[:,-]?\s*", re.IGNORECASE)


def translit(text: str) -> str:
    return nlu.normalize(text).translate(CYR_TO_LAT)


class DemoAgent:
    def __init__(self, executor: ToolExecutor, ai_settings):
        self.x = executor
        self.settings = ai_settings
        self.ctx = executor.ctx

    # ------------------------------------------------------------------ utils
    @property
    def s(self) -> dict:
        return self.x.state

    @property
    def lang(self) -> str:
        return self.ctx.lang

    def _t(self, key: str, **kw) -> str:
        return t(key, self.lang, **kw)

    def _set_stage(self, stage: str | None) -> None:
        if stage:
            self.s["stage"] = stage
        else:
            self.s.pop("stage", None)

    def _match_course(self, text: str) -> Course | None:
        norm = nlu.normalize(text)
        lat = translit(text)
        best, best_len = None, 0
        for course in Course.objects.filter(organization=self.ctx.organization, is_active=True):
            keys = [k.lower() for k in (course.keywords or [])] + [course.name.lower()]
            for k in keys:
                if not k:
                    continue
                pattern = r"(?<![\w])" + re.escape(k)
                if (re.search(pattern, norm) or re.search(pattern, lat)) and len(k) > best_len:
                    best, best_len = course, len(k)
        return best

    def _course_branches(self, course_id: int) -> list[dict]:
        rows = (
            Group.objects.filter(organization=self.ctx.organization, course_id=course_id, is_active=True, branch__is_active=True)
            .values("branch_id", "branch__name")
            .distinct()
            .order_by("branch__name")
        )
        return [{"branch_id": r["branch_id"], "name": r["branch__name"]} for r in rows]

    def _match_branch(self, text: str, options: list[dict]) -> dict | None:
        n = nlu.pick_number(text, len(options))
        if n:
            return options[n - 1]
        lat_tokens = re.findall(r"[\w']+", translit(text))
        for opt in options:
            name_tokens = re.findall(r"[\w']+", translit(opt["name"]))
            for nt in name_tokens:
                if len(nt) < 4:
                    continue
                for tok in lat_tokens:
                    if tok.startswith(nt[:5]) or difflib.SequenceMatcher(None, tok, nt).ratio() >= 0.72:
                        return opt
        return None

    # ------------------------------------------------------------------ entry
    def respond(self, text: str) -> str:
        text = (text or "").strip()
        stage = self.s.get("stage")
        intents = nlu.detect_intents(text)

        if nlu.has_any(text, [k.lower() for k in (self.settings.handoff_keywords or [])]):
            return self._handoff("Mijoz administrator bilan gaplashmoqchi")

        if stage == "await_confirm":
            return self._on_confirm(text)
        if stage == "await_cancel_confirm":
            return self._on_cancel_confirm(text)
        if stage == "await_reminder":
            reply = self._on_reminder(text)
            if reply:
                return reply
        if "my_bookings" in intents:
            return self._my_bookings()
        if "cancel" in intents:
            return self._start_cancel()
        if stage == "await_cancel_pick":
            reply = self._on_cancel_pick(text)
            if reply:
                return reply
        if stage == "await_slot":
            reply = self._on_slot_pick(text)
            if reply:
                return reply
        if stage == "await_name":
            return self._on_name(text)
        if stage == "await_phone":
            return self._on_phone(text)
        if stage == "await_branch":
            reply = self._on_branch(text)
            if reply:
                return reply
        if stage == "await_time":
            reply = self._on_time(text)
            if reply:
                return reply
        if stage == "await_trial_interest":
            if nlu.is_affirmative(text):
                return self._start_booking_flow()
            if nlu.is_negative(text):
                self._set_stage(None)
                return self._t("anything_else")

        course = self._match_course(text)
        if not course and stage == "await_course":
            options = self.s.get("course_options") or []
            n = nlu.pick_number(text, len(options))
            if n:
                course = Course.objects.filter(organization=self.ctx.organization, pk=options[n - 1], is_active=True).first()
        if course:
            if self.s.get("course_id") != course.id:
                self.s.pop("branch_id", None)
                self.s.pop("part_of_day", None)
            self.s["course_id"] = course.id
            self.x.execute("update_lead", {"interested_course_id": course.id})
            self.s["failed_attempts"] = 0

        if "booking" in intents:
            self.s["failed_attempts"] = 0
            if self.s.get("course_id"):
                return self._start_booking_flow()
            return self._ask_course_for_trial()
        if course:
            return self._course_info(course.id)
        if "price" in intents or "courses" in intents:
            self.s["failed_attempts"] = 0
            return self._courses_overview()
        if "branches" in intents:
            self.s["failed_attempts"] = 0
            return self._branches()
        if "schedule" in intents:
            self.s["failed_attempts"] = 0
            return self._schedule_overview()
        if "greeting" in intents and len(nlu.words(text)) <= 4:
            self._set_stage(None)
            return self.settings.greeting_for(self.lang, self.ctx.organization.name) + "\n\n" + self._t("menu_hint")
        if "thanks" in intents:
            return self._t("thanks_reply")
        return self._knowledge_or_clarify(text)

    # ------------------------------------------------------------------ blocks
    def _handoff(self, reason: str) -> str:
        from apps.ai_agent.services import in_working_hours, working_hours_label

        self.x.execute("request_human_handoff", {"reason": reason})
        self._set_stage(None)
        text = self._t("handoff")
        if self.settings.handoff_outside_hours_notice and not in_working_hours(self.settings, self.ctx.now):
            text += self._t("handoff_outside_hours", hours=working_hours_label(self.settings, self.lang))
        return text

    def _knowledge_or_clarify(self, text: str) -> str:
        res = self.x.execute("search_knowledge", {"query": text})
        results = res.get("results") or []
        if results:
            top = results[0]
            self.s["failed_attempts"] = 0
            source = top["document_title"] + (
                f", {top['page']}-bet" if top.get("page") and self.lang == "uz" else (f", p. {top['page']}" if top.get("page") else "")
            )
            return self._t("knowledge_answer", snippet=top["snippet"], source=source)
        failed = int(self.s.get("failed_attempts", 0)) + 1
        self.s["failed_attempts"] = failed
        if failed >= self.settings.handoff_after_failed_attempts:
            self.s["failed_attempts"] = 0
            return self._handoff("AI savolga javob topa olmadi")
        return self._t("clarify")

    def _courses_overview(self) -> str:
        res = self.x.execute("list_courses", {})
        courses = res.get("courses") or []
        if not courses:
            return self._t("no_courses")
        lines = [self._t("courses_header")]
        for i, c in enumerate(courses, start=1):
            branches = ", ".join(c["branches"]) if c["branches"] else "—"
            lines.append(f"{i}) {c['name']} — {c['price_label']} ({branches})")
        lines.append("")
        lines.append(self._t("which_course"))
        self.s["course_options"] = [c["course_id"] for c in courses]
        self._set_stage("await_course")
        return "\n".join(lines)

    def _ask_course_for_trial(self) -> str:
        res = self.x.execute("list_courses", {})
        courses = res.get("courses") or []
        if not courses:
            return self._t("no_courses")
        lines = [self._t("ask_trial")]
        for i, c in enumerate(courses, start=1):
            lines.append(f"{i}) {c['name']}")
        self.s["course_options"] = [c["course_id"] for c in courses]
        self.s["want_trial"] = True
        self._set_stage("await_course")
        return "\n".join(lines)

    def _course_info(self, course_id: int) -> str:
        res = self.x.execute("get_course_details", {"course_id": course_id})
        if not res.get("ok"):
            return self._t("no_courses")
        c = res["course"]
        groups = "\n".join(f"• {g['branch']}: {g['schedule']}" for g in c["groups"]) or self._t("no_groups")
        card = self._t(
            "course_card",
            name=c["name"],
            level=c["level"],
            price=c["price_label"],
            months=c["duration_months"],
            lessons=c["lessons_per_week"],
            minutes=c["lesson_minutes"],
            groups=groups,
        )
        if self.s.pop("want_trial", False):
            return card + "\n\n" + self._start_booking_flow()
        self._set_stage("await_trial_interest")
        return card + "\n\n" + self._t("course_offer_trial")

    def _branches(self) -> str:
        res = self.x.execute("list_branches", {})
        lines = [self._t("branches_header")]
        for b in res.get("branches", []):
            extra = f" ({b['landmark']})" if b.get("landmark") else ""
            lines.append(f"📍 {b['name']} — {b['address']}{extra}")
        return "\n".join(lines)

    def _schedule_overview(self) -> str:
        if self.s.get("course_id"):
            return self._course_info(self.s["course_id"])
        res = self.x.execute("list_courses", {})
        lines = []
        for c in res.get("courses", []):
            det = self.x.execute("get_course_details", {"course_id": c["course_id"]})
            groups = det.get("course", {}).get("groups", [])
            lines.append(f"📚 {c['name']}")
            lines.extend(f"   • {g['branch']}: {g['schedule']}" for g in groups[:4])
        lines.append("")
        lines.append(self._t("course_offer_trial"))
        self._set_stage("await_course")
        self.s["want_trial"] = True
        return "\n".join(lines)

    # ------------------------------------------------------------------ booking flow
    def _start_booking_flow(self) -> str:
        course_id = self.s.get("course_id")
        if not course_id:
            return self._ask_course_for_trial()
        if not self.s.get("branch_id"):
            options = self._course_branches(course_id)
            if not options:
                self._set_stage(None)
                return self._t("no_slots")
            lead_branch = self.ctx.lead.branch_id
            if lead_branch and any(o["branch_id"] == lead_branch for o in options):
                self.s["branch_id"] = lead_branch
            elif len(options) == 1:
                self.s["branch_id"] = options[0]["branch_id"]
            else:
                self.s["branch_options"] = options
                self._set_stage("await_branch")
                lines = [self._t("ask_branch")] + [f"{i}) {o['name']}" for i, o in enumerate(options, start=1)]
                return "\n".join(lines)
        if not self.s.get("part_of_day"):
            self._set_stage("await_time")
            return self._t("ask_time")
        return self._offer_slots()

    def _offer_slots(self) -> str:
        args = {"course_id": self.s["course_id"], "branch_id": self.s["branch_id"], "part_of_day": self.s.get("part_of_day", "any")}
        res = self.x.execute("check_trial_availability", args)
        slots = res.get("slots") or []
        if not slots and args["part_of_day"] != "any":
            args["part_of_day"] = "any"
            res = self.x.execute("check_trial_availability", args)
            slots = res.get("slots") or []
        slots = slots[: self.settings.max_slots_to_offer]
        if not slots:
            self._set_stage(None)
            return self._t("no_slots")
        self.s["offered_slots"] = [sl["slot_id"] for sl in slots]
        self._set_stage("await_slot")
        lines = [self._t("slots_header", course=slots[0]["course"], branch=slots[0]["branch"])]
        for i, sl in enumerate(slots, start=1):
            lines.append(f"{i}) {sl['label']} — {self._t('seats_left', n=sl['seats_left'])}")
        lines.append(self._t("slots_pick"))
        return "\n".join(lines)

    def _on_branch(self, text: str) -> str | None:
        options = self.s.get("branch_options") or self._course_branches(self.s.get("course_id") or 0)
        choice = self._match_branch(text, options)
        if not choice:
            return None
        self.s["branch_id"] = choice["branch_id"]
        self.x.execute("update_lead", {"branch_id": choice["branch_id"]})
        part = nlu.detect_part_of_day(text)
        if part:
            self.s["part_of_day"] = part
        return self._start_booking_flow()

    def _on_time(self, text: str) -> str | None:
        part = nlu.detect_part_of_day(text)
        if not part:
            return None
        self.s["part_of_day"] = part
        self.x.execute(
            "update_lead", {"preferred_time": {"morning": "ertalab", "afternoon": "tushdan keyin", "evening": "kechqurun", "any": "farqi yo'q"}[part]}
        )
        return self._offer_slots()

    def _on_slot_pick(self, text: str) -> str | None:
        offered = self.s.get("offered_slots") or []
        n = nlu.pick_number(text, len(offered))
        if not n:
            part = nlu.detect_part_of_day(text)
            if part:
                self.s["part_of_day"] = part
                return self._offer_slots()
            return None
        self.s["selected_slot"] = offered[n - 1]
        return self._proceed_contact()

    def _proceed_contact(self) -> str:
        lead = self.ctx.lead
        if not lead.full_name:
            self._set_stage("await_name")
            return self._t("ask_name")
        if self.settings.ask_phone_before_booking and not lead.phone:
            self._set_stage("await_phone")
            return self._t("ask_phone")
        return self._propose()

    def _on_name(self, text: str) -> str:
        name = NAME_PREFIX.sub("", text.strip()).strip(" .!,")
        if not re.fullmatch(r"[^\W\d_][^\W\d_'\- ]{0,40}( [^\W\d_][^\W\d_'\- ]{0,40}){0,3}", name or "", re.UNICODE):
            return self._t("invalid_name")
        self.x.execute("update_lead", {"full_name": name.title() if name.islower() else name})
        return self._proceed_contact()

    def _on_phone(self, text: str) -> str:
        phone = extract_phone(text)
        if not phone:
            return self._t("invalid_phone")
        res = self.x.execute("update_lead", {"phone": phone})
        if not res.get("ok"):
            return self._t("invalid_phone")
        return self._proceed_contact()

    def _summary_kwargs(self, data: dict) -> dict:
        address = data.get("address") or ""
        return {
            "course": data["course"],
            "branch": data["branch"],
            "address": f", {address}" if address else "",
            "when": data["label"],
            "name": data.get("name") or self.ctx.lead.full_name or "—",
        }

    def _propose(self) -> str:
        slot_id = self.s.get("selected_slot")
        res = self.x.execute("create_trial_booking", {"slot_id": slot_id})
        if res.get("status") == "confirmation_required":
            self._set_stage("await_confirm")
            return self._t("confirm_booking", **self._summary_kwargs(res["summary"]))
        if res.get("status") == "phone_required":
            self._set_stage("await_phone")
            return self._t("ask_phone")
        if res.get("error") == "already_booked":
            self._set_stage(None)
            return self._t("already_booked", booking_id=res.get("booking_id"))
        return self._t("booking_failed", reason=res.get("message", "")) + "\n\n" + self._offer_slots()

    def _on_confirm(self, text: str) -> str:
        slot_id = self.s.get("selected_slot")
        if nlu.is_affirmative(text):
            res = self.x.execute("create_trial_booking", {"slot_id": slot_id, "customer_confirmed": True})
            if res.get("ok"):
                booking = res["booking"]
                for key in ("selected_slot", "offered_slots", "part_of_day"):
                    self.s.pop(key, None)
                if res.get("test_mode"):
                    self._set_stage(None)
                    return self._t("test_mode_booking", slot_id=booking["slot_id"])
                text_out = self._t("booked", booking_id=booking["booking_id"], **self._summary_kwargs(booking))
                if self.ctx.lead.consent_reminders:
                    self._set_stage(None)
                    return text_out
                self._set_stage("await_reminder")
                return text_out + "\n\n" + self._t("ask_reminder")
            if res.get("error") == "already_booked":
                self._set_stage(None)
                return self._t("already_booked", booking_id=res.get("booking_id"))
            if res.get("status") == "confirmation_required":
                return self._t("confirm_booking", **self._summary_kwargs(res["summary"]))
            return self._t("booking_failed", reason=res.get("message", "")) + "\n\n" + self._offer_slots()
        if nlu.is_negative(text):
            self.s.pop("pending_booking", None)
            return self._t("booking_declined") + "\n\n" + self._offer_slots()
        return self._t("confirm_again")

    def _on_reminder(self, text: str) -> str | None:
        if nlu.is_affirmative(text):
            self.x.execute("update_lead", {"consent_reminders": True})
            self._set_stage(None)
            return self._t("reminder_on")
        if nlu.is_negative(text):
            self._set_stage(None)
            return self._t("reminder_off")
        self._set_stage(None)
        return None

    # ------------------------------------------------------------------ my bookings / cancel
    def _booking_line(self, b: dict) -> str:
        return f"#{b['booking_id']} · {b['course']} · {b['branch']} · {b['label']}"

    def _my_bookings(self) -> str:
        res = self.x.execute("list_my_bookings", {})
        bookings = res.get("bookings") or []
        self._set_stage(None)
        if not bookings:
            return self._t("no_bookings")
        return "\n".join([self._t("my_bookings_header")] + [f"{i}) {self._booking_line(b)}" for i, b in enumerate(bookings, start=1)])

    def _start_cancel(self) -> str:
        res = self.x.execute("list_my_bookings", {})
        bookings = res.get("bookings") or []
        if not bookings:
            self._set_stage(None)
            return self._t("no_bookings")
        if len(bookings) == 1:
            return self._ask_cancel(bookings[0]["booking_id"])
        self.s["cancel_options"] = [b["booking_id"] for b in bookings]
        self._set_stage("await_cancel_pick")
        return "\n".join([self._t("cancel_which")] + [f"{i}) {self._booking_line(b)}" for i, b in enumerate(bookings, start=1)])

    def _on_cancel_pick(self, text: str) -> str | None:
        options = self.s.get("cancel_options") or []
        n = nlu.pick_number(text, len(options))
        if not n:
            return None
        return self._ask_cancel(options[n - 1])

    def _ask_cancel(self, booking_id: int) -> str:
        res = self.x.execute("cancel_trial_booking", {"booking_id": booking_id})
        if res.get("status") == "confirmation_required":
            self.s["cancel_booking_id"] = booking_id
            self._set_stage("await_cancel_confirm")
            return self._t("cancel_confirm", summary=self._booking_line(res["summary"]))
        self._set_stage(None)
        return self._t("no_bookings")

    def _on_cancel_confirm(self, text: str) -> str:
        booking_id = self.s.get("cancel_booking_id")
        if nlu.is_affirmative(text):
            res = self.x.execute("cancel_trial_booking", {"booking_id": booking_id, "customer_confirmed": True})
            self._set_stage(None)
            if res.get("ok"):
                return self._t("cancelled", booking_id=booking_id)
            return self._t("clarify")
        self.s.pop("pending_cancel", None)
        self._set_stage(None)
        return self._t("cancel_kept")
