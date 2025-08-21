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



# from datetime import datetime, timedelta, timezone
# from typing import Optional, Dict, Any, Tuple, List

# from sqlalchemy import func
# from admin.services import BaseService
# from admin.repositories.users_repo import UsersRepo
# from admin.audit import record_admin_action, audit_context  # helpers you already have

# # If you keep AdminAuditLog model, only needed if you count deactivations from audit
# from admin.models import AdminAuditLog  # adjust import to where the model lives
# from extensions import db

# class UserService(BaseService):
#     def __init__(self):
#         super().__init__()
#         self.repo = UsersRepo(self.session)

#     # ---------- Summary (periodised, with deltas) ----------
#     def users_summary(self, period: str) -> Dict[str, Any]:
#         period = (period or "7d").lower()
#         start, end = self._window_for(period)
#         prev_start, prev_end = self._previous_window(start, end)

#         total_users_now = self.repo.count_total_users()  # snapshot

#         active_now  = self.repo.count_active_between(start, end)
#         active_prev = self.repo.count_active_between(prev_start, prev_end)

#         new_now  = self.repo.count_new_between(start, end)
#         new_prev = self.repo.count_new_between(prev_start, prev_end)

#         # If you prefer to count deactivations via audit log:
#         deact_now  = self._count_deactivations_between(start, end)
#         deact_prev = self._count_deactivations_between(prev_start, prev_end)

#         return {
#             "computed_at": datetime.now(timezone.utc).isoformat(),
#             "range": {"start": start.isoformat(), "end": end.isoformat()},
#             "cards": {
#                 "total_users":       {"value": int(total_users_now or 0), "delta_vs_prev": None},
#                 "active_users":      {"value": int(active_now or 0),      "delta_vs_prev": self._pct_delta(active_now,  active_prev)},
#                 "new_registrations": {"value": int(new_now or 0),         "delta_vs_prev": self._pct_delta(new_now,     new_prev)},
#                 "deactivated_users": {"value": int(deact_now or 0),       "delta_vs_prev": self._pct_delta(deact_now,   deact_prev)},
#             },
#         }

#     # ---------- List/Table ----------
#     def list_users(self, page: int, per_page: int, q: Optional[str], sort_field: str, desc: bool):
#         items, total = self.repo.list_users(page, per_page, q, sort_field, desc)

#         result = []
#         for u in items:
#             last_login = self.repo.last_login_at(u.id)
#             scan_cnt   = self.repo.scan_count(u.id)
#             tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
#             result.append({
#                 "id": u.id,
#                 "email": u.email,
#                 "username": u.username,
#                 "name": u.name,
#                 "created_at": u.created_at.isoformat() if u.created_at else None,
#                 "last_login_at": last_login.isoformat() if last_login else None,
#                 "is_deactivated": bool(u.is_deactivated),
#                 "scan_count": int(scan_cnt or 0),
#                 "tier": tier,
#             })
#         return result, int(total or 0)

#     # ---------- Detail ----------
#     def user_detail(self, user_id: int):
#         u = self.repo.user_detail(user_id)
#         self.ensure_found(u, "User not found")
#         last_login = self.repo.last_login_at(u.id)
#         scan_cnt   = self.repo.scan_count(u.id)
#         ip_logs    = self.repo.recent_ip_logs(u.id, limit=20)

#         tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
#         return {
#             "id": u.id,
#             "email": u.email,
#             "username": u.username,
#             "name": u.name,
#             "is_deactivated": bool(u.is_deactivated),
#             "tier": tier,
#             "scan_count": int(scan_cnt or 0),
#             "last_login_at": last_login.isoformat() if last_login else None,
#             "ip_logs": [
#                 {
#                     "ip": x.ip,
#                     "user_agent": x.user_agent,
#                     "device": x.device,
#                     "created_at": x.created_at.isoformat() if x.created_at else None,
#                 }
#                 for x in (ip_logs or [])
#             ],
#         }

