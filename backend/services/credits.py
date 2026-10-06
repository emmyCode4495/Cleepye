"""Per-user credit balance operations via Supabase."""

from __future__ import annotations

import logging
from typing import Any

from backend.services import supabase_client as sb
from backend.services.pricing import credits_for_duration_seconds, credits_for_job, get_plan

logger = logging.getLogger(__name__)


class InsufficientCredits(Exception):
    def __init__(self, balance: int, needed: int):
        self.balance = balance
        self.needed = needed
        super().__init__(f"Need {needed} credits, have {balance}")


class PlanLimitExceeded(Exception):
    def __init__(self, message: str):
        super().__init__(message)


async def get_profile(user_id: str) -> dict[str, Any] | None:
    return await sb.rest_select(
        "profiles",
        query=f"id=eq.{user_id}&select=*",
        single=True,
    )


async def get_balance(user_id: str) -> int:
    profile = await get_profile(user_id)
    if not profile:
        return 0
    return int(profile.get("credits_balance") or 0)


async def get_clarity_balance(user_id: str) -> int:
    profile = await get_profile(user_id)
    if not profile:
        return 0
    return int(profile.get("clarity_credits_balance") or 0)


class InsufficientClarityCredits(Exception):
    def __init__(self, balance: int, needed: int):
        self.balance = balance
        self.needed = needed
        super().__init__(f"Need {needed} Clarity credits, have {balance}")


async def assert_can_start_job(
    user_id: str,
    *,
    duration_sec: float | None,
    max_clips: int,
) -> dict[str, Any]:
    """
    Check plan limits + credits before/during a job.
    If duration is unknown yet (pre-download), only checks max_clips and balance > 0.
    """
    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")

    plan = get_plan(profile.get("plan_id") or "free")
    balance = int(profile.get("credits_balance") or 0)

    if plan.max_clips_per_job and max_clips > plan.max_clips_per_job:
        raise PlanLimitExceeded(
            f"Your {plan.name} plan allows up to {plan.max_clips_per_job} clips per job"
        )

    needed = credits_for_job()
    if balance < needed:
        raise InsufficientCredits(balance, needed)

    if duration_sec is not None:
        minutes = duration_sec / 60.0
        if minutes > plan.max_source_minutes:
            raise PlanLimitExceeded(
                f"Your {plan.name} plan allows sources up to {plan.max_source_minutes} minutes"
            )

    return profile



async def charge_for_job(
    user_id: str,
    *,
    duration_sec: float,
    job_id: str,
) -> dict[str, Any]:
    """Deduct credits after duration is known. Idempotent per job_id in ledger."""
    needed = credits_for_job()  # 1 credit per mine
    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")

    balance = int(profile.get("credits_balance") or 0)
    if balance < needed:
        raise InsufficientCredits(balance, needed)

    # Skip if already charged for this job
    existing = await sb.rest_select(
        "credit_ledger",
        query=f"user_id=eq.{user_id}&job_id=eq.{job_id}&reason=eq.mine_job&select=id&limit=1",
    )
    if existing:
        return {"charged": 0, "balance": balance, "already": True}

    new_balance = balance - needed
    await sb.rest_patch(
        "profiles",
        query=f"id=eq.{user_id}",
        body={"credits_balance": new_balance},
    )
    await sb.rest_insert(
        "credit_ledger",
        {
            "user_id": user_id,
            "delta": -needed,
            "reason": "mine_job",
            "job_id": job_id,
            "metadata": {"duration_sec": duration_sec, "credits": needed},
        },
    )
    logger.info(f"Charged {needed} credits to {user_id} for job {job_id}; balance={new_balance}")
    return {"charged": needed, "balance": new_balance, "already": False}


async def grant_credits(
    user_id: str,
    amount: int,
    *,
    reason: str,
    metadata: dict | None = None,
) -> int:
    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")
    balance = int(profile.get("credits_balance") or 0)
    new_balance = balance + amount
    await sb.rest_patch(
        "profiles",
        query=f"id=eq.{user_id}",
        body={"credits_balance": new_balance},
    )
    await sb.rest_insert(
        "credit_ledger",
        {
            "user_id": user_id,
            "delta": amount,
            "reason": reason,
            "metadata": metadata or {},
        },
    )
    return new_balance


