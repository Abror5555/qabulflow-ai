from celery import shared_task

from apps.knowledge import services


@shared_task(name="apps.knowledge.tasks.process_knowledge_document", ignore_result=True, acks_late=True)
def process_knowledge_document(document_id: int) -> str:
    document = services.process_document(document_id)
    return document.status
