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
