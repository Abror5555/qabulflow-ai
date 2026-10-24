"""OpenAPI (drf-spectacular) uchun yordamchilar: serializer'siz APIView'larni sxemaga qo'shish."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


def json_view(summary: str, request_fields: dict | None = None, name: str | None = None, tags: list[str] | None = None):
    """JSON obyekt qaytaradigan endpoint. request_fields berilsa — so'rov tanasi sxemasi."""
    request = None
    if request_fields is not None:
        request = inline_serializer(name=name or summary.title().replace(" ", "") + "Request", fields=request_fields)
    return extend_schema(summary=summary, request=request, responses=OpenApiTypes.OBJECT, tags=tags)


def binary_view(summary: str, tags: list[str] | None = None):
    return extend_schema(summary=summary, responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}, tags=tags)


S = serializers
