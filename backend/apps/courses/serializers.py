from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.courses.models import Course, Group, TrialSlot
from apps.organizations.models import Branch


class OrgPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Faqat joriy tashkilot ichidagi obyektlarni qabul qiladi (boshqa tashkilot ID'si — "topilmadi")."""

    def get_queryset(self):
        org = self.context.get("organization")
        return self.queryset.filter(organization=org) if org is not None else self.queryset.none()


class CourseSerializer(serializers.ModelSerializer):
    groups_count = serializers.IntegerField(read_only=True, required=False)
    upcoming_slots = serializers.IntegerField(read_only=True, required=False)
    level_label = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "description",
            "level",
            "level_label",
            "teaching_language",
            "price",
            "currency",
            "price_period",
            "duration_months",
            "lessons_per_week",
            "lesson_minutes",
            "keywords",
            "is_active",
            "groups_count",
            "upcoming_slots",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "currency"]

    def validate_name(self, value):
        org = self.context["organization"]
        qs = Course.objects.filter(organization=org, name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bunday nomli kurs mavjud.")
        return value.strip()

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Ro'yxat bo'lishi kerak.")
        return [str(v).strip().lower()[:40] for v in value if str(v).strip()][:20]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Narx manfiy bo'lishi mumkin emas.")
        return value


class GroupSerializer(serializers.ModelSerializer):
    course_id = OrgPrimaryKeyRelatedField(source="course", queryset=Course.objects.all())
    branch_id = OrgPrimaryKeyRelatedField(source="branch", queryset=Branch.objects.all())
    course_name = serializers.CharField(source="course.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    schedule_label = serializers.CharField(read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "course_id",
            "course_name",
            "branch_id",
            "branch_name",
            "teacher_name",
            "days",
            "start_time",
            "end_time",
            "schedule_label",
            "capacity",
            "enrolled_count",
            "start_date",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "enrolled_count"]

    def validate_days(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Kamida bitta hafta kunini tanlang.")
        days = sorted({int(d) for d in value})
        if any(d < 0 or d > 6 for d in days):
            raise serializers.ValidationError("Hafta kuni 0–6 oralig'ida bo'lishi kerak.")
        return days

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "Tugash vaqti boshlanishdan keyin bo'lishi kerak."})
        org = self.context["organization"]
        name = attrs.get("name")
        if name:
            qs = Group.objects.filter(organization=org, name__iexact=name.strip())
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"name": "Bunday nomli guruh mavjud."})
        return attrs


class TrialSlotSerializer(serializers.ModelSerializer):
    group_id = OrgPrimaryKeyRelatedField(source="group", queryset=Group.objects.all())
    group_name = serializers.CharField(source="group.name", read_only=True)
    course_id = serializers.IntegerField(source="group.course_id", read_only=True)
    course_name = serializers.CharField(source="group.course.name", read_only=True)
    branch_id = serializers.IntegerField(source="group.branch_id", read_only=True)
    branch_name = serializers.CharField(source="group.branch.name", read_only=True)
    seats_left = serializers.IntegerField(read_only=True)
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = TrialSlot
        fields = [
            "id",
            "group_id",
            "group_name",
            "course_id",
            "course_name",
            "branch_id",
            "branch_name",
            "starts_at",
            "ends_at",
            "capacity",
            "seats_taken",
            "seats_left",
            "status",
            "notes",
            "is_past",
            "created_at",
        ]
        read_only_fields = ["id", "seats_taken", "created_at"]

    def get_is_past(self, obj) -> bool:
        return obj.starts_at <= timezone.now()

    def validate(self, attrs):
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and not ends:
            group = attrs.get("group") or getattr(self.instance, "group", None)
            minutes = group.course.lesson_minutes if group else 90
            attrs["ends_at"] = starts + timedelta(minutes=minutes)
            ends = attrs["ends_at"]
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": "Tugash vaqti boshlanishdan keyin bo'lishi kerak."})
        if self.instance is None and starts and starts <= timezone.now():
            raise serializers.ValidationError({"starts_at": "O'tgan vaqtga sinov darsi qo'shib bo'lmaydi."})
        capacity = attrs.get("capacity")
        if self.instance is not None and capacity is not None and capacity < self.instance.seats_taken:
            raise serializers.ValidationError({"capacity": f"Sig'im band joylar sonidan ({self.instance.seats_taken}) kam bo'lishi mumkin emas."})
        return attrs


class GenerateSlotsSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    weeks = serializers.IntegerField(min_value=1, max_value=8, default=2)
    capacity = serializers.IntegerField(min_value=1, max_value=50, default=4)
