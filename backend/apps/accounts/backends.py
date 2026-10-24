from django.conf import settings
from django.contrib.auth.backends import ModelBackend

from apps.accounts.models import User


class EmailBackend(ModelBackend):
    """Email + parol orqali kirish. Demo hisoblar faqat DEMO_MODE yoqilganda ishlaydi."""

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        email = (email or username or "").strip().lower()
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            User().set_password(password)  # timing attack'ni kamaytirish
            return None
        if not user.check_password(password) or not self.user_can_authenticate(user):
            return None
        return user

    def user_can_authenticate(self, user) -> bool:
        if getattr(user, "is_demo", False) and not settings.DEMO_MODE:
            return False
        return super().user_can_authenticate(user)

    def get_user(self, user_id):
        user = super().get_user(user_id)
        if user is not None and user.is_demo and not settings.DEMO_MODE:
            return None
        return user
