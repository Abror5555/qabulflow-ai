from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import record_audit
from apps.core.permissions import ManagerWriteOperatorRead, OwnerWriteManagerRead, OwnerWriteOperatorRead
from apps.core.schema import json_view
from apps.core.viewsets import OrganizationScopedMixin
from apps.organizations.models import Branch, Membership, WidgetSettings, generate_public_key
from apps.organizations.serializers import (
    BranchSerializer,
    InviteMemberSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    WidgetSettingsSerializer,
)


class CurrentOrganizationView(APIView):
    permission_classes = [OwnerWriteOperatorRead]

    @extend_schema(responses=OrganizationSerializer)
    def get(self, request):
        return Response(OrganizationSerializer(request.organization).data)

    @extend_schema(request=OrganizationSerializer, responses=OrganizationSerializer)
    def patch(self, request):
        ser = OrganizationSerializer(request.organization, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record_audit(request.organization, "organization.updated", actor=request.user, obj=request.organization, summary="Tashkilot sozlamalari yangilandi")
        return Response(ser.data)


class BranchViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [ManagerWriteOperatorRead]
    queryset = Branch.objects.all()
    search_fields = ["name", "address"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        return super().get_queryset().annotate(groups_count=Count("groups", filter=Q(groups__is_active=True)))

    def perform_create(self, serializer):
        branch = serializer.save(organization=self.request.organization)
        record_audit(self.request.organization, "branch.created", actor=self.request.user, obj=branch, summary=f"Filial qo'shildi: {branch.name}")


class TeamViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [OwnerWriteManagerRead]
    queryset = Membership.objects.select_related("user").prefetch_related("branches")
    search_fields = ["user__full_name", "user__email"]
    filterset_fields = ["role", "is_active"]
    ordering = ["-is_active", "user__full_name"]

    def perform_update(self, serializer):
        membership = serializer.save()
        record_audit(
            self.request.organization,
            "team.updated",
            actor=self.request.user,
            obj=membership,
            summary=f"Xodim yangilandi: {membership.user.full_name} ({membership.get_role_display()})",
        )

    @extend_schema(request=InviteMemberSerializer, responses=MembershipSerializer)
    @action(detail=False, methods=["post"])
    def invite(self, request):
        ser = InviteMemberSerializer(data=request.data, context={"organization": request.organization})
        ser.is_valid(raise_exception=True)
        membership = ser.save()
        record_audit(request.organization, "team.invited", actor=request.user, obj=membership, summary=f"Jamoaga qo'shildi: {membership.user.full_name}")
        return Response(MembershipSerializer(membership, context={"organization": request.organization}).data, status=201)

    @action(detail=False, methods=["get"], permission_classes=[OwnerWriteOperatorRead])
    def assignable(self, request):
        """Mas'ul biriktirish uchun faol xodimlar (barcha rollar ko'ra oladi)."""

        qs = Membership.objects.filter(organization=request.organization, is_active=True).select_related("user").order_by("user__full_name")
        return Response([{"user_id": m.user_id, "full_name": m.user.full_name, "role": m.role, "initials": m.user.initials} for m in qs])


class WidgetSettingsView(APIView):
    permission_classes = [OwnerWriteManagerRead]

    def _get(self, request):
        obj, _ = WidgetSettings.objects.get_or_create(organization=request.organization, defaults={"title": request.organization.name})
        return obj

    @extend_schema(responses=WidgetSettingsSerializer)
    def get(self, request):
        return Response(WidgetSettingsSerializer(self._get(request)).data)

    @extend_schema(request=WidgetSettingsSerializer, responses=WidgetSettingsSerializer)
    def patch(self, request):
        obj = self._get(request)
        ser = WidgetSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record_audit(request.organization, "widget.updated", actor=request.user, obj=obj, summary="Vidjet sozlamalari yangilandi")
        return Response(ser.data)


@json_view("Vidjet public kalitini yangilash", {}, name="WidgetRotateKeyRequest")
class WidgetRotateKeyView(APIView):
    permission_classes = [OwnerWriteManagerRead]

    def post(self, request):
        obj, _ = WidgetSettings.objects.get_or_create(organization=request.organization)
        obj.public_key = generate_public_key()
        obj.save(update_fields=["public_key", "updated_at"])
        record_audit(request.organization, "widget.key_rotated", actor=request.user, obj=obj, summary="Vidjet kaliti yangilandi")
        return Response(WidgetSettingsSerializer(obj).data)
