"""
Payment integration.

Deliberately flat: there is no provider abstraction layer. This single module holds
the whole payment integration -- the small, provider-neutral value objects and error
types below, and the PostFinance service functions that the views/order flow call
directly.

The value objects are plain data, not an abstraction: they document the shapes that
cross into and out of the provider code. If a second provider is ever needed, split
this module then -- not before.

PostFinance Checkout is integrated via its official SDK (``postfinancecheckout``). The
SDK's verbose, path-style method names are wrapped by the small functions here so the
rest of geoshop only ever sees ``create_session`` / ``get_status`` / etc.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings

from postfinancecheckout import (
    Configuration,
    LineItemCreate,
    LineItemType,
    TransactionCreate,
    TransactionEnvironmentSelectionStrategy,
    TransactionsService,
    WebhookEncryptionKeysService,
)

if TYPE_CHECKING:
    from api.models import Payment

LOGGER = logging.getLogger(__name__)


class PaymentError(Exception):
    """Base class for payment errors."""


class WebhookVerificationError(PaymentError):
    """Raised when an incoming webhook fails signature/authenticity verification."""


@dataclass(frozen=True)
class ReturnUrls:
    """Where the provider sends the buyer's browser back to after the hosted page."""

    success: str
    failure: str
    cancel: str


@dataclass(frozen=True)
class Session:
    """Result of opening a hosted-payment session with the provider."""

    # The provider's own id for the transaction, stored on Payment.provider_transaction_id.
    provider_transaction_id: str
    # The hosted payment page the buyer's browser must be redirected to.
    redirect_url: str


@dataclass(frozen=True)
class WebhookEvent:
    """A verified, parsed webhook normalised to geoshop's own vocabulary."""

    # The provider's unique id for this event -- the dedup key (see PaymentEvent).
    provider_event_id: str
    # The provider's transaction id (webhook `entityId`), matched to Payment.provider_transaction_id.
    provider_transaction_id: str
    # The provider's outcome mapped onto our PaymentStatus.
    new_status: "Payment.PaymentStatus"
    # The exact, verbatim payload as received, stored on PaymentEvent.raw_payload.
    raw_payload: dict


# --- PostFinance Checkout ---------------------------------------------------------

PROVIDER_NAME = "postfinance"


def _space_id() -> int:
    """The PostFinance Space id, passed to every SDK call."""
    return int(settings.POSTFINANCE_SPACE_ID)


def _configuration() -> Configuration:
    """Build an authenticated SDK configuration from settings (Application User creds)."""
    return Configuration(
        user_id=str(settings.POSTFINANCE_USER_ID),
        authentication_key=settings.POSTFINANCE_API_SECRET,
    )


def _payment_page_url(provider_transaction_id) -> str:
    """The hosted payment-page URL for an existing PostFinance transaction."""
    service = TransactionsService(_configuration())
    return service.get_payment_transactions_id_payment_page_url(
        int(provider_transaction_id), _space_id()
    )


def create_session(payment: "Payment", return_urls: "ReturnUrls") -> "Session":
    """
    Open a hosted-payment session for ``payment`` and return where to redirect the
    buyer. Sends our ``merchant_reference`` and amount to PostFinance; the created
    transaction starts PENDING and is settled via the hosted page + webhook.
    """
    service = TransactionsService(_configuration())
    space = _space_id()

    line_item = LineItemCreate(
        name="Geoshop order %s" % payment.order_id,
        unique_id=str(payment.merchant_reference),
        quantity=1,
        # PostFinance derives the transaction total from the sum of its line items.
        amount_including_tax=float(payment.amount.amount),
        type=LineItemType.PRODUCT,
    )
    # Force test vs production per settings. Defaults to test, so we never accidentally
    # take a real payment against a space that happens to have live connectors.
    if settings.POSTFINANCE_TEST_MODE:
        environment_strategy = TransactionEnvironmentSelectionStrategy.FORCE_TEST_ENVIRONMENT
    else:
        environment_strategy = TransactionEnvironmentSelectionStrategy.FORCE_PRODUCTION_ENVIRONMENT

    transaction_create = TransactionCreate(
        currency=str(payment.amount.currency),
        line_items=[line_item],
        merchant_reference=str(payment.merchant_reference),
        success_url=return_urls.success,
        failed_url=return_urls.failure,
        environment_selection_strategy=environment_strategy,
    )

    transaction = service.post_payment_transactions(space, transaction_create)
    redirect_url = _payment_page_url(transaction.id)
    LOGGER.info(
        "Opened PostFinance transaction %s for payment %s", transaction.id, payment.merchant_reference
    )
    return Session(provider_transaction_id=str(transaction.id), redirect_url=redirect_url)


