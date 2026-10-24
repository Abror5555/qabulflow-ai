from django.http import FileResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import record_audit
from apps.core.permissions import IsOrganizationMember, ManagerWriteOperatorRead
from apps.core.schema import json_view
from apps.core.viewsets import OrganizationScopedMixin
from apps.knowledge import services
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)
    file = serializers.FileField(write_only=True, required=True)

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "title",
            "file",
            "file_type",
            "original_filename",
            "size_bytes",
            "visibility",
            "visibility_label",
            "status",
            "status_label",
            "status_message",
            "page_count",
            "chunk_count",
            "char_count",
            "flagged_lines",
            "uploaded_by_name",
            "indexed_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"title": {"required": False, "allow_blank": True}}
        read_only_fields = [
            "id",
            "file_type",
            "original_filename",
            "size_bytes",
            "status",
            "status_message",
            "page_count",
            "chunk_count",
            "char_count",
            "flagged_lines",
            "indexed_at",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None and not isinstance(self.instance, list):
            fields["file"].required = False
        return fields

    def validate_file(self, value):
        self._file_type = services.validate_upload(value)
        return value


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeChunk
        fields = ["id", "position", "page_number", "text"]


class KnowledgeDocumentViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [ManagerWriteOperatorRead]
    queryset = KnowledgeDocument.objects.select_related("uploaded_by")
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    search_fields = ["title", "original_filename"]
    filterset_fields = ["status", "visibility", "file_type"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        upload = serializer.validated_data["file"]
        title = (serializer.validated_data.get("title") or upload.name.rsplit(".", 1)[0])[:200]
        doc = serializer.save(
            organization=self.request.organization,
            uploaded_by=self.request.user,
            title=title,
            file_type=serializer._file_type,
            original_filename=upload.name[:255],
            size_bytes=upload.size,
        )
        record_audit(self.request.organization, "knowledge.uploaded", actor=self.request.user, obj=doc, summary=f"Hujjat yuklandi: {doc.title}")
        services.queue_processing(doc)

    def perform_update(self, serializer):
        visibility = serializer.validated_data.pop("visibility", None)
        serializer.validated_data.pop("file", None)
        doc = serializer.save()
        if visibility and visibility != doc.visibility:
            services.set_visibility(doc, visibility)
            record_audit(
                self.request.organization, "knowledge.visibility", actor=self.request.user, obj=doc, summary=f"{doc.title}: {doc.get_visibility_display()}"
            )

    def perform_destroy(self, instance):
        title = instance.title
        instance.file.delete(save=False)
        instance.delete()
        record_audit(self.request.organization, "knowledge.deleted", actor=self.request.user, summary=f"Hujjat o'chirildi: {title}")

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        doc = self.get_object()
        services.queue_processing(doc)
        record_audit(request.organization, "knowledge.reprocess", actor=request.user, obj=doc, summary=f"Qayta indekslash: {doc.title}")
        doc.refresh_from_db()
        return Response(KnowledgeDocumentSerializer(doc).data)

    @action(detail=True, methods=["get"], permission_classes=[IsOrganizationMember])
    def chunks(self, request, pk=None):
        doc = self.get_object()
        chunks = doc.chunks.order_by("position")[:200]
        return Response({"document": KnowledgeDocumentSerializer(doc).data, "chunks": ChunkSerializer(chunks, many=True).data})

    @action(detail=True, methods=["get"], permission_classes=[IsOrganizationMember])
    def download(self, request, pk=None):
        doc = self.get_object()
        response = FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.original_filename)
        response["Cache-Control"] = "private, no-store"
        return response


@json_view("Bilim bazasidan qidirish (q, audience=customer|staff)")
class KnowledgeSearchView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(parameters=[OpenApiParameter("q", str), OpenApiParameter("audience", str, enum=["customer", "staff"])])
    def get(self, request):
        audience = request.query_params.get("audience", "customer")
        hits = services.search(request.organization, request.query_params.get("q", ""), audience="staff" if audience == "staff" else "customer", limit=8)
        return Response(
            {
                "audience": audience,
                "results": [
                    {
                        "chunk_id": h.chunk_id,
                        "document_id": h.document_id,
                        "document_title": h.document_title,
                        "page_number": h.page_number,
                        "visibility": h.visibility,
                        "snippet": h.snippet,
                        "score": h.score,
                    }
                    for h in hits
                ],
            }
        )
