from django.db.models import Count, Prefetch
from django_filters import rest_framework as df
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.bookings import services as booking_services
from apps.bookings.models import Enrollment, TrialBooking
from apps.core.audit import record_audit
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsOrganizationMember, role_at_least
from apps.core.utils import local_range, org_tz, parse_date_param
from apps.core.viewsets import OrganizationScopedMixin
from apps.courses.models import Course, Group
from apps.leads import services
from apps.leads.models import Lead, LeadStatusChange
from apps.leads.serializers import (
    AssignSerializer,
    EnrollmentSerializer,
    EnrollSerializer,
    LeadDetailSerializer,
    LeadListSerializer,
    LeadNoteSerializer,
    LeadWriteSerializer,
    StatusChangeSerializer,
)


class LeadFilter(df.FilterSet):
    status = df.CharFilter()
    source = df.CharFilter()
    branch = df.NumberFilter(field_name="branch_id")
    course = df.NumberFilter(field_name="interested_course_id")
    assigned_to = df.CharFilter(method="filter_assigned")

    class Meta:
        model = Lead
        fields = ["status", "source", "branch", "course", "assigned_to"]

    def filter_assigned(self, qs, name, value):
        if value == "me":
            return qs.filter(assigned_to=self.request.user)
        if value == "none":
            return qs.filter(assigned_to__isnull=True)
        try:
            return qs.filter(assigned_to_id=int(value))
        except ValueError:
            return qs.none()


class LeadViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsOrganizationMember]
    queryset = Lead.objects.filter(is_test=False).select_related("branch", "interested_course", "assigned_to")
    branch_field = "branch"
    filterset_class = LeadFilter
    search_fields = ["full_name", "phone", "telegram_username", "goal"]
    ordering_fields = ["created_at", "last_activity_at", "full_name", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LeadWriteSerializer
        if self.action == "retrieve":
            return LeadDetailSerializer
        return LeadListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        tz = org_tz(self.request.organization)
        start, end = local_range(parse_date_param(p.get("created_from"), "created_from"), parse_date_param(p.get("created_to"), "created_to"), tz)
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lt=end)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                "notes__author",
                Prefetch("status_changes", queryset=LeadStatusChange.objects.select_related("changed_by").order_by("-created_at")),
                Prefetch(
                    "trial_bookings", queryset=TrialBooking.objects.select_related("slot__group__course", "slot__group__branch").order_by("-confirmed_at")
                ),
                "enrollments__course",
                "enrollments__group",
                "enrollments__confirmed_by",
            )
        return qs

    def create(self, request, *args, **kwargs):
        ser = LeadWriteSerializer(data=request.data, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        lead = services.create_lead(
            request.organization,
            source=data.get("source") or Lead.Source.MANUAL,
            full_name=data.get("full_name", ""),
            phone=data.get("phone", ""),
            language=data.get("language", request.organization.default_language),
            branch=data.get("branch"),
            interested_course=data.get("interested_course"),
            actor=request.user,
            via="operator",
        )
        extra = {k: v for k, v in data.items() if k in ("goal", "level", "preferred_time", "assigned_to", "phone_verified")}
        if extra:
            services.update_lead(lead, extra, actor=request.user)
        lead.refresh_from_db()
        return Response(LeadDetailSerializer(lead, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        lead = self.get_object()
        ser = LeadWriteSerializer(lead, data=request.data, partial=True, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        services.update_lead(lead, dict(ser.validated_data), actor=request.user)
        record_audit(request.organization, "lead.updated", actor=request.user, obj=lead, summary=f"Mijoz ma'lumotlari yangilandi: {lead.display_name}")
        return Response(LeadDetailSerializer(self.get_queryset().get(pk=lead.pk), context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        if not role_at_least(self.request, "manager"):
            raise BusinessError("permission_denied", "Mijozni o'chirish uchun menejer roli kerak.", status_code=403)
        if instance.trial_bookings.exists() or instance.enrollments.exists():
            raise BusinessError("protected", "Mijozda bronlar mavjud. O'chirish o'rniga holatini 'Yo'qotilgan' qiling.")
        name = instance.display_name
        instance.delete()
        record_audit(self.request.organization, "lead.deleted", actor=self.request.user, summary=f"Mijoz o'chirildi: {name}")

    @extend_schema(request=StatusChangeSerializer, responses=LeadDetailSerializer)
    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        lead = self.get_object()
        ser = StatusChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ser.validated_data["status"] == Lead.Status.ENROLLED and not role_at_least(request, "manager"):
            raise BusinessError("permission_denied", '"O\'qishga yozildi" holatini faqat menejer/egasi tasdiqlaydi.', status_code=403)
        services.change_status(lead, ser.validated_data["status"], actor=request.user, via="operator", reason=ser.validated_data.get("reason", ""))
        return Response(LeadDetailSerializer(self.get_queryset().get(pk=lead.pk), context=self.get_serializer_context()).data)

    @extend_schema(request=AssignSerializer, responses=LeadListSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        lead = self.get_object()
        ser = AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = None
        if ser.validated_data["user_id"] is not None:
            user = User.objects.filter(pk=ser.validated_data["user_id"], memberships__organization=request.organization, memberships__is_active=True).first()
            if user is None:
                raise BusinessError("invalid_assignee", "Xodim topilmadi.", status_code=400)
        services.update_lead(lead, {"assigned_to": user}, actor=request.user)
        record_audit(
            request.organization,
            "lead.assigned",
            actor=request.user,
            obj=lead,
            summary=f"{lead.display_name} → {user.full_name if user else 'biriktirilmagan'}",
        )
        return Response(LeadListSerializer(lead).data)

    @extend_schema(request=LeadNoteSerializer, responses=LeadNoteSerializer)
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        lead = self.get_object()
        note = services.add_note(lead, request.data.get("text", ""), request.user)
        return Response(LeadNoteSerializer(note).data, status=201)

    @extend_schema(request=EnrollSerializer, responses=EnrollmentSerializer)
    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        if not role_at_least(request, "manager"):
            raise BusinessError("permission_denied", "O'qishga yozilishni faqat menejer/egasi tasdiqlaydi.", status_code=403)
        lead = self.get_object()
        ser = EnrollSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        course = Course.objects.filter(organization=request.organization, pk=ser.validated_data["course_id"]).first()
        if course is None:
            raise BusinessError("not_found", "Kurs topilmadi.", status_code=404)
        group = None
        if ser.validated_data.get("group_id"):
            group = Group.objects.filter(organization=request.organization, pk=ser.validated_data["group_id"]).first()
            if group is None:
                raise BusinessError("not_found", "Guruh topilmadi.", status_code=404)
        enrollment = booking_services.confirm_enrollment(
            request.organization, lead=lead, course=course, group=group, actor=request.user, notes=ser.validated_data.get("notes", "")
        )
        return Response(EnrollmentSerializer(enrollment).data, status=201)

    @action(detail=False, methods=["get"])
    def kanban(self, request):
        qs = self.filter_queryset(self.get_queryset())
        counts = dict(qs.order_by().values_list("status").annotate(c=Count("id")))
        limit = min(int(request.query_params.get("per_column", 30)), 100)
        columns = []
        for value, label in Lead.Status.choices:
            items = qs.filter(status=value).order_by("-last_activity_at")[:limit]
            columns.append({"status": value, "label": label, "count": counts.get(value, 0), "items": LeadListSerializer(items, many=True).data})
        return Response({"columns": columns})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        return Response(
            {
                "total": qs.count(),
                "unassigned": qs.filter(assigned_to__isnull=True).exclude(status__in=["enrolled", "lost"]).count(),
                "mine": qs.filter(assigned_to=request.user).count(),
                "needs_attention": qs.filter(conversations__needs_attention=True).distinct().count(),
                "by_status": dict(qs.order_by().values_list("status").annotate(c=Count("id"))),
            }
        )


class EnrollmentViewSet(OrganizationScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsOrganizationMember]
    queryset = Enrollment.objects.select_related("lead", "course", "group", "confirmed_by")
    filterset_fields = ["status", "course"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if not role_at_least(request, "manager"):
            raise BusinessError("permission_denied", "Bu amal menejer/egasi uchun.", status_code=403)
        enrollment = booking_services.cancel_enrollment(request.organization, pk, actor=request.user)
        return Response(EnrollmentSerializer(enrollment).data)