def start_payment(order, return_urls: "ReturnUrls") -> "tuple[Payment, str]":
    """
    Orchestrate a card payment for a finalized, fully-priced ``order``.

    The caller (the ``/pay`` view) must have already finalized the order's contents
    and recomputed its price (``_prepare_order_items()`` + ``set_price()``), so
    ``order.total_with_vat`` is the definitive amount to charge.

    Behaviour:
    - If the order already has an in-flight payment (a ``CREATED``/``PENDING`` row that
      already opened a PostFinance transaction), reuse it -- never charge twice.
    - Otherwise create a ``Payment`` row first (so a local trace survives even if the
      provider call fails), open a PostFinance session, then record the provider
      transaction, mark the payment ``PENDING``, and move the order to
      ``AWAITING_PAYMENT``.

    Returns ``(payment, redirect_url)``.
    """
    from django.db import transaction as db_transaction

    from api.models import Order, Payment  # local import avoids any import cycle

    if order.total_with_vat is None:
        raise PaymentError(
            "Cannot start a card payment for order %s: it is not fully priced." % order.id
        )

    # Dedup: an order should have at most one in-flight payment.
    open_payment = order.payments.filter(
        status__in=(Payment.PaymentStatus.CREATED, Payment.PaymentStatus.PENDING)
    ).first()
    if open_payment and open_payment.provider_transaction_id:
        LOGGER.info(
            "Reusing in-flight payment %s for order %s", open_payment.merchant_reference, order.id
        )
        return open_payment, _payment_page_url(open_payment.provider_transaction_id)

    # Local record first, so we keep a trace even if the provider call fails.
    payment = open_payment or Payment.objects.create(
        order=order,
        amount=order.total_with_vat,
        provider=PROVIDER_NAME,
        status=Payment.PaymentStatus.CREATED,
    )

    session = create_session(payment, return_urls)

    with db_transaction.atomic():
        payment.provider_transaction_id = session.provider_transaction_id
        payment.status = Payment.PaymentStatus.PENDING
        payment.save(update_fields=["provider_transaction_id", "status", "updated_at"])
        order.order_status = Order.OrderStatus.AWAITING_PAYMENT
        order.save(update_fields=["order_status"])

    LOGGER.info(
        "Started payment %s for order %s (%s)", payment.merchant_reference, order.id, payment.amount
    )
    return payment, session.redirect_url


# PostFinance TransactionState -> our PaymentStatus value. Only FULFILL means "paid,
# deliver"; COMPLETED/AUTHORIZED are funds-in-flight but not yet safe to fulfil (per
# PostFinance docs). Unknown states map to PENDING (never settle on a state we don't know).
_STATE_TO_STATUS = {
    "FULFILL": "SETTLED",
    "AUTHORIZED": "AUTHORIZED",
    "COMPLETED": "AUTHORIZED",
    "FAILED": "FAILED",
    "DECLINE": "FAILED",
    "VOIDED": "CANCELED",
    "CONFIRMED": "PENDING",
    "PROCESSING": "PENDING",
    "PENDING": "PENDING",
    "CREATE": "CREATED",
}


def get_status(provider_transaction_id) -> "Payment.PaymentStatus":
    """Read a transaction's authoritative state from PostFinance, mapped to our PaymentStatus."""
    service = TransactionsService(_configuration())
    transaction = service.get_payment_transactions_id(int(provider_transaction_id), _space_id())
    state = getattr(transaction.state, "value", transaction.state)
    return _STATE_TO_STATUS.get(str(state), "PENDING")


def refund(provider_transaction_id: str, amount) -> None:
    """Refund a settled transaction."""
    raise NotImplementedError  # not in scope yet


def parse_and_verify_webhook(request) -> "WebhookEvent":
    """
    Verify an incoming PostFinance webhook and parse it into a :class:`WebhookEvent`.

    Authenticity: the request carries an ``X-Signature`` header; the SDK's
    ``is_content_valid`` fetches the matching public key and checks the raw body against
    it. A missing/invalid signature raises :class:`WebhookVerificationError`.

    The verified body carries only ids (``eventId``, ``entityId`` = the transaction id);
    the authoritative status is then read back from PostFinance via ``get_status`` -- we
    never trust a status value from the POST body itself.
    """
    signature = request.headers.get("X-Signature")
    raw_body = request.body.decode("utf-8")
    if not signature:
        raise WebhookVerificationError("Missing X-Signature header")
    try:
        is_valid = WebhookEncryptionKeysService(_configuration()).is_content_valid(signature, raw_body)
    except Exception as exc:  # SDK raises on malformed header / unknown key
        raise WebhookVerificationError("Could not verify webhook signature: %s" % exc)
    if not is_valid:
        raise WebhookVerificationError("Webhook signature does not match the payload")

    payload = json.loads(raw_body)
    provider_transaction_id = str(payload.get("entityId"))
    return WebhookEvent(
        provider_event_id=str(payload.get("eventId")),
        provider_transaction_id=provider_transaction_id,
        new_status=get_status(provider_transaction_id),
        raw_payload=payload,
    )
