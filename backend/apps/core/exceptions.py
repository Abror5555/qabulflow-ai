"""Tushunarli, bir xil formatdagi API xato javoblari.

Format: {"error": {"code": "...", "message": "...", "fields": {...}}}
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class BusinessError(Exception):
    """Service qatlamidagi biznes qoidasi buzilishi (masalan: slot to'lgan)."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code: str, message: str, *, status_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code


def _flatten(detail):
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, list):
        return [str(x) if not isinstance(x, (dict, list)) else _flatten(x) for x in detail]
    return str(detail)


def api_exception_handler(exc, context):
    if isinstance(exc, BusinessError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status=exc.status_code,
        )
    if isinstance(exc, ProtectedError):
        return Response(
            {"error": {"code": "protected", "message": "Bu yozuvga boshqa ma'lumotlar bog'langan. O'chirish o'rniga nofaol qiling."}},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound("Yozuv topilmadi.")
    if isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Kutilmagan xato: %s", exc.__class__.__name__)
        return Response(
            {"error": {"code": "server_error", "message": "Serverda kutilmagan xato yuz berdi. Keyinroq urinib ko'ring."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        detail = _flatten(exc.detail)
        if isinstance(detail, dict):
            non_field = detail.pop("non_field_errors", None)
            message = non_field[0] if non_field else "Kiritilgan ma'lumotlarni tekshiring."
            response.data = {"error": {"code": "validation_error", "message": message, "fields": detail}}
        else:
            message = detail[0] if isinstance(detail, list) and detail else str(detail)
            response.data = {"error": {"code": "validation_error", "message": message, "fields": {}}}
        return response

    code_map = {
        exceptions.NotAuthenticated: ("not_authenticated", "Tizimga kiring."),
        exceptions.AuthenticationFailed: ("authentication_failed", "Autentifikatsiya muvaffaqiyatsiz."),
        exceptions.PermissionDenied: ("permission_denied", None),
        exceptions.NotFound: ("not_found", "Yozuv topilmadi."),
        exceptions.MethodNotAllowed: ("method_not_allowed", "Bu metodga ruxsat yo'q."),
        exceptions.Throttled: ("rate_limited", None),
    }
    for exc_type, (code, default_message) in code_map.items():
        if isinstance(exc, exc_type):
            message = default_message or str(getattr(exc, "detail", "")) or "Ruxsat yo'q."
            if isinstance(exc, exceptions.Throttled):
                message = "So'rovlar juda ko'p. Birozdan keyin urinib ko'ring."
            if isinstance(exc, exceptions.PermissionDenied):
                message = str(exc.detail) if exc.detail else "Bu amal uchun ruxsat yo'q."
            response.data = {"error": {"code": code, "message": message}}
            return response

    response.data = {"error": {"code": "error", "message": str(getattr(exc, "detail", exc))}}
    return response
