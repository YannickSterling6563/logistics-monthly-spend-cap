from decimal import Decimal

from src.logistics_spend_cap import (
    ProofOfDelivery,
    ShipmentEvent,
    ShipmentException,
    ShipmentReview,
    plan_review,
)


def review() -> ShipmentReview:
    return ShipmentReview(
        ShipmentEvent("SHP-1", "exception", "2026-10-25T09:30:00Z"),
        ProofOfDelivery("SHP-1", "pod.jpg", "abc123"),
        ShipmentException("ADDRESS_CHECK", "signature needs review"),
    )


def test_exception_review_is_rejected_when_it_would_cross_the_cap() -> None:
    decision = plan_review(review(), Decimal("11.90"), Decimal("12.00"))
    assert decision.decision == "REJECT"
    assert decision.estimated_usd == Decimal("0.18")
    assert decision.remaining_usd == Decimal("0.10")
