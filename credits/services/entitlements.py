from __future__ import annotations
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
    - Optionally deactivates features not in plan (keeps record for audit)
    """
    desired = set(PLAN_FEATURES.get(plan, []))
    # Fetch existing rows
    rows = db.session.query(Entitlement).filter(Entitlement.user_id == user_id).all()
    existing = { (r.feature): r for r in rows }

    # Upsert desired -> active=1
    for feat in desired:
        row = existing.get(feat)
        if row:
            if row.active != 1:
                row.active = 1
                db.session.add(row)
        else:
            db.session.add(Entitlement(user_id=user_id, feature=feat, active=1))

    # Deactivate others
    for feat, row in existing.items():
        if feat not in desired and row.active != 0:
            row.active = 0
            db.session.add(row)

def has_feature(user_id: int, feature: str) -> bool:
    row = db.session.query(Entitlement).filter(
        Entitlement.user_id == user_id, Entitlement.feature == feature, Entitlement.active == 1
    ).first()
    return bool(row)

def list_entitlements(user_id: int) -> dict[str, bool]:
    rows = db.session.query(Entitlement).filter(Entitlement.user_id == user_id).all()
    return { r.feature: bool(r.active) for r in rows }
