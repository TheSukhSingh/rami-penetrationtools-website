from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from sqlalchemy import func, select, exists, and_, or_, case

from extensions import db
from admin.repositories import BaseRepo
from admin.errors import NotFound, Forbidden

from auth.models import User, Role, LocalAuth, LoginEvent, UserIPLog, user_roles
from tools.models import ToolScanHistory



def utc_start_of_day(dt: Optional[datetime] = None) -> datetime:
    dt = dt or datetime.now(timezone.utc)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


class UsersRepo(BaseRepo):
    """Data access for users (excludes admins where needed)."""

    # ---------- Helpers ----------
    def _normal_user_query(self):
        return self.session.query(User).filter(
            ~User.is_admin_user,
            ~User.is_master_user,
        )
    
    def _non_admin_user_query(self):
        return self._normal_user_query()
    
    def _admin_user_query(self):
        return self.session.query(User).filter(User.is_admin_user)

    def _master_user_query(self):
        return self.session.query(User).filter(User.is_master_user)
    
    def _apply_search(self, query, q: Optional[str]):
        if not q:
            return query
        ql = q.strip().lower()
        return query.filter(
            or_(
                func.lower(User.email).like(f"%{ql}%"),
                func.lower(User.username).like(f"%{ql}%"),
                func.lower(User.name).like(f"%{ql}%"),
            )
        )

    # ---------- Metrics ----------

    def count_total_users(self) -> int:
        return self._non_admin_user_query().count()
    
    def count_total_admins(self) -> int:
        return self._admin_user_query().count()

    def count_total_masters(self) -> int:
        return self._master_user_query().count()

    def count_new_between(self, start: datetime, end: datetime) -> int:
        return (
            self._non_admin_user_query()
            .filter(User.created_at >= start, User.created_at < end)
            .count()
        )

    def count_active_between(self, start: datetime, end: datetime) -> int:
        # distinct users with a successful login event between start/end
        subq = (
            self.session.query(LoginEvent.user_id)
            .filter(
                LoginEvent.successful.is_(True),
                LoginEvent.occurred_at >= start,
                LoginEvent.occurred_at < end,
            )
            .distinct()
            .subquery()
        )
        return self._non_admin_user_query().filter(User.id.in_(select(subq.c.user_id))).count()

    # ---------- Listing / details ----------

    def list_users(
        self,
        page: int,
        per_page: int,
        q: Optional[str],
        sort_field: str,
        desc: bool,
    ) -> Tuple[List[User], int]:


        query = self._non_admin_user_query()

        # SA 2.x-friendly scalar subqueries for sorting/enrichment
        last_login_sub = (
            select(func.max(LoginEvent.occurred_at))
            .where(and_(LoginEvent.user_id == User.id, LoginEvent.successful.is_(True)))
            .correlate(User)
            .scalar_subquery()
        )

        scan_count_sub = (
            select(func.count(ToolScanHistory.id))
            .where(ToolScanHistory.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
        )

        if ToolScanHistory is not None:
            query = query.add_columns(scan_count_sub.label("scan_count"))

        query = self._apply_search(query, q)

        if sort_field == "last_login_at":
            nulls_rank = case((last_login_sub.is_(None), 1), else_=0)
            order_expr = last_login_sub.desc() if desc else last_login_sub.asc()
            query = query.order_by(nulls_rank.asc(), order_expr)
        elif sort_field == "scan_count":
            order_expr = scan_count_sub.desc() if desc else scan_count_sub.asc()
            query = query.order_by(order_expr)
        elif sort_field in {"created_at", "email", "username", "name"}:
            col = getattr(User, sort_field)
            query = query.order_by(col.desc() if desc else col.asc())
        else:
            # Safe fallback: prefer recent last_login_sub, then created_at
            nulls_rank = case((last_login_sub.is_(None), 1), else_=0)
            query = query.order_by(nulls_rank.asc(), last_login_sub.desc(), User.created_at.desc())


        items, total = self.paginate(query, page, per_page)

        if ToolScanHistory is not None:
            items = [row[0] for row in items] 
        return items, total

    def user_detail(self, user_id: int):
        user = self.session.get(User, user_id)
        return user

    def last_login_at(self, user_id: int) -> Optional[datetime]:
        # la = self.session.get(LocalAuth, user_id)
        # return la.last_login_at if la else None
        return (
            self.session.query(func.max(LoginEvent.occurred_at))
            .filter(LoginEvent.user_id == user_id, LoginEvent.successful.is_(True))
            .scalar()
        )

    def scan_count(self, user_id: int) -> int:
        if ToolScanHistory is None:
            return 0
        return (
            self.session.query(func.count(ToolScanHistory.id))
            .filter(ToolScanHistory.user_id == user_id)
            .scalar()
            or 0
        )

    def recent_ip_logs(self, user_id: int, limit: int = 10):
        return (
            self.session.query(UserIPLog)
            .filter(UserIPLog.user_id == user_id)
            .order_by(UserIPLog.created_at.desc())
            .limit(limit)
            .all()
        )

    # ---------- Mutations ----------

    def set_deactivated(self, user_id: int, value: bool) -> User:
        user = self.session.get(User, user_id)
        if not user:
            raise NotFound("User not found")
        if user.is_master_user:
            raise Forbidden("Cannot modify a master/owner account")
        user.is_deactivated = bool(value)
        return user  

    def get_role_by_name(self, name: str) -> Role:
        role = self.session.query(Role).filter(Role.name == name).first()
        if not role:
            raise NotFound("Role not found")
        return role

    def replace_tier_role(self, user_id: int, tier_role_name: str) -> User:
        user = self.session.get(User, user_id)
        if not user:
            raise NotFound("User not found")
        
        if user.is_master_user:
            raise Forbidden("Cannot change roles for a master/owner account")

        tier_roles = [r for r in user.roles if r.name.startswith("tier_")]
        for r in tier_roles:
            user.roles.remove(r)

        new_role = self.get_role_by_name(tier_role_name)
        user.roles.append(new_role)
        return user
