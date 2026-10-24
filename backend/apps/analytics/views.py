import csv
import io
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import Analytics, parse_filters
from apps.bookings.serializers import TrialBookingSerializer
from apps.conversations.serializers import ConversationListSerializer
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsOrganizationMember, ManagerOnly
from apps.leads.serializers import LeadListSerializer

FILTER_PARAMS = [
    OpenApiParameter("date_from", str, description="YYYY-MM-DD (tashkilot zonasida)"),
    OpenApiParameter("date_to", str, description="YYYY-MM-DD (kiritilgan kun ham kiradi)"),
    OpenApiParameter("branch_id", int),
    OpenApiParameter("course_id", int),
    OpenApiParameter("source", str),
    OpenApiParameter("granularity", str, enum=["day", "week"]),
]


class OverviewView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(parameters=FILTER_PARAMS, responses=dict)
    def get(self, request):
        filters = parse_filters(request.organization, request.query_params, request.membership)
        return Response(Analytics(request.organization, filters).overview())


class DetailsView(APIView):
    """Grafik nuqtasi/segmentidan filtrlangan tafsilotlar jadvali (drill-down)."""

    permission_classes = [IsOrganizationMember]

    @extend_schema(
        parameters=FILTER_PARAMS
        + [
            OpenApiParameter("metric", str, required=True),
            OpenApiParameter("bucket", str),
            OpenApiParameter("channel", str),
            OpenApiParameter("status", str),
            OpenApiParameter("stage", str),
            OpenApiParameter("detail_course_id", int),
        ],
        responses=dict,
    )
    def get(self, request):
        p = request.query_params
        filters = parse_filters(request.organization, p, request.membership)
        analytics = Analytics(request.organization, filters)
        detail_course = p.get("detail_course_id")
        kind, qs = analytics.details(
            p.get("metric", ""),
            bucket=p.get("bucket"),
            channel=p.get("channel"),
            status=p.get("status"),
            stage=p.get("stage"),
            course_id=int(detail_course) if detail_course and detail_course.isdigit() else None,
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = {"leads": LeadListSerializer, "bookings": TrialBookingSerializer, "conversations": ConversationListSerializer}[kind]
        response = paginator.get_paginated_response(serializer(page, many=True).data)
        response.data["kind"] = kind
        return response


class ExportCSVView(APIView):
    """Panel bilan bir xil service va filtrlar asosida CSV eksport."""

    permission_classes = [ManagerOnly]

    @extend_schema(parameters=FILTER_PARAMS, responses={(200, "text/csv"): bytes})
    def get(self, request):
        filters = parse_filters(request.organization, request.query_params, request.membership)
        data = Analytics(request.organization, filters).overview()
        buffer = io.StringIO()
        buffer.write("﻿")  # Excel uchun UTF-8 BOM
        w = csv.writer(buffer)
        f = data["filters"]
        w.writerow(["QabulFlow AI — analitika eksporti"])
        w.writerow(["Tashkilot", request.organization.name])
        w.writerow(["Davr", f["date_from"], f["date_to"], "Vaqt zonasi", data["period"]["timezone"]])
        w.writerow(["Filial filtri", f["branch_id"] or "barchasi", "Kurs filtri", f["course_id"] or "barchasi", "Manba filtri", f["source"] or "barchasi"])
        w.writerow(["Eksport vaqti", timezone.localtime(timezone.now(), ZoneInfo(data["period"]["timezone"])).isoformat(timespec="seconds")])
        w.writerow([])
        w.writerow(["section", "key", "label", "value", "previous", "change", "change_unit"])
        for k in data["kpis"]:
            w.writerow(["kpi", k["key"], k["label"], _fmt(k["value"]), _fmt(k["previous"]), _fmt(k["change"]), k["change_unit"]])
        w.writerow([])
        w.writerow(["section", "bucket", "bucket_start", "bucket_end", "new_leads", "confirmed_bookings", "cancelled_bookings"])
        for row in data["timeseries"]:
            w.writerow(
                ["timeseries", row["bucket"], row["bucket_start"], row["bucket_end"], row["new_leads"], row["confirmed_bookings"], row["cancelled_bookings"]]
            )
        w.writerow([])
        w.writerow(["section", "key", "label", "count"])
        for row in data["channels"]:
            w.writerow(["channel", row["channel"], row["label"], row["count"]])
        for row in data["sources"]:
            w.writerow(["source", row["source"], row["label"], row["count"]])
        for row in data["booking_statuses"]:
            w.writerow(["booking_status", row["status"], row["label"], row["count"]])
        for row in data["funnel"]:
            w.writerow(["funnel", row["stage"], row["label"], row["count"]])
        w.writerow([])
        w.writerow(["section", "course_id", "course", "interest", "bookings"])
        for row in data["courses"]:
            w.writerow(["course", row["course_id"], row["name"], row["interest"], row["bookings"]])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="qabulflow-analytics-{f["date_from"]}_{f["date_to"]}.csv"'
        return response


def _fmt(value):
    return "—" if value is None else value
