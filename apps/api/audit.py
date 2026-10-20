"""Audit trail: who did what, when, from where.

Two layers:
  * explicit events (`audit(...)`) for actions where the detail matters (status changes, refunds,
    user and role changes, logins, payment anomalies);
  * a middleware fallback (main.py) that records every other successful admin write by method + path,
    so nothing slips through when a new route is added.

Recording must never break the action being audited, and details must never hold secrets:
callers pass small dicts of facts (ids, statuses, amounts), never request bodies."""
import json
import logging
import re
from typing import Any, Optional

from fastapi import Request

from rate_limit import client_ip

logger = logging.getLogger(__name__)

_MAX_DETAIL = 2000
_ID_SEGMENT = re.compile(r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{20,}|\d+)$", re.I)


def _actor_parts(actor: Any) -> tuple[str, Optional[str]]:
    if isinstance(actor, dict):
        return str(actor.get("sub") or "unknown"), actor.get("role")
    return (str(actor) if actor else "unknown"), None


def _detail_json(detail: Any) -> Optional[str]:
    if detail is None:
        return None
    text = detail if isinstance(detail, str) else json.dumps(detail, default=str, sort_keys=True)
    return text if len(text) <= _MAX_DETAIL else text[: _MAX_DETAIL - 1] + "…"


def audit(
    action: str,
    actor: Any = "system",
    *,
    request: Optional[Request] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Any = None,
    role: Optional[str] = None,
) -> None:
    """Record one event. `actor` is a username or the {"sub", "role"} dict from the auth dependencies.
    Never raises."""
    try:
        from deps import audit_repo
        name, actor_role = _actor_parts(actor)
        audit_repo.record(
            action=action, actor=name, actor_role=role or actor_role,
            entity_type=entity_type, entity_id=entity_id,
            detail=_detail_json(detail), ip=client_ip(request) if request is not None else None,
        )
        if request is not None:
            request.scope["audit_done"] = True  # tells the middleware fallback not to log it again
    except Exception:
        logger.exception("Audit write failed for %s", action)


def normalise_path(path: str) -> tuple[str, Optional[str], Optional[str]]:
    """'/api/v1/admin/promos/<uuid>' -> ('/admin/promos/{id}', 'promos', '<uuid>')."""
    p = path[len("/api/v1"):] if path.startswith("/api/v1") else path
    parts = [s for s in p.split("/") if s]
    entity_id = None
    out = []
    for seg in parts:
        if _ID_SEGMENT.match(seg):
            entity_id = seg
            out.append("{id}")
        else:
            out.append(seg)
    entity_type = parts[1] if len(parts) > 1 and parts[0] == "admin" else (parts[0] if parts else None)
    # Keyed resources (cms/<key>, settings) have a meaningful last segment instead of an id.
    if entity_id is None and len(parts) >= 3 and parts[0] == "admin":
        entity_id = parts[-1]
    return "/" + "/".join(out), entity_type, entity_id
