"""Admin audit log routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import require_admin
from src.api.models import AuditLogOut
from src.persistence import audit_store


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/audit-logs")
async def list_audit_logs(
    actor_user_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[AuditLogOut]:
    return [
        AuditLogOut(**event)
        for event in audit_store.list_events(actor_user_id=actor_user_id, limit=limit)
    ]
