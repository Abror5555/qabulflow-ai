"""1. Login, ruxsatlar va boshqa tashkilot ma'lumotlariga kira olmaslik."""

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.conversations import inbound
from apps.conversations.models import Attachment, Message
from apps.knowledge.models import KnowledgeDocument
from apps.organizations.models import Membership

pytestmark = pytest.mark.django_db


def test_login_success_and_me(kit):
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    res = client.post("/api/auth/login/", {"email": kit.owner.email, "password": "Secret123!x"}, format="json", HTTP_X_CSRFTOKEN=token)
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["role"] == "owner"
    assert body["organization"]["id"] == kit.org.id
    me = client.get("/api/auth/me/")
    assert me.status_code == 200 and me.json()["email"] == kit.owner.email


def test_login_requires_csrf(kit):
    client = APIClient(enforce_csrf_checks=True)
    res = client.post("/api/auth/login/", {"email": kit.owner.email, "password": "Secret123!x"}, format="json")
    assert res.status_code == 403


def test_login_wrong_password(kit, anon_client):
    res = anon_client.post("/api/auth/login/", {"email": kit.owner.email, "password": "wrong"}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_credentials"


def test_demo_account_disabled_outside_demo_mode(kit, anon_client):
    User.objects.filter(pk=kit.owner.pk).update(is_demo=True)
    with override_settings(DEMO_MODE=False):
        res = anon_client.post("/api/auth/login/", {"email": kit.owner.email, "password": "Secret123!x"}, format="json")
    assert res.status_code == 400


def test_unauthenticated_is_rejected(anon_client):
    for url in ("/api/leads/", "/api/courses/", "/api/analytics/overview/", "/api/conversations/"):
        assert anon_client.get(url).status_code in (401, 403)


def test_role_permissions(kit, client_for):
    operator, manager, owner = client_for(kit.operator), client_for(kit.manager), client_for(kit.owner)
    payload = {"name": "Yangi kurs", "price": "500000", "level": "beginner"}
    assert operator.post("/api/courses/", payload, format="json").status_code == 403
    assert manager.post("/api/courses/", payload, format="json").status_code == 201
    assert operator.get("/api/courses/").status_code == 200
    # Jamoa: operator ko'ra olmaydi, menejer ko'radi lekin taklif qila olmaydi, egasi taklif qiladi
    assert operator.get("/api/team/").status_code == 403
    assert manager.get("/api/team/").status_code == 200
    invite = {"full_name": "Yangi Xodim", "email": "new.staff@example.test", "role": "operator", "password": "Kuchli-Parol-77"}
    assert manager.post("/api/team/invite/", invite, format="json").status_code == 403
    assert owner.post("/api/team/invite/", invite, format="json").status_code == 201
    # CSV eksport operator uchun yopiq
    assert operator.get("/api/analytics/export.csv").status_code == 403
    assert manager.get("/api/analytics/export.csv").status_code == 200
    # Integratsiya tekshiruvi faqat egasi
    assert manager.post("/api/integrations/telegram/check/").status_code == 403


def test_cannot_demote_last_owner(kit, client_for):
    owner = client_for(kit.owner)
    membership = Membership.objects.get(user=kit.owner, organization=kit.org)
    res = owner.patch(f"/api/team/{membership.id}/", {"role": "manager"}, format="json")
    assert res.status_code == 400


def test_operator_cannot_confirm_enrollment(kit, client_for):
    lead = kit.lead()
    res = client_for(kit.operator).post(f"/api/leads/{lead.id}/enroll/", {"course_id": kit.course.id}, format="json")
    assert res.status_code == 403
    res = client_for(kit.operator).post(f"/api/leads/{lead.id}/status/", {"status": "enrolled"}, format="json")
    assert res.status_code == 403
    res = client_for(kit.manager).post(f"/api/leads/{lead.id}/enroll/", {"course_id": kit.course.id}, format="json")
    assert res.status_code == 201


def test_tenant_isolation_by_id(kit, other_kit, client_for):
    client = client_for(kit.owner)
    foreign_lead = other_kit.lead()
    foreign_slot = other_kit.slot()
    foreign_conv = inbound.get_webchat_conversation(other_kit.org, visitor_id="web_foreign")
    msg = Message.objects.create(organization=other_kit.org, conversation=foreign_conv, sender="customer", kind="voice", text="x")
    att = Attachment.objects.create(
        organization=other_kit.org, message=msg, file=ContentFile(b"OggS" + b"0" * 100, name="a.ogg"), content_type="audio/ogg", size_bytes=104
    )
    doc = KnowledgeDocument(organization=other_kit.org, title="Maxfiy", file_type="txt", original_filename="m.txt", visibility="customer")
    doc.file.save("m.txt", ContentFile(b"maxfiy matn " * 20), save=True)

    assert client.get(f"/api/leads/{foreign_lead.id}/").status_code == 404
    assert client.patch(f"/api/leads/{foreign_lead.id}/", {"full_name": "Hack"}, format="json").status_code == 404
    assert client.get(f"/api/courses/{other_kit.course.id}/").status_code == 404
    assert client.get(f"/api/trial-slots/{foreign_slot.id}/").status_code == 404
    assert client.get(f"/api/conversations/{foreign_conv.id}/").status_code == 404
    assert client.get(f"/api/attachments/{att.id}/download/").status_code == 404
    assert client.get(f"/api/knowledge/documents/{doc.id}/download/").status_code == 404
    # Boshqa tashkilot slotiga bron qilish
    own_lead = kit.lead()
    res = client.post("/api/bookings/", {"lead_id": own_lead.id, "slot_id": foreign_slot.id}, format="json")
    assert res.status_code == 404
    res = client.post("/api/bookings/", {"lead_id": foreign_lead.id, "slot_id": kit.slot().id}, format="json")
    assert res.status_code == 404
    # Boshqa tashkilot kursi bilan guruh yaratish
    res = client.post(
        "/api/groups/",
        {"name": "X", "course_id": other_kit.course.id, "branch_id": kit.branch.id, "days": [0], "start_time": "10:00", "end_time": "11:00"},
        format="json",
    )
    assert res.status_code == 400
    # Ro'yxatlarda boshqa tashkilot yozuvlari yo'q
    ids = [row["id"] for row in client.get("/api/leads/?page_size=200").json()["results"]]
    assert foreign_lead.id not in ids
    # Tashkilotni almashtirib bo'lmaydi (a'zolik yo'q)
    assert client.post("/api/auth/switch-organization/", {"organization_id": other_kit.org.id}, format="json").status_code == 404
    # Statistika filtrida boshqa tashkilot filiali
    assert client.get(f"/api/analytics/overview/?branch_id={other_kit.branch.id}").status_code == 404


def test_branch_restricted_operator(kit, client_for):
    membership = Membership.objects.get(user=kit.operator, organization=kit.org)
    membership.branches.set([kit.branch])
    own = kit.lead(branch=kit.branch)
    other = kit.lead(branch=kit.branch2)
    unassigned = kit.lead()
    ids = {row["id"] for row in client_for(kit.operator).get("/api/leads/?page_size=100").json()["results"]}
    assert own.id in ids and unassigned.id in ids and other.id not in ids
    assert client_for(kit.operator).get(f"/api/leads/{other.id}/").status_code == 404
    assert client_for(kit.manager).get(f"/api/leads/{other.id}/").status_code == 200


def test_me_anonymous_returns_flag(anon_client):
    res = anon_client.get("/api/auth/me/")
    assert res.status_code == 200 and res.json() == {"authenticated": False}
    assert anon_client.patch("/api/auth/me/", {"full_name": "x"}, format="json").status_code in (401, 403)


def test_kanban_and_summary_counts_group_correctly(kit, client_for):
    """Regressiya: ordering GROUP BY ga tushib, har ustun hisobi 1 bo'lib qolmasligi kerak."""
    for _ in range(3):
        kit.lead(status="new")
    for _ in range(2):
        kit.lead(status="qualified")
    client = client_for(kit.manager)
    columns = {c["status"]: c for c in client.get("/api/leads/kanban/").json()["columns"]}
    assert columns["new"]["count"] == 3 and len(columns["new"]["items"]) == 3
    assert columns["qualified"]["count"] == 2
    summary = client.get("/api/leads/summary/").json()
    assert summary["by_status"] == {"new": 3, "qualified": 2}
    assert summary["total"] == 5
