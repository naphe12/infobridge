from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.models.common import CaseStatus
from app.models.exchange import ExchangeCase


ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.DRAFT: frozenset({CaseStatus.SENT}),
    CaseStatus.SENT: frozenset({CaseStatus.RECEIVED}),
    CaseStatus.RECEIVED: frozenset({CaseStatus.ASSIGNED}),
    CaseStatus.ASSIGNED: frozenset({CaseStatus.IN_PROGRESS}),
    CaseStatus.IN_PROGRESS: frozenset({CaseStatus.PENDING_VALIDATION}),
    CaseStatus.PENDING_VALIDATION: frozenset({CaseStatus.APPROVED, CaseStatus.REJECTED}),
    CaseStatus.APPROVED: frozenset({CaseStatus.RESPONSE_SENT}),
    CaseStatus.REJECTED: frozenset({CaseStatus.PENDING_VALIDATION}),
    CaseStatus.RESPONSE_SENT: frozenset({CaseStatus.CLOSED}),
    CaseStatus.CLOSED: frozenset({CaseStatus.ARCHIVED}),
    CaseStatus.ARCHIVED: frozenset(),
    CaseStatus.IN_REVIEW: frozenset({CaseStatus.ASSIGNED}),
}


def transition_case(exchange_case: ExchangeCase, target: CaseStatus) -> None:
    allowed_targets = ALLOWED_CASE_TRANSITIONS.get(exchange_case.status, frozenset())
    if target not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid case transition: {exchange_case.status.value} -> {target.value}",
        )
    exchange_case.status = target
    exchange_case.updated_at = datetime.now(timezone.utc)
