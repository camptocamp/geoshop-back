# Online Payment (PostFinance Checkout)

Geoshop lets customers order geodata. Historically every order was **billed offline** ("invoice"):
the order is confirmed and the money is handled outside the system. This feature adds **online card
payment** through **PostFinance Checkout**, offered *alongside* invoice for eligible orders — the
buyer chooses.

---

## 1. Overview

- Card payment is an **additional** option, not a replacement — the invoice path is unchanged.
- It is offered **only for orders whose price is fully calculated automatically** by the platform
  (see §2). Everything else stays invoice-only.
- Payment happens on **PostFinance's hosted page**; the customer never enters card details in
  geoshop, and geoshop never stores card data.
- When a payment succeeds, the order enters the **same delivery pipeline** as an invoice order.

---

## 2. Specification & decisions

**Card is offered only for fully auto-priced orders.** A card charge must be an exact, final amount
that the platform computed itself. Any order whose price is not fully known automatically is
**invoice-only**. Concretely, an order is **excluded** from card payment when:

- a product's computed price **exceeds its `max_price`** (e.g. a very large perimeter) — this
  intentionally forces a manual quote;
- a product **requires manual pricing or validation** from the data provider;
- the order was **already sent for a manual quote** (a human entered the price) — it is priced, but
  not *auto*-priced;
- **any single item** in the order needs a quote — then the **whole order** is invoice-only (there is
  no partial/mixed card payment).

**Free orders** (total = 0) require no payment and simply proceed.

**Product groups are card-payable**, but a group's real price is only known after it is "expanded"
into concrete products at checkout, so its price is computed at the checkout step (see §4).

**Test vs. production.** Transactions run in a forced environment — **test by default** — so no real
money can move during development or testing.

---

## 3. Provider: PostFinance Checkout

**Why PostFinance Checkout.** It is the most widely used payment solution in Switzerland, it supports
the payment methods the client needs (notably **TWINT** and credit/debit cards), and it met the
client's requirements.

**How it is integrated.**
- Via the official **PostFinance Python SDK**.
- Using the **hosted payment page**: the buyer is redirected to PostFinance to enter their payment
  details. Because card data never touches geoshop's servers, this keeps geoshop in the light
  **PCI DSS SAQ-A** scope — geoshop stores no card data.
- Test vs. production is controlled by a setting; a **test connector** (TWINT/card) in the space lets
  us complete simulated payments with **no real money**.

> Note: PostFinance Checkout runs on Wallee's platform, so the SDK is effectively the white-labeled
> Wallee SDK — useful when searching documentation.

---

## 4. Payment workflow

```
Cart (order in DRAFT)
   │  "go to checkout"
   ▼
POST /prepare   ── READ-ONLY: compute the definitive final price + eligibility (no change to the cart)
   │
   ├─ "quote"  → order needs a manual quote → invoice / quote path only
   ├─ "free"   → total is 0 → no payment
   └─ "card"   → buyer chooses:
                    ├─ invoice → confirm → order READY
                    └─ card    → POST /pay → order AWAITING_PAYMENT → redirect to hosted page
                                                │  buyer pays (card / TWINT)
                                                ▼
                                    signed webhook ─┬─ SETTLED  → confirm() → order READY
                                                    └─ FAILED   → order back to DRAFT (retryable)
```

1. The buyer builds a cart (an order in `DRAFT`) and draws the perimeter.
2. On **"go to checkout"**, the backend computes the **definitive final price and eligibility** in a
   **read-only** step (`prepare`) — without modifying the cart.
3. The checkout page shows the result: **card + invoice** (eligible), **invoice/quote only**, or
   **free**.
4. If the buyer chooses **card**, the backend opens a PostFinance transaction and redirects the buyer
   to the hosted page, where they pay.
5. PostFinance notifies the backend with a **signed webhook**. On **settlement** the order is
   finalized (`confirm()`) and advances to `READY`, joining the normal delivery pipeline. On
   **failure** the order returns to `DRAFT` so the buyer can edit or retry.

**Why `prepare` and `pay` are non-destructive until settlement.** For a **product group**, the final
price depends on server-side *expansion* — turning the group into the concrete products that actually
apply to the drawn perimeter. Doing that expansion destructively at checkout would corrupt the
frontend's group-based cart. So both `prepare` and `pay` compute the price by **previewing** the
expansion **in memory** — they write nothing. The order is finalized (expansion persisted) **only on
payment settlement** (`confirm()`), or on the invoice path's own `confirm`. This guarantees the amount
shown, the amount charged, and the amount finalized all match, and that a failed or abandoned payment
leaves the cart exactly as it was — ready to retry.

---

## 5. Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/order/{id}/prepare/` | `POST` | **Read-only.** Compute the final price + which payment option applies. Returns `{ payment_option: "card" \| "free" \| "quote", total, currency }`. |
| `/order/{id}/pay/` | `POST` | Start a card payment. Returns `{ payment_required, redirect_url, payment_id, amount }`; the frontend redirects the buyer to `redirect_url`. |
| `/order/{id}/confirm/` | `GET` | Existing **invoice** path (unchanged) — confirms the order and advances it to `READY`. |
| `/payment/webhook/postfinance/` | `POST` | PostFinance settlement callback (server-to-server; not called by users). |

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

**Order status added for card payment** (`Order.OrderStatus`):

```python
AWAITING_PAYMENT  # buyer redirected to pay; waiting for the settlement webhook
```

On a successful settlement the order proceeds to `READY`, exactly like a confirmed invoice order, so
the rest of the extraction/delivery process is unchanged. A failed or canceled payment sends the order
back to `DRAFT` (the cart was never finalized), so the buyer can edit or retry.

---

## 7. TODO

- **Payment status on the order (derived, not stored).** For admin/reporting readability — and to
  let the external billing process exclude card-paid orders — a read-only property such as
  `Order.is_card_paid` / `Order.payment_status` could be derived from the order's latest `Payment`.
  Keeping it *derived* (not a second stored field) means the `Payment` stays the single source of
  truth and nothing has to be kept in sync.
- **Refunds.** Not implemented — `refund()` in `api/payments.py` is a stub. A refund would issue the
  refund on the PostFinance transaction and move the `Payment` to a `REFUNDED` state — the status was
  removed for now (unused) and would be re-added with the feature, along with deciding how the order
  should reflect it.
- **Freeze the cart while an order awaits payment.** OrderItem create/update are not status-guarded,
  so the cart can still be changed while the order is `AWAITING_PAYMENT`. Since the amount to charge is
  snapshotted when payment starts, a later change would make the charged total diverge from the
  finalized order. The backend should block item changes in this state, and the frontend should
  disable editing while awaiting payment.
- **Prompt handling of abandoned payments.** If a buyer leaves the payment page without paying,
  PostFinance sends no immediate notification — it only moves the transaction to a terminal state
  after its authorization timeout. Until then the order stays `AWAITING_PAYMENT`, so the buyer can't
  retry. We need a quicker way to release an abandoned order back to `DRAFT`.