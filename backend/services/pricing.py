"""
Cleepye pricing — Nigeria-first (NGN).

1 credit = 1 mining job (one source video processed end-to-end).
Plans only include features the product actually supports today.
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


PLANS: list[Plan] = [
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


def get_plan(plan_id: str) -> Plan:
    for p in PLANS:
        if p.id == plan_id:
            return p
    return PLANS[0]


def format_ngn(amount: int) -> str:
    return f"₦{amount:,}"


def credits_for_job() -> int:
    return 1


def credits_for_duration_seconds(duration_sec: float) -> int:
    return 1


def plans_public() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "currency": "NGN",
            "price_monthly": p.price_monthly_ngn,
            "price_label": f"{format_ngn(p.price_monthly_ngn)}/mo",
            "credits_per_month": p.credits_per_month,
            "max_clips_per_job": p.max_clips_per_job,
            "max_source_minutes": p.max_source_minutes,
            "description": p.description,
            "features": p.features,
            "popular": p.popular,
        }
        for p in PLANS
    ]

SIGNUP_BONUS_CREDITS = 5
