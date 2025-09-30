from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, UniqueConstraint
from extensions import db


class BillingCustomer(db.Model):
    __tablename__ = "billing_customer"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

class SubscriptionSnapshot(db.Model):
    __tablename__ = "billing_subscription_snapshot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32)) # active, past_due, canceled, incomplete, etc.
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProcessedStripeEvent(db.Model):
    __tablename__ = "billing_processed_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
