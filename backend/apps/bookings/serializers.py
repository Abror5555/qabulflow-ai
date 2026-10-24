from rest_framework import serializers

from apps.bookings.models import BookingEvent, TrialBooking


class BookingEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default=None)
    label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = BookingEvent
        fields = ["id", "event_type", "label", "actor_type", "actor_name", "reason", "occurred_at", "from_slot_id", "to_slot_id"]


class TrialBookingSerializer(serializers.ModelSerializer):
    lead_name = serializers.CharField(source="lead.display_name", read_only=True)
    lead_phone = serializers.CharField(source="lead.phone", read_only=True)
    slot_id = serializers.IntegerField(read_only=True)
    starts_at = serializers.DateTimeField(source="slot.starts_at", read_only=True)
    ends_at = serializers.DateTimeField(source="slot.ends_at", read_only=True)
    course_id = serializers.IntegerField(source="slot.group.course_id", read_only=True)
    course_name = serializers.CharField(source="slot.group.course.name", read_only=True)
    group_name = serializers.CharField(source="slot.group.name", read_only=True)
    branch_id = serializers.IntegerField(source="slot.group.branch_id", read_only=True)
    branch_name = serializers.CharField(source="slot.group.branch.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    channel_label = serializers.CharField(source="get_channel_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)
    can_mark_attendance = serializers.SerializerMethodField()

    class Meta:
        model = TrialBooking
        fields = [
            "id",
            "lead_id",
            "lead_name",
            "lead_phone",
            "slot_id",
            "starts_at",
            "ends_at",
            "course_id",
            "course_name",
            "group_name",
            "branch_id",
            "branch_name",
            "status",
            "status_label",
            "channel",
            "channel_label",
            "conversation_id",
            "confirmed_at",
            "cancelled_at",
            "cancel_reason",
            "attendance_marked_at",
            "reschedule_count",
            "created_by_name",
            "notes",
            "can_mark_attendance",
        ]

    def get_can_mark_attendance(self, obj) -> bool:
        from django.utils import timezone

        return obj.status != "cancelled" and obj.slot.starts_at <= timezone.now()


class TrialBookingDetailSerializer(TrialBookingSerializer):
    events = BookingEventSerializer(many=True, read_only=True)

    class Meta(TrialBookingSerializer.Meta):
        fields = TrialBookingSerializer.Meta.fields + ["events"]


class CreateBookingSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField()
    slot_id = serializers.IntegerField()
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CancelBookingSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RescheduleSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()


class AttendanceSerializer(serializers.Serializer):
    attended = serializers.BooleanField()
