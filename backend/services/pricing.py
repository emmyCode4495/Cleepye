"""
Cleepye pricing — Nigeria-first (NGN).

Two credit meters:
  - Mining credits: 1 credit = 1 mining job (one source video).
  - Clarity credits: used for enhance / upscale / slow-mo / HDR / images (Topaz under the hood).

Free: 1 mining credit only. No Clarity credits.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_monthly_ngn: int
    credits_per_month: int  # mining credits
    clarity_credits_per_month: int
    max_clips_per_job: int  # 0 = unlimited
    max_source_minutes: int
    features: list[str] = field(default_factory=list)
    popular: bool = False
    description: str = ""
    listed: bool = True
    # Clarity workflow access
    clarity_all_workflows: bool = False  # Pro: Creative, Ultra, HDR, etc.
    clarity_advanced: bool = False  # Creator: all except Creative


PLANS: list[Plan] = [
    Plan(
        id="free",
        name="Free",
        price_monthly_ngn=0,
        credits_per_month=1,
        clarity_credits_per_month=0,
        max_clips_per_job=1,
        max_source_minutes=15,
        description="Mine your first video free. Clarity requires a paid plan.",
        features=[
            "1 free mining credit (first video)",
            "1 clip per mine",
            "Sources up to 15 minutes",
            "Word-level captions",
            "9:16 smart reframe",
            "No Clarity credits — upgrade to enhance",
        ],
        listed=False,
    ),
    Plan(
        id="starter",
        name="Starter",
        price_monthly_ngn=10_000,
        credits_per_month=8,
        clarity_credits_per_month=40,
        max_clips_per_job=8,
        max_source_minutes=45,
        description="For creators getting started with weekly clips.",
        features=[
            "8 mining credits each month",
            "40 Clarity credits each month",
            "Up to 8 clips per mine",
            "Sources up to 45 minutes",
            "Precise enhance & smooth motion",
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
        clarity_credits_per_month=120,
        max_clips_per_job=12,
        max_source_minutes=90,
        popular=True,
        clarity_advanced=True,
        description="For regular publishing, longer videos, and Clarity enhance.",
        features=[
            "20 mining credits each month",
            "120 Clarity credits each month",
            "Up to 12 clips per mine",
            "Sources up to 90 minutes",
            "All Clarity workflows except Creative",
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
        clarity_credits_per_month=300,
        max_clips_per_job=0,  # unlimited
        max_source_minutes=180,
        clarity_all_workflows=True,
        clarity_advanced=True,
        description="For heavy mining and full Clarity (Creative, Ultra, HDR).",
        features=[
            "40 mining credits each month",
            "300 Clarity credits each month",
            "Unlimited clips per mine",
            "Sources up to 3 hours",
            "All Clarity workflows (incl. Creative & HDR)",
            "All caption styles",
            "Custom font upload",
            "9:16 smart reframe",
            "Full HD & 4K export",
            "Job history on your account",
        ],
    ),
]

# Mining top-ups (cheap for you)
CREDIT_PACKS = [
    {"id": "pack_5", "credits": 5, "price_ngn": 4_000, "label": "5 mining credits", "type": "mining"},
    {"id": "pack_15", "credits": 15, "price_ngn": 10_000, "label": "15 mining credits", "type": "mining"},
    {"id": "pack_40", "credits": 40, "price_ngn": 22_000, "label": "40 mining credits", "type": "mining"},
]

# Clarity top-ups (priced off Topaz cost)
CLARITY_PACKS = [
    {"id": "clarity_50", "credits": 50, "price_ngn": 6_000, "label": "50 Clarity credits", "type": "clarity"},
    {"id": "clarity_150", "credits": 150, "price_ngn": 15_000, "label": "150 Clarity credits", "type": "clarity"},
    {"id": "clarity_400", "credits": 400, "price_ngn": 35_000, "label": "400 Clarity credits", "type": "clarity"},
]

PAYMENT_PROVIDER_ORDER = ("flutterwave", "paystack", "korapay")

# New users: 1 mining credit only. Zero Clarity.
SIGNUP_BONUS_CREDITS = 1
SIGNUP_BONUS_CLARITY = 0


# ---------------------------------------------------------------------------
# Clarity burn rates (user-facing Clarity credits)
# ---------------------------------------------------------------------------
CLARITY_BURN: dict[str, dict[str, int | float]] = {
    # images: flat
    "wonder": {"per_job": 2},
    "bloom": {"per_job": 2},
    "standard": {"per_job": 1},
    "denoise": {"per_job": 1},
    "portrait": {"per_job": 2},
    "restore": {"per_job": 2},
    "high_fidelity": {"per_job": 2},
    "low_res": {"per_job": 3},
    # video: per 10 seconds of *source* (or output for slow-mo)
    "precise": {"per_10s": 5},
    "creative": {"per_10s": 40},
    "sharp": {"per_10s": 8},
    "ultra": {"per_10s": 15},
    "smooth": {"per_10s": 3},
    "slowmo_2x": {"per_10s": 5},
    "slowmo_4x": {"per_10s": 10},
    "slowmo_8x": {"per_10s": 20},
    "hdr": {"per_10s": 4},
    # mine-pipeline aliases
    "standard_video": {"per_10s": 5},
}


# Workflows allowed by plan
STARTER_CLARITY = {"precise", "smooth", "standard", "denoise", "high_fidelity"}
CREATOR_CLARITY = STARTER_CLARITY | {
    "sharp", "ultra", "slowmo_2x", "slowmo_4x", "hdr",
    "wonder", "bloom", "portrait", "restore", "low_res",
}
PRO_CLARITY = CREATOR_CLARITY | {"creative", "slowmo_8x"}


def clarity_allowed(plan_id: str, workflow_id: str) -> bool:
    plan = get_plan(plan_id)
    wid = (workflow_id or "precise").lower()
    if plan.id == "pro" or plan.clarity_all_workflows:
        return True
    if plan.id == "creator":
        return wid in CREATOR_CLARITY
    if plan.id == "starter":
        return wid in STARTER_CLARITY
    return False  # free: no Clarity


def estimate_clarity_credits(workflow_id: str, *, duration_sec: float = 0, media: str = "video") -> int:
    """Estimate Clarity credits for a job. Minimum 1 if any work."""
    wid = (workflow_id or "precise").lower()
    if media == "image" or wid in {
        "wonder", "bloom", "standard", "denoise", "portrait", "restore", "high_fidelity", "low_res"
    }:
        cfg = CLARITY_BURN.get(wid) or {"per_job": 1}
        return max(1, int(cfg.get("per_job") or 1))
    cfg = CLARITY_BURN.get(wid) or {"per_10s": 5}
    per_10 = float(cfg.get("per_10s") or 5)
    secs = max(float(duration_sec or 0), 1.0)
    return max(1, int((secs / 10.0) * per_10 + 0.999))  # ceil


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
            "clarity_credits_per_month": p.clarity_credits_per_month,
            "max_clips_per_job": p.max_clips_per_job,
            "max_source_minutes": p.max_source_minutes,
            "description": p.description,
            "features": p.features,
            "popular": p.popular,
            "clarity_all_workflows": p.clarity_all_workflows,
            "clarity_advanced": p.clarity_advanced,
        }
        for p in PLANS
        if p.listed and p.price_monthly_ngn > 0
    ]


def packs_public() -> dict:
    return {
        "mining": CREDIT_PACKS,
        "clarity": CLARITY_PACKS,
    }
