from rest_framework import serializers

from apps.conversations.models import Attachment, Conversation, HumanHandoff, Message
from apps.leads.serializers import UserBriefSerializer


class AttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "kind", "content_type", "size_bytes", "duration_seconds", "download_url"]

    def get_download_url(self, obj) -> str:
        return f"/api/attachments/{obj.id}/download/"


class MessageSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "author",
            "kind",
            "text",
            "language",
            "transcript_status",
            "transcript_confidence",
            "is_demo",
            "ai_status",
            "sources",
            "tool_trace",
            "delivery_status",
            "attachments",
            "created_at",
        ]


class HandoffSerializer(serializers.ModelSerializer):
    taken_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = HumanHandoff
        fields = ["id", "requested_via", "reason", "status", "taken_by", "taken_at", "returned_at", "created_at"]


class ConversationListSerializer(serializers.ModelSerializer):
    lead_id = serializers.IntegerField(read_only=True)
    lead_name = serializers.CharField(source="lead.display_name", read_only=True)
    lead_status = serializers.CharField(source="lead.status", read_only=True)
    lead_status_label = serializers.CharField(source="lead.get_status_display", read_only=True)
    assigned_to = UserBriefSerializer(read_only=True)
    channel_label = serializers.CharField(source="get_channel_display", read_only=True)
    unanswered = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "lead_id",
            "lead_name",
            "lead_status",
            "lead_status_label",
            "channel",
            "channel_label",
            "status",
            "mode",
            "assigned_to",
            "language",
            "needs_attention",
            "last_message_at",
            "last_message_preview",
            "unanswered",
            "created_at",
        ]

    def get_unanswered(self, obj) -> bool:
        return getattr(obj, "last_sender", None) == Message.Sender.CUSTOMER


class ConversationDetailSerializer(ConversationListSerializer):
    handoffs = HandoffSerializer(many=True, read_only=True)
    lead = serializers.SerializerMethodField()
    state_summary = serializers.SerializerMethodField()

    class Meta(ConversationListSerializer.Meta):
        fields = ConversationListSerializer.Meta.fields + ["handoffs", "lead", "state_summary"]

    def get_lead(self, obj) -> dict:
        lead = obj.lead
        bookings = [
            {
                "id": b.id,
                "status": b.status,
                "status_label": b.get_status_display(),
                "course_name": b.slot.group.course.name,
                "branch_name": b.slot.group.branch.name,
                "starts_at": serializers.DateTimeField().to_representation(b.slot.starts_at),
            }
            for b in lead.trial_bookings.select_related("slot__group__course", "slot__group__branch").order_by("-confirmed_at")[:5]
        ]
        return {
            "id": lead.id,
            "display_name": lead.display_name,
            "full_name": lead.full_name,
            "phone": lead.phone,
            "telegram_username": lead.telegram_username,
            "source": lead.source,
            "source_label": lead.get_source_display(),
            "status": lead.status,
            "status_label": lead.get_status_display(),
            "language": lead.language,
            "goal": lead.goal,
            "level": lead.level,
            "preferred_time": lead.preferred_time,
            "branch_name": lead.branch.name if lead.branch else None,
            "interested_course_id": lead.interested_course_id,
            "interested_course_name": lead.interested_course.name if lead.interested_course else None,
            "consent_reminders": lead.consent_reminders,
            "bookings": bookings,
        }

    def get_state_summary(self, obj) -> dict:
        state = obj.state or {}
        return {"stage": state.get("stage"), "pending_booking": bool(state.get("pending_booking")), "course_id": state.get("course_id")}


class ReplySerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4000)
