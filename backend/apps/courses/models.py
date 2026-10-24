from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class Course(TimeStampedModel):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Boshlang'ich"
        INTERMEDIATE = "intermediate", "O'rta"
        ADVANCED = "advanced", "Yuqori"
        ALL = "all", "Barcha darajalar"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="courses")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.ALL)
    teaching_language = models.CharField(max_length=32, default="O'zbek")
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="UZS")
    price_period = models.CharField(max_length=16, default="month", choices=[("month", "oyiga"), ("course", "kurs uchun")])
    duration_months = models.PositiveSmallIntegerField(default=3)
    lessons_per_week = models.PositiveSmallIntegerField(default=3)
    lesson_minutes = models.PositiveSmallIntegerField(default=90)
    keywords = models.JSONField(default=list, blank=True, help_text="Suhbatda kursni aniqlash uchun kalit so'zlar")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="uniq_course_name_per_org")]

    def __str__(self) -> str:
        return self.name


class Group(TimeStampedModel):
    WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="groups")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="groups")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="groups")
    name = models.CharField(max_length=120)
    teacher_name = models.CharField(max_length=120, blank=True, help_text="Ichki ma'lumot: mijozga ko'rsatilmaydi")
    days = models.JSONField(default=list, help_text="Hafta kunlari: 0=Dushanba ... 6=Yakshanba")
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=12, validators=[MinValueValidator(1)])
    enrolled_count = models.PositiveSmallIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["course__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_group_name_per_org"),
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="group_time_order"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def schedule_label(self) -> str:
        days = ", ".join(self.WEEKDAYS[d] for d in sorted(self.days or []) if 0 <= d <= 6)
        return f"{days} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class TrialSlot(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        CANCELLED = "cancelled", "Bekor qilingan"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="trial_slots")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="trial_slots")
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    capacity = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    seats_taken = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["organization", "starts_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(seats_taken__lte=F("capacity")), name="slot_capacity_not_exceeded"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="slot_time_order"),
        ]

    def __str__(self) -> str:
        return f"{self.group} @ {self.starts_at:%Y-%m-%d %H:%M}"

    @property
    def seats_left(self) -> int:
        return max(0, self.capacity - self.seats_taken)
