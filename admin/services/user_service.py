# from datetime import datetime, timedelta, timezone
# from typing import Optional, Dict, Any

# from sqlalchemy import func
# from admin.audit import record_admin_action, audit_context
# from admin.services import BaseService
# from admin.repositories.users_repo import UsersRepo
# from admin.models import AdminAuditLog

# class UserService(BaseService):
#     def __init__(self):
#         super().__init__()
#         self.repo = UsersRepo(self.session)

#     def users_summary(self, period: str):
#         period = (period or "7d").lower()
#         start, end = self._window_for(period)
#         prev_start, prev_end = self._previous_window(start, end)

#         # snapshots / counts
#         total_users_now = self.repo.count_total_users()  # snapshot (no delta on this card)

#         active_now  = self.repo.count_active_between(start, end)
#         active_prev = self.repo.count_active_between(prev_start, prev_end)

#         new_now  = self.repo.count_new_between(start, end)
#         new_prev = self.repo.count_new_between(prev_start, prev_end)

#         # deactivations = new deactivation events in window (from admin audit log)
#         deact_now  = self._count_deactivations_between(start, end)
#         deact_prev = self._count_deactivations_between(prev_start, prev_end)

#         return {
#             "computed_at": datetime.now(timezone.utc).isoformat(),
#             "range": {"start": start.isoformat(), "end": end.isoformat()},
#             "cards": {
#                 "total_users": {
#                     "value": total_users_now,
#                     "delta_vs_prev": None,  # no delta for total snapshot
#                 },
#                 "active_users": {
#                     "value": active_now,
#                     "delta_vs_prev": self._pct_delta(active_now, active_prev),
#                 },
#                 "new_registrations": {
#                     "value": new_now,
#                     "delta_vs_prev": self._pct_delta(new_now, new_prev),
#                 },
#                 "deactivated_users": {
#                     "value": deact_now,
#                     "delta_vs_prev": self._pct_delta(deact_now, deact_prev),
#                 },
#             },
#         }
    
#     def _window_for(self, period: str):
#         now = datetime.now(timezone.utc)
#         if period in ("1d", "1day", "today"): start = now.replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "7d":  start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "30d": start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "90d": start = (now - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period in ("all-time","all","at"): start = datetime(1970,1,1,tzinfo=timezone.utc)
#         else: start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
#         return start, now

#     def _previous_window(self, start, end):
#         delta = end - start
#         return start - delta, start

#     def _pct_delta(self, curr, prev):
#         if prev <= 0: return 100.0 if curr > 0 else 0.0
#         return ((curr - prev) / prev) * 100.0

#     def _count_deactivations_between(self, start, end) -> int:
#         q = (
#             self.session.query(func.count(AdminAuditLog.id))
#             .filter(
#                 AdminAuditLog.action == "users.deactivate",
#                 AdminAuditLog.success.is_(True),
#                 AdminAuditLog.created_at >= start,
#                 AdminAuditLog.created_at < end,
#             )
#         )
#         return int(q.scalar() or 0)

#     def list_users(self, page: int, per_page: int, q: Optional[str], sort_field: str, desc: bool):
#         items, total = self.repo.list_users(page, per_page, q, sort_field, desc)
#         # Project to a lightweight shape for the table; fetch a few computed bits
#         result = []
#         for u in items:
#             last_login = self.repo.last_login_at(u.id)
#             scan_cnt   = self.repo.scan_count(u.id)
#             # derive a simple tier from roles (role starting with 'tier_')
#             tier = next((r.name for r in u.roles if r.name.startswith("tier_")), None)
#             result.append({
#                 "id": u.id,
#                 "email": u.email,
#                 "username": u.username,
#                 "name": u.name,
#                 "created_at": u.created_at,
#                 "last_login_at": last_login,
#                 "is_deactivated": u.is_deactivated,
#                 "scan_count": scan_cnt,
#                 "tier": tier,
#             })
#         return result, total

#     def user_detail(self, user_id: int):
#         u = self.repo.user_detail(user_id)
#         self.ensure_found(u, "User not found")
#         last_login = self.repo.last_login_at(u.id)
#         scan_cnt   = self.repo.scan_count(u.id)
#         ip_logs    = self.repo.recent_ip_logs(u.id, limit=20)
#         tier       = next((r.name for r in u.roles if r.name.startswith("tier_")), None)
#         return {
#             "id": u.id,
#             "email": u.email,
#             "username": u.username,
#             "name": u.name,
#             "created_at": u.created_at,
#             "last_login_at": last_login,
#             "is_deactivated": u.is_deactivated,
#             "scan_count": scan_cnt,
#             "tier": tier,
#             "ip_logs": [
#                 {
#                     "ip": log.ip,
#                     "user_agent": log.user_agent,
#                     "device": log.device,
#                     "created_at": log.created_at,
#                 } for log in ip_logs
#             ],
#         }

