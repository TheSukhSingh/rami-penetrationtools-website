# account/services/privacy.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable, List

from extensions import db
from auth.models import User, RefreshToken
from account.models import (
    AccountProfile,
    AccountNotificationPrefs,
    DataExportJob,
    AccountDeletionRequest,
    DeletionRequestStatus,
)

# If you have other per-user tables, add them here.
# Use lightweight bulk deletes; they’re safe with foreign keys that cascade further.
_DELETION_TABLES = [
    RefreshToken,
    AccountProfile,
    AccountNotificationPrefs,
    DataExportJob,
    # add more: SupportTicket, ToolScanHistory, etc.
]

def _utcnow():
    return datetime.now(timezone.utc)

def delete_user_hard(user_id: int) -> int:
    """
    Hard-delete a user's data. Returns number of rows directly touched here
    (excluding cascades fired by FK ondelete=CASCADE).
    """
    touched = 0
    for Model in _DELETION_TABLES:
        try:
            cnt = db.session.query(Model).filter_by(user_id=user_id).delete(synchronize_session=False)
            touched += int(cnt or 0)
        except Exception:
            # If a table doesn’t exist in this environment, skip silently.
            db.session.rollback()

    # Finally delete the user row (this may cascade further).
    u = db.session.query(User).get(user_id)
    if u:
        db.session.delete(u)
        touched += 1

    db.session.commit()
    return touched

def execute_due_deletions(limit: int = 100) -> int:
    """
    Execute all due (scheduled_delete_at <= now) deletion requests
    in PENDING or CONFIRMED state, up to `limit`.
    Returns number of users deleted.
    """
    now = _utcnow()

    # First mark the requests as EXECUTED (timestamped) so audit trails
    # are captured before the user row is deleted (which may cascade).
    q = (AccountDeletionRequest.query
         .filter(AccountDeletionRequest.status.in_([
             DeletionRequestStatus.PENDING.value,
             DeletionRequestStatus.CONFIRMED.value,
         ]),
                 AccountDeletionRequest.scheduled_delete_at <= now)
         .order_by(AccountDeletionRequest.scheduled_delete_at.asc())
         .limit(limit))

    due: List[AccountDeletionRequest] = q.all()
    if not due:
        return 0

    user_ids = []
    for dr in due:
        dr.status = DeletionRequestStatus.EXECUTED.value
        dr.executed_at = now
        db.session.add(dr)
        user_ids.append(dr.user_id)
    db.session.commit()

    # Now hard-delete each user and their data.
    deleted = 0
    for uid in user_ids:
        delete_user_hard(uid)
        deleted += 1

    return deleted
