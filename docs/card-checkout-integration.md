# Card Payment — Checkout Integration Plan

**Status:** proposed (awaiting client input) · **Date:** 2026-07-22

How online card payment (PostFinance Checkout) integrates with geoshop-back's existing
order checkout, which today supports only offline "invoice" payment. This document is for the
client to decide how to proceed. It assumes the payment groundwork already in place (the
`Payment` / `PaymentEvent` models, order statuses, and the PostFinance `create_session`
integration described in `payment-integration.md`).

---

## 1. How checkout works today (the "invoice" path)

There is no explicit "pay by invoice" choice — it is simply the only path that exists:

1. An order is created as `DRAFT`; the buyer adds items.
2. The frontend calls **`GET /order/{id}/confirm/`**. The view validates that items exist and each
   has a data format, then calls **`Order.confirm()`**.
3. `Order.confirm()` expands product groups, resolves overlaps, stamps `date_ordered`, triggers
   validation for approval-needed items, then:
   - if **all items are priced** → order becomes `READY` (ready for extraction/delivery);
   - otherwise → a quote is requested and the order becomes `PENDING`.
4. `READY` orders are picked up for processing and delivered. **Billing happens outside the
   system** — the `invoice_reference` / `invoice_contact` fields are the only trace of payment.

So "invoice" means: *confirm and proceed immediately; the money is handled offline.* There is no
payment-method field, no customer-category rule, and no order-type distinction for this today.

---

## 2. Decisions already taken

- **Both options offered, buyer's free choice.** Every buyer chooses invoice or card at checkout;
  no eligibility rules or customer-category restrictions.
- **A separate endpoint for card** (`POST /order/{id}/pay/`), leaving the existing invoice
  `GET /order/{id}/confirm/` completely untouched. Least risk to the existing flow.

---

## 3. Key correctness finding

`Order.confirm()`'s preparation step (`_expand_product_groups()` +
`_resolve_grouped_order_items_by_overlap()`) **deletes and recreates order items** (a product
"group" is replaced by its child products, each re-priced). This can change the order's contents
and therefore its **total**. Importantly, `confirm()` runs this preparation but **never recomputes
the order total afterwards**.

That is tolerable for invoice (a human bills the final amount), but **unacceptable for card**: we
must charge exactly the final, post-expansion price. Therefore the card path must **finalize the
order contents and recompute the total before charging**.

---

## 4. Proposed card flow

### `POST /order/{id}/pay/` (new)

1. **Preconditions** (same as the confirm view): status is `DRAFT`/`QUOTE_DONE`; items exist; each
   has a data format.
2. **Finalize contents & price**: run group expansion + overlap resolution, then **recompute the
   total** (`set_price()`). Guarantees the charged amount matches the real order.
3. **Guard rails**:
   - not fully priced → `400` ("a quote is needed first" — card cannot pay an unpriced order);
   - **total = 0 (free order)** → no payment: run the normal `confirm()` → `READY`, respond
     `{ payment_required: false }`.
4. **Create the `Payment`** (`CREATED`, `amount = total`, provider `postfinance`). Deduplication: if
   the order already has an open (`PENDING`) payment, reuse it rather than creating a second.
5. **Open the PostFinance session** (`create_session`) → store `provider_transaction_id`, set
   `Payment → PENDING` and `Order → AWAITING_PAYMENT`.
6. Respond `{ payment_required: true, redirect_url, payment_id }`. The frontend redirects the buyer
   to `redirect_url` (PostFinance's hosted payment page).

### Webhook (settlement — separate step)

When PostFinance notifies that the payment settled: `Payment → SETTLED`, `Order → PAID`, then call
the existing **`Order.confirm()`** to advance the order to `READY`. Because `/pay` already expanded
the items, `confirm()`'s expansion/resolution become no-ops — so the existing logic is fully
reused and it stamps `date_ordered`, triggers approval validations, and sets `READY`.

### Order status transitions

```
Invoice:  DRAFT/QUOTE_DONE  --confirm-->  READY
Card:     DRAFT/QUOTE_DONE  --pay-->  AWAITING_PAYMENT  --webhook settled-->  PAID  -->  READY
                                       \--webhook failed-->  PAYMENT_FAILED (buyer may retry)
Free:     DRAFT/QUOTE_DONE  --pay (total 0)-->  READY   (no payment)
```

---

## 5. Changes required

- `api/models.py`: extract `confirm()`'s two preparation calls into a small
  `_prepare_order_items()` method so the card path can reuse them. **Pure refactor — no change to
  the invoice path's behavior.** `set_price()` is deliberately *not* added to `confirm()`; only the
  card path recomputes the total.
- `api/views.py`: add the `pay` action to the order viewset.
- `api/serializers.py`: small request serializer (return URLs) + response.
- `api/payments.py`: a `start_payment(order, return_urls)` orchestrator (creates the `Payment`,
  calls `create_session`, updates the rows) so the view stays thin.

---

## 6. Open questions for the client

1. **Return URLs** — after paying, PostFinance sends the buyer back to a success and a failure URL.
   Should these be fixed frontend routes (built from configuration), or passed per-request by the
   frontend? (PostFinance supports a success and a failed URL; it has no separate "cancel" URL —
   cancellation routes to the failed URL.)
2. **Retry / abandonment** — if a buyer starts a card payment and abandons it, the order stays in
   `AWAITING_PAYMENT`. Is reusing the existing open payment on a repeat attempt acceptable, or is a
   different behavior desired (e.g. expire after some time)?
3. **Mixed carts / free orders** — confirm the free-order behavior (skip payment → `READY`) is
   correct for the client.
4. **Refunds** — out of scope for this step; a refund maps a settled payment back to `REFUNDED`.
   When does the client expect to need it?

---

## 7. What is verifiable after this step

`/pay` creating a `Payment` row, moving the order to `AWAITING_PAYMENT`, and returning a real
PostFinance redirect URL — testable end-to-end (database + sandbox). The `PAID` transition depends
on the webhook, which is the following step.