#     def deactivate(self, user_id: int):
#         with self.atomic():
#             u_before = self.repo.user_detail(user_id)
#             self.ensure_found(u_before, message="User not found")
#             res = self.repo.set_deactivated(user_id, True)
#             u_after = self.repo.user_detail(user_id)
#             record_admin_action(
#                 action="users.deactivate",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"is_deactivated": u_before.is_deactivated}, "after": {"is_deactivated": u_after.is_deactivated}},
#                 **audit_context()
#             )
#             return {"id": res.id, "is_deactivated": True}

#     def reactivate(self, user_id: int):
#         with self.atomic():
#             u_before = self.repo.user_detail(user_id)
#             self.ensure_found(u_before, message="User not found")
#             res = self.repo.set_deactivated(user_id, False)
#             u_after = self.repo.user_detail(user_id)
#             record_admin_action(
#                 action="users.reactivate",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"is_deactivated": u_before.is_deactivated}, "after": {"is_deactivated": u_after.is_deactivated}},
#                 **audit_context()
#             )
#             return {"id": res.id, "is_deactivated": False}

#     def set_tier(self, user_id: int, tier_role_name: str):
#         with self.atomic():
#             u_before = self.repo.user_detail(user_id)
#             self.ensure_found(u_before, message="User not found")
#             before_tier = next((r.name for r in u_before.roles if r.name.startswith("tier_")), None)
#             u = self.repo.replace_tier_role(user_id, tier_role_name)
#             after_tier = tier_role_name
#             record_admin_action(
#                 action="users.set_tier",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"tier": before_tier}, "after": {"tier": after_tier}},
#                 **audit_context()
#             )
#             return {"id": u.id, "tier": tier_role_name}



# from datetime import datetime, timedelta, timezone
# from sqlalchemy import func
# from extensions import db
# from admin.models import AdminAuditLog
# from .base import BaseService  # if you have a BaseService that provides .atomic(), else remove inheritance

# class UserService(BaseService):
#     # assume you set self.repo = UsersRepo() in __init__

#     def users_summary(self, period: str):
#         period = (period or "7d").lower()
#         start, end = self._window_for(period)
#         prev_start, prev_end = self._previous_window(start, end)

#         total_users_now = self.repo.count_total_users()

#         active_now  = self.repo.count_active_between(start, end)
#         active_prev = self.repo.count_active_between(prev_start, prev_end)

#         new_now  = self.repo.count_new_between(start, end)
#         new_prev = self.repo.count_new_between(prev_start, prev_end)

#         deact_now  = self._count_deactivations_between(start, end)
#         deact_prev = self._count_deactivations_between(prev_start, prev_end)

#         return {
#             "computed_at": datetime.now(timezone.utc).isoformat(),
#             "range": {"start": start.isoformat(), "end": end.isoformat()},
#             "cards": {
#                 "total_users": { "value": int(total_users_now or 0), "delta_vs_prev": None },
#                 "active_users": { "value": int(active_now or 0), "delta_vs_prev": self._pct_delta(active_now, active_prev) },
#                 "new_registrations": { "value": int(new_now or 0), "delta_vs_prev": self._pct_delta(new_now, new_prev) },
#                 "deactivated_users": { "value": int(deact_now or 0), "delta_vs_prev": self._pct_delta(deact_now, deact_prev) },
#             },
#         }

#     def _window_for(self, period: str):
#         now = datetime.now(timezone.utc)
#         if period in ("1d", "1day", "today"):
#             start = now.replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "7d":
#             start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "30d":
#             start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period == "90d":
#             start = (now - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
#         elif period in ("all-time","all","at"):
#             start = datetime(1970,1,1,tzinfo=timezone.utc)
#         else:
#             start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
#         return start, now

#     def _previous_window(self, start, end):
#         delta = end - start
#         return start - delta, start

#     def _pct_delta(self, curr, prev):
#         curr = int(curr or 0); prev = int(prev or 0)
#         if prev <= 0: return 100.0 if curr > 0 else 0.0
#         return ((curr - prev) / prev) * 100.0

#     def _count_deactivations_between(self, start, end) -> int:
#         q = (
#             db.session.query(func.count(AdminAuditLog.id))
#             .filter(
#                 AdminAuditLog.action == "users.deactivate",
#                 AdminAuditLog.success.is_(True),
#                 AdminAuditLog.created_at >= start,
#                 AdminAuditLog.created_at < end,
#             )
#         )
#         return int(q.scalar() or 0)



from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, List

from sqlalchemy import func
from admin.services import BaseService
from admin.repositories.users_repo import UsersRepo
from admin.audit import record_admin_action, audit_context  # helpers you already have

# If you keep AdminAuditLog model, only needed if you count deactivations from audit
from admin.models import AdminAuditLog  # adjust import to where the model lives
from extensions import db

