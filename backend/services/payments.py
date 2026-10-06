"""
Payment providers for Nigeria: Flutterwave (primary) → Paystack → Korapay.
Uses the first provider that is configured and responds successfully.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx

from backend.config import get_settings
from backend.services.pricing import PAYMENT_PROVIDER_ORDER, get_plan, format_money, price_for_plan

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    def __init__(self, message: str, provider: str | None = None):
        self.provider = provider
        super().__init__(message)


def _configured_providers() -> list[str]:
    s = get_settings()
    available = []
    for name in PAYMENT_PROVIDER_ORDER:
        if name == "flutterwave" and s.flutterwave_secret_key:
            available.append(name)
        elif name == "paystack" and s.paystack_secret_key:
            available.append(name)
        elif name == "korapay" and s.korapay_secret_key:
            available.append(name)
    return available


async def _flutterwave_init(
    *,
    amount: int,
    currency: str,
    email: str,
    tx_ref: str,
    title: str,
    redirect_url: str,
    meta: dict,
) -> dict[str, Any]:
    s = get_settings()
    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,
        "redirect_url": redirect_url,
        "customer": {"email": email},
        "customizations": {"title": title, "logo": ""},
        "meta": meta,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.flutterwave.com/v3/payments",
            headers={
                "Authorization": f"Bearer {s.flutterwave_secret_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()
        if resp.status_code >= 400 or data.get("status") != "success":
            raise PaymentError(data.get("message") or "Flutterwave init failed", "flutterwave")
        link = data.get("data", {}).get("link")
        if not link:
            raise PaymentError("Flutterwave did not return a payment link", "flutterwave")
        return {"provider": "flutterwave", "payment_url": link, "reference": tx_ref, "raw": data}


async def _paystack_init(
    *,
    amount: int,
    currency: str,
    email: str,
    tx_ref: str,
    title: str,
    redirect_url: str,
    meta: dict,
) -> dict[str, Any]:
    s = get_settings()
    # Paystack: kobo for NGN, cents for USD
    subunit = amount * 100
    payload = {
        "email": email,
        "amount": subunit,
        "currency": currency,
        "reference": tx_ref,
        "callback_url": redirect_url,
        "metadata": {**meta, "title": title},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {s.paystack_secret_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()
        if resp.status_code >= 400 or not data.get("status"):
            raise PaymentError(data.get("message") or "Paystack init failed", "paystack")
        link = data.get("data", {}).get("authorization_url")
        if not link:
            raise PaymentError("Paystack did not return a payment link", "paystack")
        return {"provider": "paystack", "payment_url": link, "reference": tx_ref, "raw": data}


async def _korapay_init(
    *,
    amount: int,
    currency: str,
    email: str,
    tx_ref: str,
    title: str,
    redirect_url: str,
    meta: dict,
) -> dict[str, Any]:
    s = get_settings()
    payload = {
        "amount": amount,
        "currency": currency,
        "reference": tx_ref,
        "redirect_url": redirect_url,
        "customer": {"email": email},
        "narration": title,
        "notification_url": s.payment_webhook_url or None,
        "metadata": meta,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.korapay.com/merchant/api/v1/charges/initialize",
            headers={
                "Authorization": f"Bearer {s.korapay_secret_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()
        if resp.status_code >= 400 or not data.get("status"):
            raise PaymentError(
                (data.get("message") or data.get("error") or "Korapay init failed"),
                "korapay",
            )
        link = (
            data.get("data", {}).get("checkout_url")
            or data.get("data", {}).get("payment_url")
        )
        if not link:
            raise PaymentError("Korapay did not return a payment link", "korapay")
        return {"provider": "korapay", "payment_url": link, "reference": tx_ref, "raw": data}


_INITERS = {
    "flutterwave": _flutterwave_init,
    "paystack": _paystack_init,
    "korapay": _korapay_init,
}


async def initiate_subscription_payment(
    *,
    plan_id: str,
    email: str,
    user_id: str,
    redirect_url: str,
    currency: str = "NGN",
) -> dict[str, Any]:
    plan = get_plan(plan_id)
    currency = "NGN" if currency == "NGN" else "USD"
    amount = price_for_plan(plan, currency)
    if amount <= 0:
        raise PaymentError("This plan is free — no payment required")
    tx_ref = f"cleepye_{plan_id}_{user_id[:8]}_{secrets.token_hex(6)}"
    title = f"Cleepye {plan.name} — {format_money(amount, currency)}/mo"
    meta = {
        "user_id": user_id,
        "plan_id": plan_id,
        "product": "subscription",
        "currency": currency,
        "amount": amount,
    }

    providers = _configured_providers()
    if not providers:
        raise PaymentError(
            "No payment provider configured. Set FLUTTERWAVE_SECRET_KEY, PAYSTACK_SECRET_KEY, or KORAPAY_SECRET_KEY."
        )

    errors: list[str] = []
    for name in providers:
        try:
            logger.info(
                f"Initiating payment via {name} for plan={plan_id} amount={amount} {currency}"
            )
            result = await _INITERS[name](
                amount=amount,
                currency=currency,
                email=email,
                tx_ref=tx_ref,
                title=title,
                redirect_url=redirect_url,
                meta=meta,
            )
            return {
                **result,
                "amount": amount,
                "amount_ngn": plan.price_monthly_ngn if currency == "NGN" else None,
                "amount_usd": plan.price_monthly_usd if currency == "USD" else None,
                "plan_id": plan_id,
                "currency": currency,
            }
        except Exception as e:
            logger.warning(f"Payment provider {name} failed: {e}")
            errors.append(f"{name}: {e}")
            continue

    raise PaymentError(
        "All payment providers failed. " + " | ".join(errors)
    )


async def verify_flutterwave_tx(tx_ref: str) -> dict[str, Any]:
    """Confirm a transaction with Flutterwave (source of truth)."""
    s = get_settings()
    if not s.flutterwave_secret_key:
        raise PaymentError("Flutterwave not configured", "flutterwave")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://api.flutterwave.com/v3/transactions/verify_by_reference",
            params={"tx_ref": tx_ref},
            headers={"Authorization": f"Bearer {s.flutterwave_secret_key}"},
        )
        data = resp.json()
        if resp.status_code >= 400 or data.get("status") != "success":
            raise PaymentError(data.get("message") or "Verify failed", "flutterwave")
        return data.get("data") or {}


def flutterwave_hash_ok(verif_hash: str | None) -> bool:
    """Compare webhook verif-hash header to secret hash from dashboard."""
    s = get_settings()
    expected = (s.flutterwave_secret_hash or "").strip()
    if not expected:
        # If hash not set, allow but log — set FLUTTERWAVE_SECRET_HASH in production
        logger.warning("FLUTTERWAVE_SECRET_HASH not set; webhook signature not verified")
        return True
    if not verif_hash:
        return False
    import hmac
    return hmac.compare_digest(verif_hash.strip(), expected)
