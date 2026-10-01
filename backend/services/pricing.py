"""
Cleepye pricing — Nigeria-first (NGN).

1 credit = 1 mining job (one source video processed end-to-end).
Plan limits are enforced in the API and UI (clips, source length).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_monthly_ngn: int
    credits_per_month: int
    max_clips_per_job: int  # 0 = unlimited
    max_source_minutes: int
    features: list[str] = field(default_factory=list)
    popular: bool = False
    description: str = ""
    # Shown on pricing page only when price > 0
    listed: bool = True


PLANS: list[Plan] = [
    Plan(
        id="free",
        name="Free",
        price_monthly_ngn=0,
        credits_per_month=2,
        max_clips_per_job=1,
        max_source_minutes=15,
        description="Try Cleepye with 2 free credits before you subscribe.",
        features=[
            "2 free mining credits",
            "1 clip per mine",
            "Sources up to 15 minutes",
            "Word-level captions",
            "9:16 smart reframe",
        ],
        listed=False,  # not sold on pricing page
    ),
    Plan(
        id="starter",
        name="Starter",
        price_monthly_ngn=10_000,
        credits_per_month=8,
        max_clips_per_job=8,
        max_source_minutes=45,
        description="For creators getting started with weekly clips.",
        features=[
            "8 mining credits each month",
            "Up to 8 clips per mine",
            "Sources up to 45 minutes",
            "Word-level animated captions",
            "Custom font upload",
            "9:16 smart reframe",
            "HD export",
            "Job history on your account",
        ],
    ),
    Plan(
        id="creator",
        name="Creator",
        price_monthly_ngn=20_000,
        credits_per_month=20,
        max_clips_per_job=12,
        max_source_minutes=90,
        popular=True,
        description="For regular publishing and longer videos.",
        features=[
            "20 mining credits each month",
            "Up to 12 clips per mine",
            "Sources up to 90 minutes",
            "All caption styles",
            "Custom font upload",
            "9:16 smart reframe",
            "Full HD export",
            "Job history on your account",
        ],
    ),
    Plan(
        id="pro",
        name="Pro",
        price_monthly_ngn=35_000,
        credits_per_month=40,
        max_clips_per_job=0,  # unlimited
        max_source_minutes=180,
        description="For heavy use and longer-form content.",
        features=[
            "40 mining credits each month",
            "Unlimited clips per mine",
            "Sources up to 3 hours",
            "All caption styles",
            "Custom font upload",
            "9:16 smart reframe",
            "Full HD & 4K export",
            "Job history on your account",
        ],
    ),
]

CREDIT_PACKS = [
    {"id": "pack_5", "credits": 5, "price_ngn": 7_500, "label": "5 credits"},
    {"id": "pack_15", "credits": 15, "price_ngn": 18_000, "label": "15 credits"},
    {"id": "pack_40", "credits": 40, "price_ngn": 40_000, "label": "40 credits"},
]

PAYMENT_PROVIDER_ORDER = ("flutterwave", "paystack", "korapay")
SIGNUP_BONUS_CREDITS = 2


def get_plan(plan_id: str) -> Plan:
    for p in PLANS:
        if p.id == plan_id:
            return p
    return PLANS[0]  # free


def format_ngn(amount: int) -> str:
    return f"₦{amount:,}"


def credits_for_job() -> int:
    return 1


def credits_for_duration_seconds(duration_sec: float) -> int:
    return 1


def max_clips_for_plan(plan_id: str) -> int:
    """UI/API cap. 0 in plan means unlimited → return a hard ceiling."""
    plan = get_plan(plan_id)
    if plan.max_clips_per_job <= 0:
        return 20
    return plan.max_clips_per_job


def plans_public() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "currency": "NGN",
            "price_monthly": p.price_monthly_ngn,
            "price_label": "Free" if p.price_monthly_ngn == 0 else f"{format_ngn(p.price_monthly_ngn)}/mo",
            "credits_per_month": p.credits_per_month,
            "max_clips_per_job": p.max_clips_per_job,
            "max_source_minutes": p.max_source_minutes,
            "description": p.description,
            "features": p.features,
            "popular": p.popular,
        }
        for p in PLANS
        if p.listed and p.price_monthly_ngn > 0
    ]
