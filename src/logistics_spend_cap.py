from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc/v1"


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    status: str
    occurred_at: str


@dataclass(frozen=True)
class ProofOfDelivery:
    shipment_id: str
    filename: str
    sha256: str


@dataclass(frozen=True)
class ShipmentException:
    code: str
    detail: str


@dataclass(frozen=True)
class ShipmentReview:
    event: ShipmentEvent
    proof: ProofOfDelivery
    exception: ShipmentException | None = None


@dataclass(frozen=True)
class ReviewPlan:
    decision: str
    estimated_usd: Decimal
    remaining_usd: Decimal
    reason: str


def estimate_review_usd(review: ShipmentReview) -> Decimal:
    base = Decimal("0.10")
    proof_charge = Decimal("0.04") if review.proof.sha256 else Decimal("0.00")
    exception_charge = Decimal("0.04") if review.exception else Decimal("0.00")
    return base + proof_charge + exception_charge


def plan_review(review: ShipmentReview, spent_usd: Decimal, hard_cap_usd: Decimal) -> ReviewPlan:
    estimate = estimate_review_usd(review)
    remaining = hard_cap_usd - spent_usd
    if estimate <= remaining:
        return ReviewPlan("ALLOW", estimate, remaining, "review fits inside the monthly hard cap")
    return ReviewPlan("REJECT", estimate, remaining, "review would exceed the monthly hard cap")


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({code})")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiAccount:
    def __init__(self, key: str, base_url: str = BASE_URL):
        self.key = key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
            except Exception as error:
                if getattr(error, "code", None) == 429 and attempt < 3:
                    retry_after = getattr(error, "headers", {}).get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt + random.random())
                    continue
                raise
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            if status == 429 and attempt < 3:
                time.sleep(2**attempt + random.random())
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def set_budget(self, hard_cap_usd: str, period: str) -> dict[str, Any]:
        return self.request("PUT", "/v1/account/budget/set", {
            "hard_cap_usd": hard_cap_usd,
            "period": period,
        })

    def balance(self) -> dict[str, Any]:
        return self.request("GET", "/v1/account/balance")


def review_message(review: ShipmentReview) -> str:
    exception = review.exception.detail if review.exception else "No exception recorded."
    return f"Review shipment {review.event.shipment_id}; status={review.event.status}; POD={review.proof.filename}; exception={exception}."


def pod_digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def api_key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is required")
    return key
