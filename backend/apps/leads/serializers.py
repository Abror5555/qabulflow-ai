from rest_framework import serializers

from apps.accounts.models import User
from apps.bookings.models import Enrollment, TrialBooking
from apps.core.utils import normalize_phone
from apps.courses.models import Course
from apps.courses.serializers import OrgPrimaryKeyRelatedField
from apps.leads.models import Lead, LeadNote, LeadStatusChange
from apps.organizations.models import Branch


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "initials"]


class LeadListSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    interested_course_name = serializers.CharField(source="interested_course.name", read_only=True, default=None)
    assigned_to = UserBriefSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "display_name",
            "full_name",
            "phone",
            "phone_verified",
            "telegram_username",
            "language",
            "source",
            "source_label",
            "status",
            "status_label",
            "branch_id",
            "branch_name",
            "interested_course_id",
            "interested_course_name",
            "goal",
            "level",
            "preferred_time",
            "assigned_to",
            "consent_reminders",
            "created_at",
            "last_activity_at",
        ]


class LeadWriteSerializer(serializers.ModelSerializer):
    branch_id = OrgPrimaryKeyRelatedField(source="branch", queryset=Branch.objects.all(), required=False, allow_null=True)
    interested_course_id = OrgPrimaryKeyRelatedField(source="interested_course", queryset=Course.objects.all(), required=False, allow_null=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(source="assigned_to", queryset=User.objects.none(), required=False, allow_null=True)

    class Meta:
        model = Lead
        fields = [
            "full_name",
            "phone",
            "phone_verified",
            "language",
            "source",
            "branch_id",
            "interested_course_id",
            "goal",
            "level",
            "preferred_time",
            "assigned_to_id",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        org = self.context.get("organization")
        if org is not None:
            self.fields["assigned_to_id"].queryset = User.objects.filter(memberships__organization=org, memberships__is_active=True)

    def validate_phone(self, value):
        if not value:
            return ""
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")
        return normalized

    def validate_source(self, value):
        if self.instance is None and value in ("telegram", "webchat"):
            raise serializers.ValidationError("Telegram/veb-chat leadlari faqat kanal orqali yaratiladi.")
        return value

    def validate(self, attrs):
        if self.instance is None and not (attrs.get("full_name") or "").strip():
            raise serializers.ValidationError({"full_name": "Ism majburiy."})
        return attrs


class LeadNoteSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = LeadNote
        fields = ["id", "text", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class LeadStatusChangeSerializer(serializers.ModelSerializer):
    changed_by = UserBriefSerializer(read_only=True)
    from_label = serializers.SerializerMethodField()
    to_label = serializers.SerializerMethodField()

    class Meta:
        model = LeadStatusChange
        fields = ["id", "from_status", "from_label", "to_status", "to_label", "changed_by", "changed_via", "reason", "created_at"]

    def get_from_label(self, obj) -> str:
        return Lead.Status(obj.from_status).label if obj.from_status in Lead.Status.values else ""

    def get_to_label(self, obj) -> str:
        return Lead.Status(obj.to_status).label if obj.to_status in Lead.Status.values else obj.to_status


class LeadBookingSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="slot.group.course.name", read_only=True)
    branch_name = serializers.CharField(source="slot.group.branch.name", read_only=True)
    starts_at = serializers.DateTimeField(source="slot.starts_at", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TrialBooking
        fields = ["id", "status", "status_label", "course_name", "branch_name", "starts_at", "channel", "confirmed_at", "cancelled_at"]


class EnrollmentSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)
    lead_name = serializers.CharField(source="lead.display_name", read_only=True)
    confirmed_by = UserBriefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "lead_id",
            "lead_name",
            "course_id",
            "course_name",
            "group_id",
            "group_name",
            "status",
            "status_label",
            "confirmed_by",
            "confirmed_at",
            "notes",
            "created_at",
        ]


class LeadDetailSerializer(LeadListSerializer):
    notes = LeadNoteSerializer(many=True, read_only=True)
    status_history = LeadStatusChangeSerializer(source="status_changes", many=True, read_only=True)
    bookings = LeadBookingSerializer(source="trial_bookings", many=True, read_only=True)
    enrollments = EnrollmentSerializer(many=True, read_only=True)
    conversations = serializers.SerializerMethodField()

    class Meta(LeadListSerializer.Meta):
        fields = LeadListSerializer.Meta.fields + ["notes", "status_history", "bookings", "enrollments", "conversations", "telegram_user_id", "consent_at"]

    def get_conversations(self, obj) -> list[dict]:
        return [
            {"id": c.id, "channel": c.channel, "mode": c.mode, "last_message_at": c.last_message_at, "preview": c.last_message_preview}
            for c in obj.conversations.exclude(channel="test").order_by("-last_message_at")
        ]


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Lead.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AssignSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(allow_null=True)


class EnrollSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    group_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)