#     # ---------- Mutations (audited) ----------
#     def deactivate(self, user_id: int):
#         with self.atomic():
#             before = self.user_detail(user_id)  # raises if not found
#             u = self.repo.set_deactivated(user_id, True)
#             after = {"is_deactivated": True}
#             record_admin_action(
#                 action="users.deactivate",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": after},
#             )
#             return {"id": u.id, "is_deactivated": True}

#     def reactivate(self, user_id: int):
#         with self.atomic():
#             before = self.user_detail(user_id)
#             u = self.repo.set_deactivated(user_id, False)
#             after = {"is_deactivated": False}
#             record_admin_action(
#                 action="users.reactivate",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": after},
#             )
#             return {"id": u.id, "is_deactivated": False}

#     def set_tier(self, user_id: int, tier_role_name: str):
#         with self.atomic():
#             u_before = self.repo.user_detail(user_id)
#             self.ensure_found(u_before, "User not found")
#             before_tier = next((r.name for r in (u_before.roles or []) if (r.name or "").startswith("tier_")), None)

#             u = self.repo.replace_tier_role(user_id, tier_role_name)

#             record_admin_action(
#                 action="users.set_tier",
#                 subject_type="user",
#                 subject_id=user_id,
#                 success=True,
#                 meta={"before": {"tier": before_tier}, "after": {"tier": tier_role_name}},
#             )
#             return {"id": u.id, "tier": tier_role_name}

#     # ---------- helpers ----------
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
#         elif period in ("all-time", "all", "at"):
#             start = datetime(1970, 1, 1, tzinfo=timezone.utc)
#         else:
#             start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
#         return start, now

#     def _previous_window(self, start, end):
#         delta = end - start
#         return start - delta, start

#     def _pct_delta(self, curr, prev):
#         curr = int(curr or 0); prev = int(prev or 0)
#         if prev <= 0:
#             return 100.0 if curr > 0 else 0.0
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





# admin/services/user_service.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

from sqlalchemy import func, desc, asc
from extensions import db

from . import BaseService                      # same base as overview service uses
from admin.repositories.users_repo import UsersRepo
from auth.models import User, LoginEvent
from tools.models import ToolScanHistory
from admin.models import AdminAuditLog
from admin.audit import record_admin_action, audit_context

UTC_NOW = lambda: datetime.now(timezone.utc)

