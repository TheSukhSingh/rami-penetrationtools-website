from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
from extensions import db
from credits.models import Entitlement
from plans.catalog import FREE_FEATURES, PRO_FEATURES

PLAN_FEATURES = {
    "free": FREE_FEATURES,
    "pro":  PRO_FEATURES,
}

def apply_entitlements(user_id: int, plan: str) -> None:
    """
    Idempotently set entitlements for a plan.
    - Marks plan features active=1
    - Deactivates features not in plan (keeps record for audit)
    """
    if plan not in PLAN_FEATURES:
        raise ValueError(f"Unknown plan: {plan}")

    now = datetime.now(timezone.utc)
    desired = set(PLAN_FEATURES[plan])

    rows = db.session.query(Entitlement).filter(Entitlement.user_id == user_id).all()
    existing = {r.feature: r for r in rows}

    # Upsert desired -> active=1
    for feat in desired:
        row = existing.get(feat)
        if row:
            if row.active != 1:
                row.active = 1
                row.updated_at = now
                db.session.add(row)
        else:
            db.session.add(Entitlement(user_id=user_id, feature=feat, active=1, updated_at=now))

    # Deactivate everything else
    for feat, row in existing.items():
        if feat not in desired and row.active != 0:
            row.active = 0
            row.updated_at = now
            db.session.add(row)

def has_feature(user_id: int, feature: str) -> bool:
    row = db.session.query(Entitlement).filter(
        Entitlement.user_id == user_id, Entitlement.feature == feature, Entitlement.active == 1
    ).first()
    return bool(row)

def list_entitlements(user_id: int) -> dict[str, bool]:
    rows = db.session.query(Entitlement).filter(Entitlement.user_id == user_id).all()
    return { r.feature: bool(r.active) for r in rows }
