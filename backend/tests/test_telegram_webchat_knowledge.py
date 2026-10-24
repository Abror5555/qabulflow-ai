"""Telegram adapteri (update dedup), veb-chat public API, bilim bazasi yuklash va seed idempotentligi."""

from datetime import UTC, datetime

import pytest
from aiogram.types import Update
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient

from apps.conversations.models import Conversation, Message
from apps.integrations.telegram.processor import TelegramProcessor
from apps.knowledge.models import KnowledgeDocument
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db


def tg_update(update_id, text=None, *, chat_id=4242, chat_type="private", callback=None):
    user = {"id": chat_id, "is_bot": False, "first_name": "Demo", "username": "demo_user", "language_code": "uz"}
    chat = {"id": chat_id, "type": chat_type}
    payload = {"update_id": update_id}
    if callback:
        payload["callback_query"] = {
            "id": f"cb{update_id}",
            "from": user,
            "chat_instance": "x",
            "data": callback,
            "message": {"message_id": 1, "date": int(datetime.now(UTC).timestamp()), "chat": chat, "text": "til"},
        }
    else:
        payload["message"] = {"message_id": update_id, "date": int(datetime.now(UTC).timestamp()), "chat": chat, "from": user, "text": text}
    return Update.model_validate(payload)


def test_telegram_start_and_text(kit):
    proc = TelegramProcessor(kit.org)
    actions = proc.process(tg_update(1, "/start"))
    assert [a.keyboard for a in actions] == ["language", "main"]
    actions = proc.process(tg_update(2, "IELTS narxi qancha?"))
    assert len(actions) == 1 and "1 200 000" in actions[0].text and actions[0].keyboard == "main"
    conv = Conversation.objects.get(organization=kit.org, channel="telegram")
    assert conv.lead.telegram_user_id == 4242 and conv.lead.source == "telegram"


def test_telegram_duplicate_update_ignored(kit):
    proc = TelegramProcessor(kit.org)
    first = proc.process(tg_update(10, "Python narxi?"))
    again = proc.process(tg_update(10, "Python narxi?"))
    assert first and again == []
    assert Message.objects.filter(conversation__channel="telegram", sender="customer").count() == 1
    assert Message.objects.filter(conversation__channel="telegram", sender="ai").count() == 1


def test_telegram_language_callback_and_group_ignored(kit):
    proc = TelegramProcessor(kit.org)
    actions = proc.process(tg_update(20, callback="lang:ru"))
    assert actions[0].callback_query_id and "русский" in actions[1].text
    conv = Conversation.objects.get(organization=kit.org, channel="telegram")
    assert conv.language == "ru" and conv.language_locked
    assert proc.process(tg_update(21, "salom", chat_id=-100, chat_type="group")) == []


def test_telegram_same_user_not_merged_with_webchat_by_name(kit):
    from apps.conversations import inbound

    web = inbound.get_webchat_conversation(kit.org, visitor_id="web_same")
    Lead.objects.filter(pk=web.lead_id).update(full_name="Demo")
    TelegramProcessor(kit.org).process(tg_update(30, "salom"))
    assert Lead.objects.filter(organization=kit.org, full_name__in=["Demo", ""]).count() == 2


@override_settings(TELEGRAM_MODE="polling")
def test_webhook_disabled_in_polling_mode(anon_client):
    assert anon_client.post("/api/integrations/telegram/webhook/x/", data="{}", content_type="application/json").status_code == 404


@override_settings(
    TELEGRAM_MODE="webhook", TELEGRAM_BOT_TOKEN="123:abc", DEMO_MODE=False, TELEGRAM_WEBHOOK_PATH_TOKEN="path123", TELEGRAM_WEBHOOK_SECRET="s3cret"
)
def test_webhook_rejects_bad_secret(anon_client):
    res = anon_client.post(
        "/api/integrations/telegram/webhook/path123/", data="{}", content_type="application/json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong"
    )
    assert res.status_code == 403
    res = anon_client.post(
        "/api/integrations/telegram/webhook/badpath/", data="{}", content_type="application/json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="s3cret"
    )
    assert res.status_code == 404


# ---------------------------------------------------------------- webchat
def test_webchat_session_message_and_poll(kit):
    client = APIClient()
    key = kit.widget.public_key
    cfg = client.get(f"/api/public/widget/{key}/config/")
    assert cfg.status_code == 200 and cfg.json()["demo_mode"] is True
    token = client.post(f"/api/public/widget/{key}/session/").json()["token"]
    res = client.post(
        f"/api/public/widget/{key}/messages/", {"text": "IELTS narxi qancha?", "client_message_id": "c1"}, format="json", HTTP_X_VISITOR_TOKEN=token
    )
    assert res.status_code == 201
    body = res.json()
    assert "1 200 000" in body["replies"][0]["text"]
    assert "tool_trace" not in body["replies"][0]
    # Takroriy yuborish (retry) dublikat yaratmaydi
    again = client.post(
        f"/api/public/widget/{key}/messages/", {"text": "IELTS narxi qancha?", "client_message_id": "c1"}, format="json", HTTP_X_VISITOR_TOKEN=token
    )
    assert again.status_code == 200
    assert Message.objects.filter(conversation__channel="webchat", sender="customer").count() == 1
    poll = client.get(f"/api/public/widget/{key}/messages/", HTTP_X_VISITOR_TOKEN=token).json()
    assert [m["sender"] for m in poll["messages"]] == ["customer", "ai"]
    assert Lead.objects.get(organization=kit.org).source == "webchat"


