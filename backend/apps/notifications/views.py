from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOrganizationMember, ManagerOnly
from apps.notifications.models import Notification, OutboxMessage


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "is_read", "created_at"]


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsOrganizationMember]
    filterset_fields = ["is_read", "kind"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(organization=self.request.organization, user=self.request.user).order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = self.get_queryset().filter(is_read=False).count()
        return response

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        updated = self.get_queryset().filter(pk=pk).update(is_read=True)
        return Response({"ok": bool(updated)})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        count = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"ok": True, "updated": count})


class OutboxSerializer(serializers.ModelSerializer):
    recipient_masked = serializers.SerializerMethodField()

    class Meta:
        model = OutboxMessage
        fields = ["id", "channel", "recipient_masked", "text", "kind", "status", "attempts", "last_error", "created_at", "sent_at"]

    def get_recipient_masked(self, obj) -> str:
        r = obj.recipient or ""
        return (r[:2] + "•" * max(0, len(r) - 4) + r[-2:]) if len(r) > 4 else "••••"


class OutboxViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Tashqi kanallar navbati. DEMO_MODE'da xabarlar shu yerda 'demo' holatida qoladi."""

    serializer_class = OutboxSerializer
    permission_classes = [ManagerOnly]
    filterset_fields = ["status", "channel", "kind"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return OutboxMessage.objects.none()
        return OutboxMessage.objects.filter(organization=self.request.organization).order_by("-created_at", "-id")
