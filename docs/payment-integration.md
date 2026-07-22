# Payment Integration — Design Notes

**Status:** planning · **Date:** 2026-07-13 · **Provider:** not yet chosen by client

This document captures the conclusions reached while scoping online-payment support for
geoshop-back, so provider-agnostic groundwork can begin before the client picks a provider.

---

## 1. Context

The client will choose one of the six evaluated Swiss payment providers.

### Provider shortlist

| Provider    | Onboarding                          | Sandbox         | Notes                          |
|-------------|-------------------------------------|-----------------|--------------------------------|
| Datatrans   | High — needs external acquirer      | Restrictive     | Digitec Galaxus, SBB           |
| Wallee      | Moderate — all-in-one               | Instant & easy  | Swiss Post                     |
| Payrexx     | Low — SME / all-in-one friendly     | Instant & easy  | BKW, Swiss Cantons             |
| PostFinance | Low — no monthly fee                | Instant & easy  | Local municipalities           |
| Saferpay    | High — enterprise + acquirer        | Moderate        | Interdiscount                  |
| Adyen       | Volume-based (Interchange++)        | Instant & easy  | Uber, Mammut                   |

*(Full fee/KYC table lives in the colleague's analysis, checked 2026-05-27.)*

### The key insight that makes early work possible

All six share the **same integration shape**:

1. Server creates a hosted payment session with the provider.
2. Buyer's browser is redirected to the provider's hosted payment page.
3. Provider notifies us asynchronously via a **webhook**, and returns the buyer via a **return URL**.
4. We reconcile the outcome against **our own merchant reference**.

They all support **TWINT / CHF**, and because payment happens on the provider's hosted page,
we stay in the light **PCI DSS SAQ-A** scope (no card data touches our servers).

The only real difference in the table is **onboarding difficulty**, not technology:
Datatrans / Saferpay / Adyen require an external acquirer (slower, heavier KYC), whereas
Wallee / Payrexx / PostFinance are all-in-one with instant sandboxes. This affects timeline,
not the code we write.

---

## 2. Decisions reached

- **Location:** the payment logic and payment data live **inside geoshop-back**, not in a
  separate service. geoshop-back is the single source of truth ("Option A").
- **Approach:** lean toward **building the abstraction from scratch** (small) rather than adopting
  the `django-payments` library. **This is not finally decided** — see §5.
- **Validation:** build against **one instant sandbox (Payrexx or Wallee)** to prove the adapter
  interface before the client's final choice, since none of the work is throwaway.
- **First implementation:** start with **PostFinance Checkout** so we have a concrete provider to
  test against end-to-end. It will be implemented **using the official PostFinance Python SDK**,
  in the flat module **`api/payments.py`** (a single file next to the app's other modules, not a
  package — matches this app's one-module-per-concern convention).
- **Auto-capture (2026-07-21):** charge immediately on payment (a one-step "sale"), not
  authorize-now-capture-on-delivery. A failed extract is handled by a **refund**, not a released
  hold. So no `capture()`/`release()` needed; `AUTHORIZED` status stays unused for now, and payment
  flows `CREATED → PENDING → SETTLED`.
- **No provider abstraction (flat by choice, 2026-07-21):** we briefly built a `PaymentProvider`
  ABC + registry port and then **removed it**. With only one provider actually planned, an
  interface with a single implementation is speculative generality (YAGNI). PostFinance is written
  as **plain service functions** called directly by the views/order flow. An interface will be
  extracted **only if** a second provider ever appears (rule of three). The `api/payments/` package
  keeps just flat, provider-neutral value objects (`Session`, `WebhookEvent`, `ReturnUrls`) and
  error types (`PaymentError`, `WebhookVerificationError`) — data, not abstraction.

---

## 3. Current state of geoshop-back (the gap to fill)

- `Order` (`api/models.py:597`) is **pay-by-invoice only** today: it has `invoice_contact` /
  `invoice_reference`, and money via django-money `MoneyField` (`total_with_vat`, etc.).
- `OrderStatus` has **no paid / awaiting-payment states**.
- There is **no `Payment` / `Transaction` entity**, no provider transaction id, no webhook, no refund.

So regardless of provider, the same gap must be filled — and that gap is entirely provider-agnostic.

---

## 4. Provider-agnostic groundwork (buildable now)

1. **New order states** on `Order.OrderStatus`: `AWAITING_PAYMENT`, `PAYMENT_FAILED`, `PAID`.
   Additive — pay-by-invoice orders skip payment and behave exactly as today.
2. **`Payment` model** — one payment attempt per row:
   - `order` (FK), `merchant_reference` (UUID, unique — our reconciliation anchor),
   - `idempotency_key` (unique — prevents double charges on retry/double-click),
   - `provider`, `provider_transaction_id`, `status`, `amount` (snapshotted MoneyField),
   - `created_at` / `updated_at`.
3. **`PaymentEvent` model** — append-only audit trail of the **raw, verbatim** message the
   provider sent; `provider_event_id` is unique and used for webhook **dedup**.
4. **PostFinance service module** — `api/payments.py` with plain functions
   (`create_session()`, `get_status()`, `refund()`, `parse_and_verify_webhook()`) called directly.
   No abstraction layer (see §2); provider-neutral value objects live in the same file.
5. **Idempotent webhook receiver** — one endpoint that verifies the signature,
   dedups by `provider_event_id`, records the raw payload, updates payment status, and advances
   the order to `PAID` on settlement. `select_for_update` + the unique event id make concurrent
   duplicate webhooks safe.

**Waits for the client's pick:** the body of each provider file (their specific API calls +
signature scheme) and their config/secrets. Everything else above is shared.

### Glossary (terms used above)

- **FK (foreign key):** a column pointing to a row in another table — how `Payment` links to its `Order`.
- **Idempotency:** doing an operation twice has the same effect as once — critical so a retry or
  double-click never charges the buyer twice. Enforced with a unique key.
- **Raw-payload / audit trail:** storing the exact original provider message (not just the parsed
  result), for dispute evidence, reprocessing after a parsing bug, and accounting.
- **Port / adapter:** a software interface (contract of method names) that the code calls without
  knowing which concrete provider is behind it. "Ports and adapters" / hexagonal architecture.
- **Webhook dedup:** providers resend the same webhook (retries, network). Each carries a unique
  event id; if we've already processed that id, we acknowledge but do nothing, so the effect
  happens exactly once.

---

## 5. Open decision — build from scratch vs. `django-payments`

Two different libraries, easy to confuse:

- **django-money** *(already in the project)* — stores and does arithmetic on amounts of money
  (`MoneyField`). Does **not** take payments. It's a data type.
- **django-payments** *(NOT in the project)* — an actual payment abstraction: a `BasePayment`
  model, a `BaseProvider` interface, webhook routing, and prebuilt backends (Stripe, PayPal,
  Braintree, Mollie…).

|                                   | Build from scratch      | django-payments skeleton         |
|-----------------------------------|-------------------------|----------------------------------|
| Provider adapters (the real work) | We write them           | We write them (**same effort**)  |
| Model / state / webhook plumbing  | We write & maintain     | Free from the library            |
| Data model shape                  | Exactly what we want    | Their shape; we conform          |
| Dependency risk                   | None                    | One more dep to track            |
| Fit (Django, in-repo, Option A)   | Good                    | Good                             |

**Why the lean is build-from-scratch:** django-payments' biggest benefit is its prebuilt backends,
and **none of the six Swiss providers are among them** — so the provider adapters are hand-written
either way. The library would only save the model + webhook boilerplate (~a day), at the cost of a
dependency and its conventions. The from-scratch sketch is trivially portable onto django-payments
later if we change our mind.

**Not final** — the choice is still open. If we later commit hard to "payment is a Django app and
we'd rather not maintain the plumbing," django-payments becomes a fair trade.

---

## 6. Suggested next steps

1. Confirm build-from-scratch vs. django-payments (§5).
2. Spin up a Payrexx **or** Wallee sandbox to validate the adapter interface.
3. Turn the sketch into real files: `Payment` + `PaymentEvent` models, a migration, the
   `api/payments/` skeleton with one stub provider, and the webhook endpoint.
4. In parallel (client-side, not dev): gather the KYC/banking docs the chosen provider's
   acquirer will require — commercial register extract, signatory IDs, UBO/Form A declaration,
   and a bank statement proving IBAN + account holder matches the legal entity.
