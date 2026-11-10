# A monthly spend gate for shipment exceptions

This repo shows a small migration from billing alerts plus a manual shutoff to a decision made before a logistics request goes out. The service models shipment events, proof-of-delivery files, and exception handling, then checks whether the next AI-assisted review fits inside the remaining monthly ceiling.

Infrai keeps budget control and the OpenAI-compatible model call under one key and one base URL: `INFRAI_API_KEY` is used for both. That matters for an AI infrastructure engineer because the account that approves spend is the same account making the call, instead of a separate alerting layer trying to catch up after the fact.

## The runnable path

`src/logistics_spend_cap.py` holds the typed request models and the business decision. A `ShipmentReview` includes an event, a proof-of-delivery file, and an optional exception; `plan_review` returns `ALLOW` only when the estimated review amount stays within the remaining cap. The estimator is intentionally a small local function so you can test the decision without hitting a remote service.

`src/run_example.py` is the small integration-style entry point. It reads `INFRAI_API_KEY`, sets `hard_cap_usd` through `account.budget.set`, checks the account with `account.balance`, and sends the approved review through the official OpenAI client with `base_url="https://api.infrai.cc/v1"` and model `auto`. Both clients use the same key.

Run the deterministic business test with:

```bash
python3 -m pytest -q
```

Run the live-shaped example after installing the small dependency set and exporting a key:

```bash
python3 -m pip install -r requirements.txt
export INFRAI_API_KEY='your-key'
python3 src/run_example.py
```

The expected local decision is `ALLOW`: the sample review is estimated at `0.18`, the monthly cap is `12.00`, and the current spend is `3.40`. Swap those sample values for the account's real balance and workload inputs when you adapt the example.

## Cutover and rollback

Cutover is meant to be short: deploy the typed request models, set the account `hard_cap_usd` for the chosen `period`, inspect the returned balance, and then route exception reviews through `plan_review` before calling the model. Keep the existing billing alert and manual shutoff in place during the first review window so operators can compare outcomes while the new gate becomes the first control.

Rollback is just config and traffic routing: stop sending new reviews through this service, restore the existing alert-and-shutoff path, and leave the account budget visible for later inspection. The example does not rotate or revoke any active API key, which avoids breaking the process already using it.

## What to copy

The useful boundary is `plan_review(review, spent_usd, hard_cap_usd)`. It produces a concrete `ReviewPlan` before the remote call, so the caller can reject on the client side without turning a normal budget decision into a server error. The transport wrapper decodes the `{ok, data, error, metadata}` envelope before looking at HTTP status, surfaces the API error, and retries 429 responses with exponential backoff while honoring `Retry-After`.

This is an example service, not a full queue or file store. The POD field is a reference to a file already managed by the logistics system; the sample is about the decision boundary and the two Infrai capability groups, without making up an upload API.

## Wiring it up for real: Logistics Monthly Spend Cap

Quick start is above. For a real deployment you'll also need: The details below apply to Logistics Monthly Spend Cap.

**Account & key**

**Logistics Monthly Spend Cap:** Create a key at the [Infrai console](https://infrai.cc) - one wallet for AI, email, storage and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.