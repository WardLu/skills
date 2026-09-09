"""Explicit lifecycle rules for publisher attempts."""

from __future__ import annotations

from .models import PublishState


_TRANSITIONS = {
    PublishState.DRAFT: frozenset((PublishState.CHECKED, PublishState.BLOCKED)),
    PublishState.BLOCKED: frozenset((PublishState.DRAFT,)),
    PublishState.CHECKED: frozenset((PublishState.PREPARED,)),
    PublishState.PREPARED: frozenset(
        (
            PublishState.AWAITING_UPLOAD_CONFIRMATION,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        )
    ),
    PublishState.AWAITING_UPLOAD_CONFIRMATION: frozenset(
        (
            PublishState.PREPARED,
            PublishState.UPLOADED,
        )
    ),
    PublishState.UPLOADED: frozenset(
        (
            PublishState.PARSING,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        )
    ),
    PublishState.PARSING: frozenset(
        (
            PublishState.PREPARED,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        )
    ),
    PublishState.AWAITING_SUBMISSION_CONFIRMATION: frozenset(
        (
            PublishState.PREPARED,
            PublishState.SUBMITTED,
            PublishState.SUBMISSION_UNKNOWN,
        )
    ),
    PublishState.SUBMISSION_UNKNOWN: frozenset(
        (
            PublishState.SUBMITTED,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        )
    ),
    PublishState.SUBMITTED: frozenset((PublishState.UNDER_REVIEW,)),
    PublishState.UNDER_REVIEW: frozenset(
        (
            PublishState.CHANGES_REQUESTED,
            PublishState.REJECTED,
            PublishState.APPROVED,
        )
    ),
    PublishState.CHANGES_REQUESTED: frozenset((PublishState.PREPARED,)),
    PublishState.REJECTED: frozenset((PublishState.PREPARED,)),
    PublishState.APPROVED: frozenset((PublishState.LIVE,)),
    PublishState.LIVE: frozenset((PublishState.SUPERSEDED, PublishState.DELISTED)),
    PublishState.SUPERSEDED: frozenset(),
    PublishState.DELISTED: frozenset(),
}


def can_transition(current: PublishState, target: PublishState) -> bool:
    """Return whether the PRD allows a state edge."""

    return target in _TRANSITIONS.get(current, frozenset())
