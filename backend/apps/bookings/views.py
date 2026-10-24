from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.bookings import services
from apps.bookings.models import BookingEvent, TrialBooking
from apps.bookings.serializers import (
    AttendanceSerializer,
    CancelBookingSerializer,
    CreateBookingSerializer,
    RescheduleSerializer,
    TrialBookingDetailSerializer,
    TrialBookingSerializer,
)
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsOrganizationMember
from apps.core.utils import local_range, org_tz, parse_date_param
from apps.core.viewsets import OrganizationScopedMixin
from apps.leads.models import Lead


class TrialBookingViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrganizationMember]
    queryset = TrialBooking.objects.filter(lead__is_test=False).select_related("lead", "slot__group__course", "slot__group__branch", "created_by")
    branch_field = "slot__group__branch"
    search_fields = ["lead__full_name", "lead__phone"]
    filterset_fields = ["status", "channel", "lead"]
    ordering_fields = ["confirmed_at", "slot__starts_at"]
    ordering = ["slot__starts_at"]

    def get_serializer_class(self):
        return TrialBookingDetailSerializer if self.action == "retrieve" else TrialBookingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        tz = org_tz(self.request.organization)
        start, end = local_range(parse_date_param(p.get("date_from"), "date_from"), parse_date_param(p.get("date_to"), "date_to"), tz)
        if start:
            qs = qs.filter(slot__starts_at__gte=start)
        if end:
            qs = qs.filter(slot__starts_at__lt=end)
        c_start, c_end = local_range(parse_date_param(p.get("confirmed_from"), "confirmed_from"), parse_date_param(p.get("confirmed_to"), "confirmed_to"), tz)
        if c_start:
            qs = qs.filter(confirmed_at__gte=c_start)
        if c_end:
            qs = qs.filter(confirmed_at__lt=c_end)
        if p.get("course"):
            qs = qs.filter(slot__group__course_id=p["course"])
        if p.get("branch"):
            qs = qs.filter(slot__group__branch_id=p["branch"])
        if self.action == "retrieve":
            qs = qs.prefetch_related(Prefetch("events", queryset=BookingEvent.objects.select_related("actor")))
        return qs

    def _detail(self, booking_id):
        return TrialBookingDetailSerializer(
            self.get_queryset().prefetch_related("events__actor").get(pk=booking_id), context=self.get_serializer_context()
        ).data

    @extend_schema(request=CreateBookingSerializer, responses=TrialBookingDetailSerializer)
    def create(self, request):
        ser = CreateBookingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lead = Lead.objects.filter(organization=request.organization, pk=ser.validated_data["lead_id"], is_test=False).first()
        if lead is None:
            raise BusinessError("lead_not_found", "Mijoz topilmadi.", status_code=404)
        key = ser.validated_data.get("idempotency_key") or request.headers.get("Idempotency-Key") or None
        result = services.create_trial_booking(
            request.organization,
            lead=lead,
            slot_id=ser.validated_data["slot_id"],
            channel=TrialBooking.Channel.PANEL,
            idempotency_key=f"panel:{key}" if key else None,
            actor=request.user,
            notes=ser.validated_data.get("notes", ""),
        )
        return Response(self._detail(result.booking.pk), status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK)

    @extend_schema(request=CancelBookingSerializer, responses=TrialBookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        ser = CancelBookingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.cancel_trial_booking(request.organization, booking.pk, actor=request.user, reason=ser.validated_data.get("reason", ""))
        return Response(self._detail(booking.pk))

    @extend_schema(request=RescheduleSerializer, responses=TrialBookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        booking = self.get_object()
        ser = RescheduleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.reschedule_trial_booking(request.organization, booking.pk, ser.validated_data["slot_id"], actor=request.user)
        return Response(self._detail(booking.pk))

    @extend_schema(request=AttendanceSerializer, responses=TrialBookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def attendance(self, request, pk=None):
        booking = self.get_object()
        ser = AttendanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.mark_attendance(request.organization, booking.pk, attended=ser.validated_data["attended"], actor=request.user)
        return Response(self._detail(booking.pk))
