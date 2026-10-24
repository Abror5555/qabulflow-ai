from django.db.models import OuterRef, Prefetch, Subquery
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.conversations import services
from apps.conversations.models import Attachment, Conversation, HumanHandoff, Message
from apps.conversations.serializers import ConversationDetailSerializer, ConversationListSerializer, MessageSerializer, ReplySerializer
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsOrganizationMember
from apps.core.schema import binary_view
from apps.core.viewsets import OrganizationScopedMixin


class ConversationViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrganizationMember]
    queryset = Conversation.objects.exclude(channel=Conversation.Channel.TEST).select_related("lead__branch", "lead__interested_course", "assigned_to")
    branch_field = "lead__branch"
    search_fields = ["lead__full_name", "lead__phone", "lead__telegram_username", "last_message_preview"]
    filterset_fields = ["channel", "mode", "status", "needs_attention", "lead"]
    ordering = ["-needs_attention", "-last_message_at"]

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        last_sender = (
            Message.objects.filter(conversation=OuterRef("pk"))
            .exclude(kind=Message.Kind.EVENT)
            .exclude(sender=Message.Sender.SYSTEM)
            .order_by("-created_at", "-id")
            .values("sender")[:1]
        )
        qs = qs.annotate(last_sender=Subquery(last_sender))
        p = self.request.query_params
        if p.get("assigned") == "me":
            qs = qs.filter(assigned_to=self.request.user)
        if p.get("queue") == "waiting":
            qs = qs.filter(mode=Conversation.Mode.HUMAN, needs_attention=True)
        if self.action == "retrieve":
            qs = qs.prefetch_related(Prefetch("handoffs", queryset=HumanHandoff.objects.select_related("taken_by")))
        return qs

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        qs = conversation.messages.select_related("author").prefetch_related("attachments").order_by("created_at", "id")
        after = request.query_params.get("after_id")
        if after:
            try:
                qs = qs.filter(id__gt=int(after))
            except ValueError:
                raise BusinessError("invalid_param", "after_id son bo'lishi kerak.", status_code=400) from None
            return Response({"results": MessageSerializer(qs[:200], many=True).data})
        total = qs.count()
        limit = min(int(request.query_params.get("limit", 100)), 300)
        items = list(qs[max(0, total - limit) :])
        return Response({"results": MessageSerializer(items, many=True).data, "total": total, "has_more": total > limit})

    def _detail(self, conversation):
        return ConversationDetailSerializer(self.get_queryset().get(pk=conversation.pk), context=self.get_serializer_context()).data

    @action(detail=True, methods=["post"], url_path="take-over")
    def take_over(self, request, pk=None):
        conversation = services.take_over(self.get_object(), request.user)
        return Response(self._detail(conversation))

    @action(detail=True, methods=["post"], url_path="return-to-ai")
    def return_to_ai(self, request, pk=None):
        conversation = services.return_to_ai(self.get_object(), request.user)
        return Response(self._detail(conversation))

    @extend_schema(request=ReplySerializer, responses=MessageSerializer)
    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ser = ReplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        message = services.operator_reply(self.get_object(), request.user, ser.validated_data["text"])
        return Response(MessageSerializer(message).data, status=201)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        conversation = services.close_conversation(self.get_object(), request.user)
        return Response(self._detail(conversation))

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        conversation = self.get_object()
        conversation.status = Conversation.Status.OPEN
        conversation.save(update_fields=["status", "updated_at"])
        return Response(self._detail(conversation))


class AttachmentViewSet(OrganizationScopedMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrganizationMember]
    queryset = Attachment.objects.all()
    serializer_class = MessageSerializer  # faqat sxema uchun; download fayl qaytaradi

    @binary_view("Ovozli xabar faylini yuklab olish (faqat ruxsatli xodim)")
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        attachment = self.get_object()
        response = FileResponse(attachment.file.open("rb"), content_type=attachment.content_type)
        response["Content-Disposition"] = f'inline; filename="voice-{attachment.id}"'
        response["Cache-Control"] = "private, no-store"
        return response