def test_webchat_token_bound_to_widget(kit, other_kit):
    client = APIClient()
    token = client.post(f"/api/public/widget/{kit.widget.public_key}/session/").json()["token"]
    res = client.get(f"/api/public/widget/{other_kit.widget.public_key}/messages/", HTTP_X_VISITOR_TOKEN=token)
    assert res.status_code == 401
    assert client.get(f"/api/public/widget/{kit.widget.public_key}/messages/", HTTP_X_VISITOR_TOKEN="forged").status_code == 401
    assert client.get("/api/public/widget/wk_unknown/config/").status_code == 404


def test_webchat_origin_allowlist(kit):
    kit.widget.allowed_origins = ["https://markaz.example"]
    kit.widget.save()
    client = APIClient()
    assert client.get(f"/api/public/widget/{kit.widget.public_key}/config/", HTTP_ORIGIN="https://evil.example").status_code == 403
    assert client.get(f"/api/public/widget/{kit.widget.public_key}/config/", HTTP_ORIGIN="https://markaz.example").status_code == 200


# ---------------------------------------------------------------- knowledge
def pdf_with_text(text: str) -> bytes:
    """xref jadvali to'g'ri hisoblangan minimal, matnli PDF."""

    stream = f"BT /F1 14 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


MINIMAL_PDF_WITH_TEXT = pdf_with_text("Sinov darsi bepul va 90 daqiqa davom etadi. Avtoturargoh bor.")


def blank_pdf() -> bytes:
    import io

    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_knowledge_upload_index_search_and_scanned_pdf(kit, client_for, django_capture_on_commit_callbacks):
    client = client_for(kit.manager)
    with django_capture_on_commit_callbacks(execute=True):
        res = client.post(
            "/api/knowledge/documents/",
            {"file": SimpleUploadedFile("faq.md", b"# Savollar\n\nOilaviy chegirma 10% beriladi.\n" * 3), "visibility": "customer"},
            format="multipart",
        )
    assert res.status_code == 201, res.content
    doc = KnowledgeDocument.objects.get(pk=res.json()["id"])
    assert doc.status == "indexed" and doc.chunk_count >= 1
    with django_capture_on_commit_callbacks(execute=True):
        res = client.post(
            "/api/knowledge/documents/", {"file": SimpleUploadedFile("text.pdf", MINIMAL_PDF_WITH_TEXT, content_type="application/pdf")}, format="multipart"
        )
    pdf = KnowledgeDocument.objects.get(pk=res.json()["id"])
    assert pdf.status == "indexed", pdf.status_message
    with django_capture_on_commit_callbacks(execute=True):
        res = client.post(
            "/api/knowledge/documents/", {"file": SimpleUploadedFile("scan.pdf", blank_pdf(), content_type="application/pdf")}, format="multipart"
        )
    scan = KnowledgeDocument.objects.get(pk=res.json()["id"])
    assert scan.status == "no_text" and "skaner" in scan.status_message
    search = client.get("/api/knowledge/search/?q=chegirma").json()["results"]
    assert search and search[0]["document_title"] == "faq"
    search = client.get("/api/knowledge/search/?q=avtoturargoh").json()["results"]
    assert search and search[0]["page_number"] == 1


def test_knowledge_upload_validation(kit, client_for):
    client = client_for(kit.manager)
    assert client.post("/api/knowledge/documents/", {"file": SimpleUploadedFile("virus.exe", b"MZ" + b"0" * 100)}, format="multipart").status_code == 400
    assert client.post("/api/knowledge/documents/", {"file": SimpleUploadedFile("fake.pdf", b"not a pdf" * 10)}, format="multipart").status_code == 400
    with override_settings(KNOWLEDGE_MAX_BYTES=100):
        assert client.post("/api/knowledge/documents/", {"file": SimpleUploadedFile("big.txt", b"a" * 500)}, format="multipart").status_code == 400
    assert (
        client_for(kit.operator).post("/api/knowledge/documents/", {"file": SimpleUploadedFile("ok.txt", b"salom dunyo " * 20)}, format="multipart").status_code
        == 403
    )


# ---------------------------------------------------------------- seed
def test_seed_is_idempotent():
    call_command("seed_demo", "--leads", "40", "--days", "30")
    first = (Lead.objects.count(), Message.objects.count())
    call_command("seed_demo", "--leads", "40", "--days", "30")
    assert (Lead.objects.count(), Message.objects.count()) == first
    assert Lead.objects.filter(organization__slug="demo-academy").count() >= 40


@override_settings(DEMO_MODE=False)
def test_seed_refuses_outside_demo_mode():
    with pytest.raises(CommandError):
        call_command("seed_demo")


def test_seed_if_empty_keeps_existing_data_and_is_deterministic():
    call_command("seed_demo", "--leads", "30", "--days", "30", "--skip-live")
    names = sorted(Lead.objects.filter(organization__slug="demo-academy").values_list("full_name", "source", "status"))
    marker = Lead.objects.filter(organization__slug="demo-academy").first()
    # --if-empty: mavjud demo tashkilot o'chirilmaydi (docker qayta ishga tushganda ma'lumot saqlanadi)
    call_command("seed_demo", "--leads", "30", "--days", "30", "--skip-live", "--if-empty")
    assert Lead.objects.filter(pk=marker.pk).exists()
    # Bir xil seed — bir xil sintetik ma'lumot
    call_command("seed_demo", "--leads", "30", "--days", "30", "--skip-live")
    again = sorted(Lead.objects.filter(organization__slug="demo-academy").values_list("full_name", "source", "status"))
    assert again == names
