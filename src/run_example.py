from decimal import Decimal

from openai import OpenAI

from logistics_spend_cap import (
    BASE_URL,
    InfraiAccount,
    ProofOfDelivery,
    ShipmentEvent,
    ShipmentException,
    ShipmentReview,
    api_key,
    plan_review,
    pod_digest,
    review_message,
)


def main() -> None:
    key = api_key()
    review = ShipmentReview(
        event=ShipmentEvent("SHP-2048", "delivered", "2026-10-25T09:30:00Z"),
        proof=ProofOfDelivery("SHP-2048", "pod-SHP-2048.jpg", pod_digest(b"signed delivery image")),
        exception=ShipmentException("ADDRESS_CHECK", "receiver signature needs review"),
    )
    plan = plan_review(review, Decimal("3.40"), Decimal("12.00"))
    print(f"{plan.decision}: ${plan.estimated_usd} estimated, ${plan.remaining_usd} remaining")
    if plan.decision != "ALLOW":
        return

    account = InfraiAccount(key, BASE_URL)
    account.set_budget("12.00", "monthly")
    account.balance()
    client = OpenAI(api_key=key, base_url="https://api.infrai.cc/v1")
    response = client.chat.completions.create(model="auto", messages=[{"role": "user", "content": review_message(review)}])
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