async def activate_subscription(
    user_id: str,
    *,
    plan_id: str,
    tx_ref: str,
    provider: str = "flutterwave",
    amount_ngn: int | None = None,
) -> dict[str, Any]:
    """
    Idempotent: set plan + grant monthly credits once per tx_ref.
    """
    from backend.services.pricing import get_plan

    plan = get_plan(plan_id)
    # Already processed this payment?
    existing = await sb.rest_select(
        "credit_ledger",
        query=f"user_id=eq.{user_id}&reason=eq.subscription_grant&select=id,metadata&order=created_at.desc&limit=20",
    )
    if existing:
        for row in existing:
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                continue
            if meta.get("tx_ref") == tx_ref:
                profile = await get_profile(user_id)
                return {
                    "already": True,
                    "plan_id": plan_id,
                    "credits_balance": int((profile or {}).get("credits_balance") or 0),
                }

    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")

    balance = int(profile.get("credits_balance") or 0)
    clarity_balance = int(profile.get("clarity_credits_balance") or 0)
    # Grant full monthly allowances (stack on remaining credits)
    new_balance = balance + plan.credits_per_month
    new_clarity = clarity_balance + int(getattr(plan, "clarity_credits_per_month", 0) or 0)

    await sb.rest_patch(
        "profiles",
        query=f"id=eq.{user_id}",
        body={
            "plan_id": plan.id,
            "credits_balance": new_balance,
            "credits_monthly_allowance": plan.credits_per_month,
            "clarity_credits_balance": new_clarity,
            "clarity_monthly_allowance": int(getattr(plan, "clarity_credits_per_month", 0) or 0),
            "subscription_status": "active",
        },
    )
    await sb.rest_insert(
        "credit_ledger",
        {
            "user_id": user_id,
            "delta": plan.credits_per_month,
            "reason": "subscription_grant",
            "metadata": {
                "tx_ref": tx_ref,
                "provider": provider,
                "plan_id": plan.id,
                "amount_ngn": amount_ngn,
                "credits_granted": plan.credits_per_month,
                "clarity_credits_granted": int(getattr(plan, "clarity_credits_per_month", 0) or 0),
            },
        },
    )
    if new_clarity > clarity_balance:
        await sb.rest_insert(
            "credit_ledger",
            {
                "user_id": user_id,
                "delta": new_clarity - clarity_balance,
                "reason": "clarity_subscription_grant",
                "metadata": {
                    "tx_ref": tx_ref,
                    "provider": provider,
                    "plan_id": plan.id,
                    "clarity_credits_granted": new_clarity - clarity_balance,
                },
            },
        )
    logger.info(
        f"Subscription activated user={user_id} plan={plan.id} "
        f"+{plan.credits_per_month} mining +{getattr(plan, 'clarity_credits_per_month', 0)} clarity tx={tx_ref}"
    )
    return {
        "already": False,
        "plan_id": plan.id,
        "credits_granted": plan.credits_per_month,
        "clarity_credits_granted": int(getattr(plan, "clarity_credits_per_month", 0) or 0),
        "credits_balance": new_balance,
        "clarity_credits_balance": new_clarity,
    }



async def assert_can_use_clarity(
    user_id: str,
    *,
    workflow_id: str,
    duration_sec: float = 0,
    media: str = "video",
) -> dict[str, Any]:
    from backend.services.pricing import clarity_allowed, estimate_clarity_credits, get_plan

    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")
    plan_id = profile.get("plan_id") or "free"
    if not clarity_allowed(plan_id, workflow_id):
        plan = get_plan(plan_id)
        raise PlanLimitExceeded(
            f"Clarity workflow not available on {plan.name}. Upgrade for more options."
        )
    needed = estimate_clarity_credits(workflow_id, duration_sec=duration_sec, media=media)
    balance = int(profile.get("clarity_credits_balance") or 0)
    if balance < needed:
        raise InsufficientClarityCredits(balance, needed)
    return {"profile": profile, "needed": needed, "balance": balance}


async def charge_clarity(
    user_id: str,
    *,
    amount: int,
    job_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Deduct Clarity credits. Idempotent per job_id."""
    if amount <= 0:
        return {"charged": 0, "balance": await get_clarity_balance(user_id)}
    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")
    balance = int(profile.get("clarity_credits_balance") or 0)
    if balance < amount:
        raise InsufficientClarityCredits(balance, amount)
    existing = await sb.rest_select(
        "credit_ledger",
        query=f"user_id=eq.{user_id}&job_id=eq.{job_id}&reason=eq.clarity_job&select=id&limit=1",
    )
    if existing:
        return {"charged": 0, "balance": balance, "already": True}
    new_balance = balance - amount
    await sb.rest_patch(
        "profiles",
        query=f"id=eq.{user_id}",
        body={"clarity_credits_balance": new_balance},
    )
    await sb.rest_insert(
        "credit_ledger",
        {
            "user_id": user_id,
            "delta": -amount,
            "reason": "clarity_job",
            "job_id": job_id,
            "metadata": {"workflow": workflow_id, "clarity_credits": amount},
        },
    )
    return {"charged": amount, "balance": new_balance, "already": False}


async def grant_clarity_credits(
    user_id: str,
    amount: int,
    *,
    reason: str,
    metadata: dict | None = None,
) -> int:
    profile = await get_profile(user_id)
    if not profile:
        raise PermissionError("Profile not found")
    balance = int(profile.get("clarity_credits_balance") or 0)
    new_balance = balance + amount
    await sb.rest_patch(
        "profiles",
        query=f"id=eq.{user_id}",
        body={"clarity_credits_balance": new_balance},
    )
    await sb.rest_insert(
        "credit_ledger",
        {
            "user_id": user_id,
            "delta": amount,
            "reason": reason,
            "metadata": metadata or {},
        },
    )
    return new_balance
