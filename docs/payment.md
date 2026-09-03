# Online Payment (PostFinance Checkout)

Historically every order in GeoShop was **billed offline** ("invoice"):
the order is confirmed and the money is handled outside the system. This feature adds **online card
payment** through **PostFinance Checkout**, offered *alongside* invoice for eligible orders — the
buyer chooses.

> ⚠️ **External billing MUST exclude card-paid orders.** An order can be delivered *and* invoiced *and*
> card-paid. The only thing preventing a customer being charged twice is the external invoicing
> process skipping orders that were already paid by card. This is an integration outside this backend.

---

## 1. Overview

- Card payment is an **additional** option, not a replacement — the invoice path is unchanged.
- It is offered **only for orders whose price is fully calculated automatically** by the platform. Everything else stays invoice-only.
- Payment happens on **PostFinance's hosted page**; the customer never enters card details in
  geoshop, and geoshop never stores card data.


---

## 2. Specification & decisions

**Card is offered only for fully auto-priced orders.**
Any order whose price is not fully known automatically is
**invoice-only**. Concretely, an order is **excluded** from card payment when:

- a product's computed price **exceeds its `max_price`** (e.g. a very large perimeter) — this
  intentionally forces a manual quote;
- a product **requires manual pricing or validation** from the data provider;
- the order was **already sent for a manual quote** (a human entered the price) — it is priced, but
  not *auto*-priced;
- **any single item** in the order needs a quote — then the **whole order** is invoice-only (there is
  no partial/mixed card payment).

**Free orders** (total = 0) require no payment and simply proceed.

**Test vs. production.** Transactions run in a forced environment — **test by default** — so no real
money can move during development or testing.

---

## 3. Provider: PostFinance Checkout

It is the most widely used payment solution in Switzerland, it supports
the payment methods the client needs (notably **TWINT** and credit/debit cards), and it met the
client's requirements.

There is a test account that can be accessed in [this page](https://checkout.postfinance.ch/), the credentials are stored in LastPass in the `UGSP-geogr` folder.

**How it is integrated.**
- Via the official **PostFinance Python SDK**.
- Using the **hosted payment page**: the buyer is redirected to PostFinance to enter their payment
  details. Geoshop stores no card data.
- Test vs. production is controlled by a setting; a **test connector** (TWINT/card) in the space lets
  us complete simulated payments with **no real money**.

> Note: PostFinance Checkout runs on Wallee's platform, so the SDK is effectively the white-labeled
> Wallee SDK — useful when searching documentation.

---

## 4. Workflow

```
Cart (order in DRAFT)
   │  buyer confirms  (POST /order/{id}/confirm-checkout/ — returns the updated order)
   ▼
confirm() finalizes the order (expands groups, prices) and sets the status
    │
    ├─ status PENDING                     → quote requested, nothing to pay
    ├─ status READY, total == 0 (free)    → nothing to pay, done
    └─ status READY, total  > 0           → payment choice
                                              ├─ invoice → nothing to call
                                              └─ card    → POST /pay → PostFinance
```


Extraction starts at `READY` regardless of payment — that is deliberate and matches the existing
invoice behaviour: geoshop delivers, then bills. Card payment is a convenience for settling, not a
gate on fulfilment.

**This means an abandoned card payment must still be invoiced.** The external billing process has to
exclude orders that have a **settled** card payment, never orders where "the buyer intended to pay by
card" — otherwise an abandoned payment is delivered and never billed by any route.


---

## 5. Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/order/{id}/confirm/` | `GET` | **Unchanged** existing endpoint. Confirms the order and advances it to `READY`; returns an empty `202`. Used by the standard (non-card) flow. |
| `/order/{id}/confirm-checkout/` | `POST` | Same effect as `confirm`, but **returns the serialized order** so the frontend can decide whether to offer card/invoice. A separate endpoint (rather than changing `confirm`) so backend/frontend can deploy independently; the frontend calls it only when card payment is enabled. |
| `/order/{id}/pay/` | `POST` | Start a card payment for a confirmed (`READY`), priced order. Creates a `Payment`, opens a PostFinance session, returns `{ redirect_url, payment_id, amount }`. **Does not change `order_status`.** |
| `/payment/webhook/postfinance/` | `POST` | PostFinance settlement callback. Verifies the signature, records a `PaymentEvent`, updates the `Payment` status. **Does not change `order_status`.** |


---

## 6. Payment and PaymentEvent Models

Two models hold the card-payment data. No card details are ever stored — only a mirror of the
provider's payment state.

```python
class Payment(models.Model):
    """One card-payment attempt for an order — our mirror of the provider's payment."""

    order = models.ForeignKey(Order, related_name="payments")   # the order being paid
    merchant_reference = models.UUIDField(unique=True)          # our own id, sent to PostFinance and echoed back in the webhook (reconciliation anchor)
    provider = models.CharField()                               # payment provider, e.g. "postfinance"
    provider_transaction_id = models.CharField(blank=True)      # the provider's transaction id (set once the payment session is opened)
    status = models.CharField(choices=PaymentStatus.choices)    # our view of the payment lifecycle (see below)
    amount = MoneyField()                                       # amount charged — a snapshot, independent of later edits to the order
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

```python
class PaymentEvent(models.Model):
    """Append-only log of the webhook notifications about a payment (audit trail + dedup).
    Rows are never updated."""

    payment = models.ForeignKey(Payment, related_name="events")  # the payment this notification concerns
    provider_event_id = models.CharField(unique=True)            # PostFinance's unique id for the event — the deduplication key
    raw_payload = models.JSONField()                             # the verbatim webhook body, kept for audit / reprocessing
    received_at = models.DateTimeField(auto_now_add=True)        # when we received it
```

**Payment status** (`Payment.PaymentStatus`):

```python
CREATED     # row exists, buyer not yet redirected
PENDING     # redirected, awaiting the provider's outcome
AUTHORIZED  # funds held, not yet captured
SETTLED     # payment guaranteed -> the order can proceed
FAILED      # payment failed
CANCELED    # payment cancelled / voided
```

---

## 7. TODO

- **Billing exclusion (external).** Coordinate with whoever generates invoices so orders with a settled
  card payment are skipped at invoice time. This is the load-bearing integration — how those orders are
  identified (a derived flag, a query on settled payments, etc.) is still to be decided with the
  external team, so nothing is exposed for it yet.
- **Which order statuses may be paid.** `/pay` currently accepts only `READY`. Since delivery is not
  gated on payment, an order can move on to `PARTIALLY_DELIVERED` or `PROCESSED` while still unpaid —
  decide whether card payment should still be allowed in those states (timing is unclear: is it useful
  to let a buyer pay after extraction has started/finished, or should that always fall to invoicing?).
- **Refunds** — still not implemented (`refund()` is a stub).