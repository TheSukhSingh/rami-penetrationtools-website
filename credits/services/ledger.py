from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from extensions import db
from credits.models import LedgerEntry, BalanceSnapshot, CreditUserState, CreditBucket, LedgerType
from plans.catalog import DAILY_FREE_CREDITS


class CreditError(Exception):
    pass


class InsufficientCredits(CreditError):
    pass

def _lock_snapshot(user_id: int) -> BalanceSnapshot:
    snap = db.session.get(BalanceSnapshot, user_id, with_for_update=True)
    if not snap:
        snap = BalanceSnapshot(user_id=user_id, daily_mic=0, monthly_mic=0, topup_mic=0, version=0)
        db.session.add(snap)
        db.session.flush()
    return snap

def ensure_daily_grant(user_id: int, grant_mic: int = DAILY_FREE_CREDITS, ref_prefix: str = "daily_") -> None:
    today_utc = datetime.now(timezone.utc).date()

    state = db.session.get(CreditUserState, user_id, with_for_update=True)
    if not state:
        state = CreditUserState(user_id=user_id)
        db.session.add(state)
        db.session.flush()
    if state.last_daily_grant_utc == today_utc:
        return
    # grant
    snap = _lock_snapshot(user_id)
    snap.daily_mic += grant_mic
    snap.version += 1
    snap.updated_at = datetime.now(timezone.utc)
    db.session.add(LedgerEntry(user_id=user_id, type=LedgerType.GRANT, bucket=CreditBucket.DAILY, amount_mic=grant_mic, ref=f"{ref_prefix}{today_utc.isoformat()}"))
    state.last_daily_grant_utc = today_utc


def grant_monthly(user_id: int, amount_mic: int, ref: str) -> None:
    try:
        db.session.add(LedgerEntry(user_id=user_id, type=LedgerType.GRANT, bucket=CreditBucket.MONTHLY, amount_mic=amount_mic, ref=ref))
        snap = _lock_snapshot(user_id)
        snap.monthly_mic += amount_mic
        snap.version += 1
        snap.updated_at = datetime.now(timezone.utc)
    except IntegrityError:
        db.session.rollback()

def grant_topup(user_id: int, amount_mic: int, ref: str) -> None:
    try:
        db.session.add(LedgerEntry(user_id=user_id, type=LedgerType.GRANT, bucket=CreditBucket.TOPUP, amount_mic=amount_mic, ref=ref))
        snap = _lock_snapshot(user_id)
        snap.topup_mic += amount_mic
        snap.version += 1
        snap.updated_at = datetime.now(timezone.utc)
    except IntegrityError:
        db.session.rollback()

def expire_all_monthly(user_id: int, ref: str) -> None:
    snap = _lock_snapshot(user_id)
    if snap.monthly_mic > 0:
        amt = snap.monthly_mic
        snap.monthly_mic = 0
        snap.version += 1
        snap.updated_at = datetime.now(timezone.utc)
        try:
            db.session.add(LedgerEntry(user_id=user_id, type=LedgerType.EXPIRE, bucket=CreditBucket.MONTHLY, amount_mic=amt, ref=ref))
        except IntegrityError:
            db.session.rollback()


def debit(user_id: int, cost_mic: int, ref: Optional[str] = None) -> Dict[str, int]:
    if ref:
        existing = db.session.query(LedgerEntry).filter_by(
            user_id=user_id, ref=ref, type=LedgerType.DEBIT
        ).first()
        if existing:
            m = existing.meta or {}
            return {
                "from_daily": int(m.get("from_daily", 0)),
                "from_monthly": int(m.get("from_monthly", 0)),
                "from_topup": int(m.get("from_topup", 0)),
            }
    ensure_daily_grant(user_id)
    snap = _lock_snapshot(user_id)

    remaining = cost_mic
    from_daily = min(snap.daily_mic, remaining)
    snap.daily_mic -= from_daily
    remaining -= from_daily

    from_monthly = 0
    if remaining > 0:
        from_monthly = min(snap.monthly_mic, remaining)
        snap.monthly_mic -= from_monthly
        remaining -= from_monthly

    from_topup = 0  # <-- initialize before next branch
    if remaining > 0:
        from_topup = min(snap.topup_mic, remaining)
        snap.topup_mic -= from_topup
        remaining -= from_topup

    if remaining > 0:
        raise InsufficientCredits("Not enough credits")

    snap.version += 1
    snap.updated_at = datetime.now(timezone.utc)
    meta = {"from_daily": from_daily, "from_monthly": from_monthly, "from_topup": from_topup}
    try:
        db.session.add(LedgerEntry(
            user_id=user_id, type=LedgerType.DEBIT, bucket=CreditBucket.NONE,
            amount_mic=cost_mic, ref=ref, meta=meta
        ))
    except IntegrityError:
        db.session.rollback()
    return meta

from sqlalchemy import func


def monthly_usage_mic(user_id: int, period_start, period_end) -> int:
    q = select(func.coalesce(func.sum(LedgerEntry.meta["from_monthly"].as_integer()), 0)).where(
        LedgerEntry.user_id == user_id,
        LedgerEntry.type == LedgerType.DEBIT,
        LedgerEntry.created_at >= period_start,
        LedgerEntry.created_at < period_end,
    )
    res = db.session.execute(q).scalar_one()
    return int(res or 0)










