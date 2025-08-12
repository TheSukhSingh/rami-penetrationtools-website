from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from admin.services import BaseService
from admin.repositories.users_repo import UsersRepo, utc_start_of_day, days_ago

class UserService(BaseService):
    def __init__(self):
        super().__init__()
        self.repo = UsersRepo(self.session)

    def users_summary(self) -> Dict[str, Any]:
        today_start = utc_start_of_day()
        month_start = today_start.replace(day=1)
        year_start  = today_start.replace(month=1, day=1)

        total        = self.repo.count_total_users()
        active_today = self.repo.count_active_between(today_start, today_start + timedelta(days=1))
        active_30d   = self.repo.count_active_between(days_ago(30), datetime.now(timezone.utc))
        new_today    = self.repo.count_new_between(today_start, today_start + timedelta(days=1))
        new_month    = self.repo.count_new_between(month_start, datetime.now(timezone.utc))
        new_year     = self.repo.count_new_between(year_start, datetime.now(timezone.utc))

        return {
            "total_users": total,
            "active_today": active_today,
            "active_30d": active_30d,
            "new_today": new_today,
            "new_month": new_month,
            "new_year": new_year,
        }

    def list_users(self, page: int, per_page: int, q: Optional[str], sort_field: str, desc: bool):
        items, total = self.repo.list_users(page, per_page, q, sort_field, desc)
        # Project to a lightweight shape for the table; fetch a few computed bits
        result = []
        for u in items:
            last_login = self.repo.last_login_at(u.id)
            scan_cnt   = self.repo.scan_count(u.id)
            # derive a simple tier from roles (role starting with 'tier_')
            tier = next((r.name for r in u.roles if r.name.startswith("tier_")), None)
            result.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "name": u.name,
                "created_at": u.created_at,
                "last_login_at": last_login,
                "is_deactivated": u.is_deactivated,
                "scan_count": scan_cnt,
                "tier": tier,
            })
        return result, total

    def user_detail(self, user_id: int):
        u = self.repo.user_detail(user_id)
        self.ensure_found(u, "User not found")
        last_login = self.repo.last_login_at(u.id)
        scan_cnt   = self.repo.scan_count(u.id)
        ip_logs    = self.repo.recent_ip_logs(u.id, limit=20)
        tier       = next((r.name for r in u.roles if r.name.startswith("tier_")), None)
        return {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "name": u.name,
            "created_at": u.created_at,
            "last_login_at": last_login,
            "is_deactivated": u.is_deactivated,
            "scan_count": scan_cnt,
            "tier": tier,
            "ip_logs": [
                {
                    "ip": log.ip,
                    "user_agent": log.user_agent,
                    "device": log.device,
                    "created_at": log.created_at,
                } for log in ip_logs
            ],
        }

    def deactivate(self, user_id: int):
        with self.atomic():
            u = self.repo.set_deactivated(user_id, True)
            return {"id": u.id, "is_deactivated": True}

    def reactivate(self, user_id: int):
        with self.atomic():
            u = self.repo.set_deactivated(user_id, False)
            return {"id": u.id, "is_deactivated": False}

    def set_tier(self, user_id: int, tier_role_name: str):
        with self.atomic():
            u = self.repo.replace_tier_role(user_id, tier_role_name)
            return {"id": u.id, "tier": tier_role_name}
