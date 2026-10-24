from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.organizations.models import Branch, Membership, Organization, WidgetSettings


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "timezone", "default_language", "currency", "is_demo", "created_at"]
        read_only_fields = ["id", "slug", "currency", "is_demo", "created_at"]


class BranchSerializer(serializers.ModelSerializer):
    groups_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Branch
        fields = ["id", "name", "address", "landmark", "phone", "is_active", "groups_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        org = self.context["organization"]
        qs = Branch.objects.filter(organization=org, name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bunday nomli filial mavjud.")
        return value.strip()


class MembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    initials = serializers.CharField(source="user.initials", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    branch_ids = serializers.PrimaryKeyRelatedField(source="branches", many=True, queryset=Branch.objects.none(), required=False)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "full_name", "email", "initials", "role", "branch_ids", "is_active", "last_login", "created_at"]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        org = self.context.get("organization")
        if org is not None:
            self.fields["branch_ids"].child_relation.queryset = Branch.objects.filter(organization=org)

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            demoting = "role" in attrs and attrs["role"] != Membership.Role.OWNER and instance.role == Membership.Role.OWNER
            deactivating = attrs.get("is_active") is False and instance.role == Membership.Role.OWNER
            if demoting or deactivating:
                owners = Membership.objects.filter(organization=instance.organization, role=Membership.Role.OWNER, is_active=True).exclude(pk=instance.pk)
                if not owners.exists():
                    raise serializers.ValidationError("Tashkilotda kamida bitta faol egasi qolishi kerak.")
        return attrs


class InviteMemberSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    password = serializers.CharField(min_length=8, write_only=True, trim_whitespace=False)
    branch_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)

    def validate_email(self, value):
        value = value.lower().strip()
        org = self.context["organization"]
        if Membership.objects.filter(organization=org, user__email=value).exists():
            raise serializers.ValidationError("Bu xodim allaqachon jamoada.")
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Bu email boshqa hisobda ishlatilgan. Boshqa email kiriting.")
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value

    def validate_branch_ids(self, value):
        org = self.context["organization"]
        found = set(Branch.objects.filter(organization=org, pk__in=value).values_list("id", flat=True))
        if found != set(value):
            raise serializers.ValidationError("Filial topilmadi.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        org = self.context["organization"]
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            is_demo=False,
        )
        membership = Membership.objects.create(user=user, organization=org, role=validated_data["role"])
        if validated_data.get("branch_ids"):
            membership.branches.set(validated_data["branch_ids"])
        return membership


class WidgetSettingsSerializer(serializers.ModelSerializer):
    embed_code = serializers.SerializerMethodField()
    chat_url = serializers.SerializerMethodField()

    class Meta:
        model = WidgetSettings
        fields = ["public_key", "is_enabled", "allowed_origins", "title", "accent_color", "position", "embed_code", "chat_url", "updated_at"]
        read_only_fields = ["public_key", "embed_code", "chat_url", "updated_at"]

    def get_embed_code(self, obj) -> str:
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        return f'<script src="{base}/widget.js" data-key="{obj.public_key}" async></script>'

    def get_chat_url(self, obj) -> str:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chat/{obj.public_key}"

    def validate_allowed_origins(self, value):
        cleaned = []
        for origin in value or []:
            origin = str(origin).strip().rstrip("/")
            parsed = urlparse(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path or parsed.query:
                raise serializers.ValidationError(f"Noto'g'ri sayt manzili: {origin}. Masalan: https://example.uz")
            cleaned.append(f"{parsed.scheme}://{parsed.netloc}")
        return list(dict.fromkeys(cleaned))[:20]

    def validate_accent_color(self, value):
        import re

        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise serializers.ValidationError("Rang #RRGGBB formatida bo'lishi kerak.")
        return value.upper()
