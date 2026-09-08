"""可审计的业务状态变更记录。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class AuditEvent:
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    from_status: str
    to_status: str
    note: str = ""
    occurred_at: str = ""

    @classmethod
    def status_change(
        cls,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        from_status: str,
        to_status: str,
        note: str = "",
    ) -> "AuditEvent":
        if not actor.strip():
            raise ValueError("audit actor is required")
        return cls(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor.strip(),
            from_status=from_status,
            to_status=to_status,
            note=note.strip(),
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
