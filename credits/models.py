from __future__ import annotations
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any
from sqlalchemy import Enum as SAEnum, Integer, String, Date, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from extensions import db


class LedgerType(str):
    GRANT = "grant"
    DEBIT = "debit"
    EXPIRE = "expire"
    REVERSAL = "reversal"


class CreditBucket(str):
    DAILY = "daily"
    MONTHLY = "monthly"
    TOPUP = "topup"
    NONE = "none" # e.g., reversal meta only


class LedgerEntry(db.Model):
    __tablename__ = "credit_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False) # LedgerType
    bucket: Mapped[str] = mapped_column(String(16), nullable=False) # CreditBucket
    amount_mic: Mapped[int] = mapped_column(Integer, nullable=False)
    ref: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


    __table_args__ = (
        db.UniqueConstraint('user_id', 'type', 'ref', name='uq_ledger_user_type_ref'),
        db.Index('ix_ledger_user_created', 'user_id', 'created_at'),
        db.Index('ix_ledger_type_created', 'type', 'created_at'),
    )



class BalanceSnapshot(db.Model):
    __tablename__ = "credit_balance_snapshot"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_mic: Mapped[int] = mapped_column(Integer, default=0)
    monthly_mic: Mapped[int] = mapped_column(Integer, default=0)
    topup_mic: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Entitlement(db.Model):
    __tablename__ = "credit_entitlements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CreditUserState(db.Model):
    __tablename__ = "credit_user_state"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_daily_grant_utc: Mapped[Optional[date]] = mapped_column(Date)
    pro_active: Mapped[int] = mapped_column(Integer, default=0)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(64))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(64))
    billing_status: Mapped[Optional[str]] = mapped_column(String(32)) # active, past_due, canceled
    past_due_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

