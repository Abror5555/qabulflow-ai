from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.middleware import SESSION_ORG_KEY, resolve_membership
from apps.core.schema import S, json_view
from apps.organizations.models import Membership


def me_payload(request) -> dict:
    user = request.user
    membership = getattr(request, "membership", None) or resolve_membership(request)
    memberships = Membership.objects.filter(user=user, is_active=True, organization__is_active=True).select_related("organization")
    org = membership.organization if membership else None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "initials": user.initials,
        "preferences": user.preferences or {},
        "is_demo_user": user.is_demo,
        "role": membership.role if membership else None,
        "branch_ids": list(membership.branches.values_list("id", flat=True)) if membership else [],
        "organization": (
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "timezone": org.timezone,
                "default_language": org.default_language,
                "currency": org.currency,
                "is_demo": org.is_demo,
            }
            if org
            else None
        ),
        "organizations": [{"id": m.organization_id, "name": m.organization.name, "role": m.role} for m in memberships],
        "demo_mode": settings.DEMO_MODE,
        "notification_prefs": membership.get_notification_prefs() if membership else {},
    }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses=inline_serializer("Csrf", {"csrfToken": serializers.CharField()}))
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: dict})
    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request, email=ser.validated_data["email"], password=ser.validated_data["password"])
        if user is None:
            return Response({"error": {"code": "invalid_credentials", "message": "Email yoki parol noto'g'ri."}}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        request.session.pop(SESSION_ORG_KEY, None)
        request.membership = resolve_membership(request)
        if request.membership is None:
            logout(request)
            return Response(
                {"error": {"code": "no_membership", "message": "Hisobingiz hech qaysi faol tashkilotga biriktirilmagan."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(me_payload(request))


@json_view("Chiqish", {}, name="LogoutRequest")
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"ok": True})


class MeSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False)
    preferences = serializers.DictField(required=False)

    def validate_preferences(self, value):
        allowed = {"theme", "sidebar_collapsed", "leads_view", "calendar_view"}
        cleaned = {k: v for k, v in value.items() if k in allowed}
        if "theme" in cleaned and cleaned["theme"] not in ("light", "dark", "system"):
            raise serializers.ValidationError("Noto'g'ri mavzu")
        return cleaned


@extend_schema_view(
    get=extend_schema(summary="Joriy foydalanuvchi va tashkilot", responses=OpenApiTypes.OBJECT),
    patch=extend_schema(summary="Profil/afzalliklarni yangilash", request=MeSerializer, responses=OpenApiTypes.OBJECT),
)
class MeView(APIView):
    def get_permissions(self):
        # GET: tizimga kirmagan foydalanuvchi uchun 200 + authenticated=false (konsolda keraksiz 403 bo'lmasligi uchun)
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        payload = me_payload(request)
        payload["authenticated"] = True
        return Response(payload)

    @extend_schema(request=MeSerializer)
    def patch(self, request):
        ser = MeSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        user = request.user
        if "full_name" in ser.validated_data:
            user.full_name = ser.validated_data["full_name"].strip() or user.full_name
        if "preferences" in ser.validated_data:
            prefs = dict(user.preferences or {})
            prefs.update(ser.validated_data["preferences"])
            user.preferences = prefs
        user.save(update_fields=["full_name", "preferences"])
        return Response(me_payload(request))


@json_view("Bildirishnoma sozlamalari", {k: S.BooleanField(required=False) for k in Membership.DEFAULT_NOTIFICATION_PREFS}, name="NotificationPrefsRequest")
class NotificationPrefsView(APIView):
    def patch(self, request):
        membership = request.membership
        prefs = membership.get_notification_prefs()
        for key, value in (request.data or {}).items():
            if key in prefs:
                prefs[key] = bool(value)
        membership.notification_prefs = prefs
        membership.save(update_fields=["notification_prefs"])
        return Response(prefs)


@json_view("Faol tashkilotni almashtirish", {"organization_id": S.IntegerField()}, name="SwitchOrganizationRequest")
class SwitchOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = request.data.get("organization_id")
        membership = Membership.objects.filter(user=request.user, organization_id=org_id, is_active=True, organization__is_active=True).first()
        if membership is None:
            return Response({"error": {"code": "not_found", "message": "Tashkilot topilmadi."}}, status=404)
        request.session[SESSION_ORG_KEY] = membership.organization_id
        request.membership = membership
        return Response(me_payload(request))


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False, min_length=8)


@json_view("Parolni o'zgartirish", {"current_password": S.CharField(), "new_password": S.CharField()}, name="ChangePasswordRequest")
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=ChangePasswordSerializer)
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if user.is_demo:
            return Response({"error": {"code": "demo_account", "message": "Demo hisob parolini o'zgartirib bo'lmaydi."}}, status=400)
        if not user.check_password(ser.validated_data["current_password"]):
            return Response(
                {"error": {"code": "invalid_password", "message": "Joriy parol noto'g'ri.", "fields": {"current_password": ["Noto'g'ri parol"]}}}, status=400
            )
        try:
            validate_password(ser.validated_data["new_password"], user)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Parol talablarga javob bermaydi.",
                        "fields": {"new_password": list(getattr(exc, "messages", [str(exc)]))},
                    }
                },
                status=400,
            )
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)
        return Response({"ok": True})
