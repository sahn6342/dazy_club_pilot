"""
Booking state machine.
Single source of truth for valid status transitions — used by admin PATCH handler.
"""
from fastapi import HTTPException

# pending is the initial state (set on booking creation).
# completed / cancelled / no_show are terminal — no further transitions allowed.
TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"confirmed", "cancelled"},
    "confirmed": {"completed", "cancelled", "no_show"},
    "completed": set(),
    "cancelled": set(),
    "no_show":   set(),
}


def assert_valid_transition(current: str, next_status: str) -> None:
    """Raise HTTP 409 if the status transition is not allowed."""
    allowed = TRANSITIONS.get(current, set())
    if next_status not in allowed:
        if not allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Booking is in terminal state '{current}' — no further transitions allowed.",
            )
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from '{current}' to '{next_status}'. "
                   f"Allowed: {sorted(allowed)}.",
        )