class UserService(BaseService):
    def __init__(self):
        super().__init__()
        self.repo = UsersRepo(self.session)

    # ---------- Summary (periodised, with deltas) ----------
    def users_summary(self, period: str) -> Dict[str, Any]:
        period = (period or "7d").lower()
        start, end = self._window_for(period)
        prev_start, prev_end = self._previous_window(start, end)

        total_users_now = self.repo.count_total_users()  # snapshot

        active_now  = self.repo.count_active_between(start, end)
        active_prev = self.repo.count_active_between(prev_start, prev_end)

        new_now  = self.repo.count_new_between(start, end)
        new_prev = self.repo.count_new_between(prev_start, prev_end)

        # If you prefer to count deactivations via audit log:
        deact_now  = self._count_deactivations_between(start, end)
        deact_prev = self._count_deactivations_between(prev_start, prev_end)

        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "cards": {
                "total_users":       {"value": int(total_users_now or 0), "delta_vs_prev": None},
                "active_users":      {"value": int(active_now or 0),      "delta_vs_prev": self._pct_delta(active_now,  active_prev)},
                "new_registrations": {"value": int(new_now or 0),         "delta_vs_prev": self._pct_delta(new_now,     new_prev)},
                "deactivated_users": {"value": int(deact_now or 0),       "delta_vs_prev": self._pct_delta(deact_now,   deact_prev)},
            },
        }

    # ---------- List/Table ----------
    def list_users(self, page: int, per_page: int, q: Optional[str], sort_field: str, desc: bool):
        items, total = self.repo.list_users(page, per_page, q, sort_field, desc)

        result = []
        for u in items:
            last_login = self.repo.last_login_at(u.id)
            scan_cnt   = self.repo.scan_count(u.id)
            tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
            result.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "name": u.name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": last_login.isoformat() if last_login else None,
                "is_deactivated": bool(u.is_deactivated),
                "scan_count": int(scan_cnt or 0),
                "tier": tier,
            })
        return result, int(total or 0)

    # ---------- Detail ----------
    def user_detail(self, user_id: int):
        u = self.repo.user_detail(user_id)
        self.ensure_found(u, "User not found")
        last_login = self.repo.last_login_at(u.id)
        scan_cnt   = self.repo.scan_count(u.id)
        ip_logs    = self.repo.recent_ip_logs(u.id, limit=20)

        tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
        return {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "name": u.name,
            "is_deactivated": bool(u.is_deactivated),
            "tier": tier,
            "scan_count": int(scan_cnt or 0),
            "last_login_at": last_login.isoformat() if last_login else None,
            "ip_logs": [
                {
                    "ip": x.ip,
                    "user_agent": x.user_agent,
                    "device": x.device,
                    "created_at": x.created_at.isoformat() if x.created_at else None,
                }
                for x in (ip_logs or [])
            ],
        }

    # ---------- Mutations (audited) ----------
    def deactivate(self, user_id: int):
        with self.atomic():
            before = self.user_detail(user_id)  # raises if not found
            u = self.repo.set_deactivated(user_id, True)
            after = {"is_deactivated": True}
            record_admin_action(
                action="users.deactivate",
                subject_type="user",
                subject_id=user_id,
                success=True,
                meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": after},
            )
            return {"id": u.id, "is_deactivated": True}

    def reactivate(self, user_id: int):
        with self.atomic():
            before = self.user_detail(user_id)
            u = self.repo.set_deactivated(user_id, False)
            after = {"is_deactivated": False}
            record_admin_action(
                action="users.reactivate",
                subject_type="user",
                subject_id=user_id,
                success=True,
                meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": after},
            )
            return {"id": u.id, "is_deactivated": False}

    def set_tier(self, user_id: int, tier_role_name: str):
        with self.atomic():
            u_before = self.repo.user_detail(user_id)
            self.ensure_found(u_before, "User not found")
            before_tier = next((r.name for r in (u_before.roles or []) if (r.name or "").startswith("tier_")), None)

            u = self.repo.replace_tier_role(user_id, tier_role_name)

            record_admin_action(
                action="users.set_tier",
                subject_type="user",
                subject_id=user_id,
                success=True,
                meta={"before": {"tier": before_tier}, "after": {"tier": tier_role_name}},
            )
            return {"id": u.id, "tier": tier_role_name}

    # ---------- helpers ----------
    def _window_for(self, period: str):
        now = datetime.now(timezone.utc)
        if period in ("1d", "1day", "today"):
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "7d":
            start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "30d":
            start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "90d":
            start = (now - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period in ("all-time", "all", "at"):
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        else:
            start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    def _previous_window(self, start, end):
        delta = end - start
        return start - delta, start

    def _pct_delta(self, curr, prev):
        curr = int(curr or 0); prev = int(prev or 0)
        if prev <= 0:
            return 100.0 if curr > 0 else 0.0
        return ((curr - prev) / prev) * 100.0

    def _count_deactivations_between(self, start, end) -> int:
        q = (
            db.session.query(func.count(AdminAuditLog.id))
            .filter(
                AdminAuditLog.action == "users.deactivate",
                AdminAuditLog.success.is_(True),
                AdminAuditLog.created_at >= start,
                AdminAuditLog.created_at < end,
            )
        )
        return int(q.scalar() or 0)
