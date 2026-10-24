from __future__ import annotations

from apps.core.models import AuditEvent


def record_audit(
    organization,
    action: str,
    *,
    actor=None,
    actor_type: str | None = None,
    obj=None,
    summary: str = "",
    metadata: dict | None = None,
    created_at=None,
) -> AuditEvent:
    if actor_type is None:
        actor_type = AuditEvent.ActorType.USER if actor is not None else AuditEvent.ActorType.SYSTEM
    kwargs = {}
    if created_at is not None:
        kwargs["created_at"] = created_at
    return AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        actor_type=actor_type,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(getattr(obj, "pk", "") or ""),
        summary=summary[:255],
        metadata=metadata or {},
        **kwargs,
    )
