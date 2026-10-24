from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import views as account_views
from apps.ai_agent import views as ai_views
from apps.analytics import views as analytics_views
from apps.bookings.views import TrialBookingViewSet
from apps.conversations.views import AttachmentViewSet, ConversationViewSet
from apps.core import views as core_views
from apps.courses.views import CourseViewSet, GroupViewSet, TrialSlotViewSet
from apps.integrations import views as integration_views
from apps.integrations import webchat
from apps.knowledge.views import KnowledgeDocumentViewSet, KnowledgeSearchView
from apps.leads.views import EnrollmentViewSet, LeadViewSet
from apps.notifications.views import NotificationViewSet, OutboxViewSet
from apps.organizations import views as org_views

router = DefaultRouter(trailing_slash=True)
router.register("branches", org_views.BranchViewSet, basename="branch")
router.register("team", org_views.TeamViewSet, basename="team")
router.register("courses", CourseViewSet, basename="course")
router.register("groups", GroupViewSet, basename="group")
router.register("trial-slots", TrialSlotViewSet, basename="trialslot")
router.register("leads", LeadViewSet, basename="lead")
router.register("enrollments", EnrollmentViewSet, basename="enrollment")
router.register("bookings", TrialBookingViewSet, basename="booking")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("attachments", AttachmentViewSet, basename="attachment")
router.register("knowledge/documents", KnowledgeDocumentViewSet, basename="knowledge-document")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("outbox", OutboxViewSet, basename="outbox")

api_patterns = [
    path("health/", core_views.health, name="health"),
    path("auth/csrf/", account_views.CsrfView.as_view()),
    path("auth/login/", account_views.LoginView.as_view()),
    path("auth/logout/", account_views.LogoutView.as_view()),
    path("auth/me/", account_views.MeView.as_view()),
    path("auth/switch-organization/", account_views.SwitchOrganizationView.as_view()),
    path("auth/change-password/", account_views.ChangePasswordView.as_view()),
    path("auth/notification-prefs/", account_views.NotificationPrefsView.as_view()),
    path("organization/", org_views.CurrentOrganizationView.as_view()),
    path("widget/", org_views.WidgetSettingsView.as_view()),
    path("widget/rotate-key/", org_views.WidgetRotateKeyView.as_view()),
    path("knowledge/search/", KnowledgeSearchView.as_view()),
    path("ai/settings/", ai_views.AISettingsView.as_view()),
    path("ai/test-chat/", ai_views.TestChatView.as_view()),
    path("ai/usage/", ai_views.AIUsageView.as_view()),
    path("analytics/overview/", analytics_views.OverviewView.as_view()),
    path("analytics/details/", analytics_views.DetailsView.as_view()),
    path("analytics/export.csv", analytics_views.ExportCSVView.as_view()),
    path("integrations/status/", integration_views.IntegrationStatusView.as_view()),
    path("integrations/telegram/check/", integration_views.TelegramCheckView.as_view()),
    path("integrations/ai/check/", integration_views.AICheckView.as_view()),
    path("integrations/telegram/webhook/<str:path_token>/", integration_views.telegram_webhook),
    path("public/widget/<str:public_key>/config/", webchat.WidgetConfigView.as_view()),
    path("public/widget/<str:public_key>/session/", webchat.WidgetSessionView.as_view()),
    path("public/widget/<str:public_key>/messages/", webchat.WidgetMessagesView.as_view()),
    path("public/widget/<str:public_key>/voice/", webchat.WidgetVoiceView.as_view()),
    path("public/widget/<str:public_key>/language/", webchat.WidgetLanguageView.as_view()),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("", include(router.urls)),
]

urlpatterns = [
    path("api/", include(api_patterns)),
    path("django-admin/", admin.site.urls),
    path("widget.js", core_views.widget_js, name="widget-js"),
    path("demo-site/", core_views.demo_site, name="demo-site"),
    re_path(r"^(?!api/|django-admin/|static/|media-private/).*$", core_views.spa_index, name="spa"),
]