class UserService(BaseService):
    def __init__(self):
        super().__init__()
        # Repo may require a session in your codebase, or not—support both:
        try:
            self.repo = UsersRepo(self.session)    # if ctor accepts session
        except TypeError:
            self.repo = UsersRepo()                # fallback to global db.session usage

    # ---------------- Summary (periodised + deltas) ----------------
    def users_summary(self, period: str) -> Dict[str, Any]:
        period = (period or "7d").lower()
        start, end = self._window_for(period)
        pstart, pend = self._previous_window(start, end)

        # use repo if available; otherwise safe fallbacks
        total_now = self._safe(lambda: self.repo.count_total_users(), 0)

        active_now  = self._safe(lambda: self.repo.count_active_between(start, end), 0)
        active_prev = self._safe(lambda: self.repo.count_active_between(pstart, pend), 0)

        new_now  = self._safe(lambda: self.repo.count_new_between(start, end), 0)
        new_prev = self._safe(lambda: self.repo.count_new_between(pstart, pend), 0)

        deact_now  = self._safe(lambda: self._count_deactivations_between(start, end), 0)
        deact_prev = self._safe(lambda: self._count_deactivations_between(pstart, pend), 0)
        return {
            "computed_at": UTC_NOW().isoformat(),
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "cards": {
                "total_users":       {"value": int(total_now or 0), "delta_vs_prev": None},
                "active_users":      {"value": int(active_now or 0), "delta_vs_prev": self._pct_delta(active_now, active_prev)},
                "new_registrations": {"value": int(new_now or 0),    "delta_vs_prev": self._pct_delta(new_now,    new_prev)},
                "deactivated_users": {"value": int(deact_now or 0),  "delta_vs_prev": self._pct_delta(deact_now,  deact_prev)},
            },
        }

    # ---------------- Listing / Table ----------------
    def list_users(self, page: int, per_page: int, q: Optional[str], sort_field: str, desc: bool):
        """
        Returns (items, total). Each item has the FE shape expected by users.js.
        Uses repo if present; otherwise runs a safe fallback query here.
        """
        # Prefer repo method if it exists
        if hasattr(self.repo, "list_users"):
            items, total = self.repo.list_users(page=page, per_page=per_page, q=q, sort_field=sort_field, desc=desc)
            # If your repo already returns serialised dicts + total, just return them
            if items and isinstance(items[0], dict):
                return items, total

            # Else items are model rows; enrich like below:
            users = items
        else:
            users, total = self._fallback_list(page, per_page, q, sort_field, desc)

        result = []
        for u in users:
            last_login_at = self._safe(lambda: self.repo.last_login_at(u.id), None) \
                             if hasattr(self.repo, "last_login_at") else self._fallback_last_login(u.id)
            scan_cnt = self._safe(lambda: self.repo.scan_count(u.id), 0) \
                        if hasattr(self.repo, "scan_count") else self._fallback_scan_count(u.id)
            tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
            result.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "name": u.name,
                "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
                "last_login_at": last_login_at.isoformat() if last_login_at else None,
                "is_deactivated": bool(u.is_deactivated),
                "scan_count": int(scan_cnt or 0),
                "tier": tier,
            })
        return result, int(total or 0)

    def _fallback_list(self, page: int, per_page: int, q: Optional[str], sort_field: str, is_desc: bool):
        U = User; LE = LoginEvent; SH = ToolScanHistory
        # subqueries for last_login and scan_count
        last_login_sub = (
            db.session.query(LE.user_id, func.max(LE.occurred_at).label("last_login_at"))
            .filter(LE.successful == True)
            .group_by(LE.user_id)
        ).subquery()

        scan_count_sub = (
            db.session.query(SH.user_id, func.count(SH.id).label("scan_count"))
            .group_by(SH.user_id)
        ).subquery()

        qset = db.session.query(U) \
            .outerjoin(last_login_sub, last_login_sub.c.user_id == U.id) \
            .outerjoin(scan_count_sub, scan_count_sub.c.user_id == U.id)

        if q:
            like = f"%{q.lower()}%"
            qset = qset.filter(
                func.lower(U.email).like(like) |
                func.lower(U.username).like(like) |
                func.lower(U.name).like(like)
            )

        # total count AFTER filters (distinct users)
        total = qset.with_entities(func.count(U.id)).scalar() or 0

        # sort
        colmap = {
            "email": U.email,
            "username": U.username,
            "name": U.name,
            "created_at": U.created_at,
            "last_login_at": last_login_sub.c.last_login_at,
            "scan_count": scan_count_sub.c.scan_count,
        }
        col = colmap.get(sort_field, last_login_sub.c.last_login_at)
        qset = qset.order_by(desc(col) if is_desc else asc(col))

        rows = qset.offset((page - 1) * per_page).limit(per_page).all()
        return rows, total

    def user_detail(self, user_id: int):
        u = self._safe(lambda: self.repo.user_detail(user_id), None) \
            if hasattr(self.repo, "user_detail") else User.query.get(user_id)
        self.ensure_found(u, "User not found")

        last_login = self._safe(lambda: self.repo.last_login_at(u.id), None) \
                     if hasattr(self.repo, "last_login_at") else self._fallback_last_login(u.id)
        scan_cnt   = self._safe(lambda: self.repo.scan_count(u.id), 0) \
                     if hasattr(self.repo, "scan_count") else self._fallback_scan_count(u.id)
        # if hasattr(self.repo, "recent_ip_logs"):
        #     ip_logs = self._safe(lambda: self.repo.recent_ip_logs(u.id, limit=20), []) or []
        # else:
        #     # optional: try to read logs directly if model exists
        #     ip_logs = []
        #     try:
        #         from admin.models import UserIPLog
        #         logs = (db.session.query(UserIPLog)
        #                 .filter(UserIPLog.user_id == u.id)
        #                 .order_by(UserIPLog.created_at.desc())
        #                 .limit(20).all())
        #         ip_logs = [{
        #             "ip": x.ip, "user_agent": x.user_agent, "device": x.device,
        #             "created_at": x.created_at.isoformat() if x.created_at else None
        #         } for x in logs]
        #     except Exception:
        #         pass
        if hasattr(self.repo, "recent_ip_logs"):
            logs = self._safe(lambda: self.repo.recent_ip_logs(u.id, limit=20), []) or []
            ip_logs = [{
                "ip": getattr(x, "ip", None),
                "user_agent": getattr(x, "user_agent", None),
                "device": getattr(x, "device", None),
                "created_at": (x.created_at.isoformat() if getattr(x, "created_at", None) else None),
            } for x in logs]
        else:
            ip_logs = []
            try:
                from admin.models import UserIPLog
                logs = (db.session.query(UserIPLog)
                        .filter(UserIPLog.user_id == u.id)
                        .order_by(UserIPLog.created_at.desc())
                        .limit(20).all())
                ip_logs = [{
                    "ip": x.ip, "user_agent": x.user_agent, "device": getattr(x, "device", None),
                    "created_at": x.created_at.isoformat() if x.created_at else None
                } for x in logs]
            except Exception:
                pass


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
            "ip_logs": ip_logs,
        }

    # ---------------- Mutations (audited) ----------------
    def deactivate(self, user_id: int):
        with self.atomic():
            before = self.user_detail(user_id)
            u = self.repo.set_deactivated(user_id, True)
            record_admin_action(
                action="users.deactivate",
                subject_type="user", subject_id=user_id, success=True,
                meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": {"is_deactivated": True}},
                **audit_context()
            )
            return {"id": u.id, "is_deactivated": True}

    def reactivate(self, user_id: int):
        with self.atomic():
            before = self.user_detail(user_id)
            u = self.repo.set_deactivated(user_id, False)
            record_admin_action(
                action="users.reactivate",
                subject_type="user", subject_id=user_id, success=True,
                meta={"before": {"is_deactivated": before["is_deactivated"]}, "after": {"is_deactivated": False}},
                **audit_context()
            )
            return {"id": u.id, "is_deactivated": False}

    def set_tier(self, user_id: int, tier_role_name: str):
        with self.atomic():
            u_before = self._safe(lambda: self.repo.user_detail(user_id), None) \
                       if hasattr(self.repo, "user_detail") else User.query.get(user_id)
            self.ensure_found(u_before, "User not found")
            before_tier = next((r.name for r in (u_before.roles or []) if (r.name or "").startswith("tier_")), None)

            # Your repo should implement this; if not, write it there.
            u = self.repo.replace_tier_role(user_id, tier_role_name)

            record_admin_action(
                action="users.set_tier",
                subject_type="user", subject_id=user_id, success=True,
                meta={"before": {"tier": before_tier}, "after": {"tier": tier_role_name}},
                **audit_context()
            )
            return {"id": u.id, "tier": tier_role_name}

    # ---------------- helpers ----------------
    def _window_for(self, period: str):
        now = UTC_NOW()
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
        q = (db.session.query(func.count(AdminAuditLog.id))
             .filter(AdminAuditLog.action == "users.deactivate",
                     AdminAuditLog.success.is_(True),
                     AdminAuditLog.created_at >= start,
                     AdminAuditLog.created_at < end))
        return int(q.scalar() or 0)

    def _fallback_last_login(self, user_id: int):
        return db.session.query(func.max(LoginEvent.occurred_at)).filter(
            LoginEvent.user_id == user_id, LoginEvent.successful == True
        ).scalar()

    def _fallback_scan_count(self, user_id: int):
        return db.session.query(func.count(ToolScanHistory.id)).filter(
            ToolScanHistory.user_id == user_id
        ).scalar()

    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default
