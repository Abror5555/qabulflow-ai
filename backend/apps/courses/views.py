from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.audit import record_audit
from apps.core.exceptions import BusinessError
from apps.core.permissions import ManagerWriteOperatorRead
from apps.core.utils import local_range, org_tz, parse_date_param
from apps.core.viewsets import OrganizationScopedMixin
from apps.courses.models import Course, Group, TrialSlot
from apps.courses.serializers import CourseSerializer, GenerateSlotsSerializer, GroupSerializer, TrialSlotSerializer


class CourseViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [ManagerWriteOperatorRead]
    queryset = Course.objects.all()
    search_fields = ["name", "description"]
    filterset_fields = ["is_active", "level"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .annotate(
                groups_count=Count("groups", filter=Q(groups__is_active=True), distinct=True),
                upcoming_slots=Count(
                    "groups__trial_slots",
                    filter=Q(groups__trial_slots__starts_at__gte=now, groups__trial_slots__status="open"),
                    distinct=True,
                ),
            )
        )

    def perform_create(self, serializer):
        course = serializer.save(organization=self.request.organization, currency=self.request.organization.currency)
        record_audit(self.request.organization, "course.created", actor=self.request.user, obj=course, summary=f"Kurs qo'shildi: {course.name}")

    def perform_update(self, serializer):
        course = serializer.save()
        record_audit(self.request.organization, "course.updated", actor=self.request.user, obj=course, summary=f"Kurs yangilandi: {course.name}")

    def perform_destroy(self, instance):
        if instance.groups.exists():
            raise BusinessError("protected", "Kursga guruhlar bog'langan. O'chirish o'rniga kursni nofaol qiling.")
        name = instance.name
        instance.delete()
        record_audit(self.request.organization, "course.deleted", actor=self.request.user, summary=f"Kurs o'chirildi: {name}")


class GroupViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [ManagerWriteOperatorRead]
    queryset = Group.objects.select_related("course", "branch")
    branch_field = "branch"
    search_fields = ["name", "teacher_name", "course__name"]
    filterset_fields = ["course", "branch", "is_active"]
    ordering = ["course__name", "name"]

    def perform_create(self, serializer):
        group = serializer.save(organization=self.request.organization)
        record_audit(self.request.organization, "group.created", actor=self.request.user, obj=group, summary=f"Guruh qo'shildi: {group.name}")

    def perform_update(self, serializer):
        group = serializer.save()
        record_audit(self.request.organization, "group.updated", actor=self.request.user, obj=group, summary=f"Guruh yangilandi: {group.name}")

    def perform_destroy(self, instance):
        if instance.trial_slots.exists() or instance.enrollments.exists():
            raise BusinessError("protected", "Guruhga sinov darslari yoki o'quvchilar bog'langan. Uni nofaol qiling.")
        name = instance.name
        instance.delete()
        record_audit(self.request.organization, "group.deleted", actor=self.request.user, summary=f"Guruh o'chirildi: {name}")


class TrialSlotViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = TrialSlotSerializer
    permission_classes = [ManagerWriteOperatorRead]
    queryset = TrialSlot.objects.select_related("group__course", "group__branch")
    branch_field = "group__branch"
    filterset_fields = ["status", "group"]
    ordering = ["starts_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        tz = org_tz(self.request.organization)
        start, end = local_range(parse_date_param(p.get("date_from"), "date_from"), parse_date_param(p.get("date_to"), "date_to"), tz)
        if start:
            qs = qs.filter(starts_at__gte=start)
        if end:
            qs = qs.filter(starts_at__lt=end)
        if p.get("course"):
            qs = qs.filter(group__course_id=p["course"])
        if p.get("branch"):
            qs = qs.filter(group__branch_id=p["branch"])
        if p.get("available") in ("1", "true"):
            from django.db.models import F

            qs = qs.filter(status="open", starts_at__gt=timezone.now(), seats_taken__lt=F("capacity"), group__is_active=True, group__course__is_active=True)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("date_from", str),
            OpenApiParameter("date_to", str),
            OpenApiParameter("course", int),
            OpenApiParameter("branch", int),
            OpenApiParameter("available", bool),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        slot = serializer.save(organization=self.request.organization)
        record_audit(
            self.request.organization,
            "slot.created",
            actor=self.request.user,
            obj=slot,
            summary=f"Sinov darsi qo'shildi: {slot.group.name}, {timezone.localtime(slot.starts_at):%d.%m %H:%M}",
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        new_status = serializer.validated_data.get("status")
        if new_status == "cancelled" and instance.bookings.filter(status="confirmed").exists():
            raise BusinessError("slot_has_bookings", "Bu vaqtda faol bronlar bor. Avval ularni boshqa vaqtga ko'chiring yoki bekor qiling.")
        if ("starts_at" in serializer.validated_data or "group" in serializer.validated_data) and instance.bookings.exclude(status="cancelled").exists():
            raise BusinessError("slot_has_bookings", "Bron qilingan sinov darsining vaqti yoki guruhini o'zgartirib bo'lmaydi. Bronlarni ko'chiring.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.bookings.exists():
            raise BusinessError("protected", "Bu sinov darsiga bronlar bog'langan. O'chirish o'rniga bekor qiling.")
        instance.delete()

    @extend_schema(request=GenerateSlotsSerializer, responses=TrialSlotSerializer(many=True))
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Guruh jadvali asosida keyingi N hafta uchun sinov darsi slotlarini yaratadi (takrorlarsiz)."""

        ser = GenerateSlotsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        group = Group.objects.filter(organization=request.organization, pk=ser.validated_data["group_id"]).select_related("course").first()
        if group is None:
            raise BusinessError("not_found", "Guruh topilmadi.", status_code=404)
        tz = org_tz(request.organization)
        today = timezone.localtime(timezone.now(), tz).date()
        created = []
        with transaction.atomic():
            for offset in range(1, ser.validated_data["weeks"] * 7 + 1):
                day = today + timedelta(days=offset)
                if day.weekday() not in (group.days or []):
                    continue
                starts = datetime.combine(day, group.start_time, tzinfo=tz)
                ends = datetime.combine(day, group.end_time, tzinfo=tz)
                if TrialSlot.objects.filter(group=group, starts_at=starts).exists():
                    continue
                created.append(
                    TrialSlot.objects.create(
                        organization=request.organization, group=group, starts_at=starts, ends_at=ends, capacity=ser.validated_data["capacity"]
                    )
                )
        record_audit(request.organization, "slot.generated", actor=request.user, obj=group, summary=f"{group.name}: {len(created)} ta sinov darsi yaratildi")
        return Response(TrialSlotSerializer(created, many=True, context=self.get_serializer_context()).data, status=201)

    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """Kalendar uchun: slotlar + ulardagi bronlar (bekor qilinganlardan tashqari)."""

        from apps.bookings.models import TrialBooking

        qs = self.filter_queryset(self.get_queryset())[:500]
        slots = list(qs)
        bookings = TrialBooking.objects.filter(organization=request.organization, slot__in=slots).exclude(status="cancelled").select_related("lead")
        by_slot: dict[int, list] = {}
        for b in bookings:
            by_slot.setdefault(b.slot_id, []).append(
                {"id": b.id, "lead_id": b.lead_id, "lead_name": b.lead.display_name, "status": b.status, "channel": b.channel}
            )
        data = TrialSlotSerializer(slots, many=True, context=self.get_serializer_context()).data
        for item in data:
            item["bookings"] = by_slot.get(item["id"], [])
        return Response({"results": data})
