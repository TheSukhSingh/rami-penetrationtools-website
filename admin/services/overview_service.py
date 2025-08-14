from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from auth.models import User
from admin.services import BaseService
from admin.repositories.users_repo import UsersRepo
from admin.repositories.scans_repo import ScansRepo
from admin.repositories.tools_repo import ToolsRepo
                  

class OverviewService(BaseService):
    def __init__(self):
        super().__init__()
        self.users  = UsersRepo(self.session)
        self.scans  = ScansRepo(self.session)
        self.tools  = ToolsRepo(self.session)

    # ---------- public ----------
    def combined(self, period) :
        period = (period or "7d").lower()
        start, end = self._window_for(period)
        prev_start, prev_end = self._previous_window(start, end)

        # ---- users ----
        total_users_now  = self._total_users_before(end)
        total_users_prev = self._total_users_before(prev_end)

        new_regs_now  = self.users.count_new_between(start, end)
        new_regs_prev = self.users.count_new_between(prev_start, prev_end)

        # ---- scans ----
        scans_now        = self.scans.count_between(start, end)
        scans_prev       = self.scans.count_between(prev_start, prev_end)
        success_now      = self.scans.success_count_between(start, end)
        success_prev     = self.scans.success_count_between(prev_start, prev_end)
        success_rate_now  = (success_now / scans_now) if scans_now else 0.0
        success_rate_prev = (success_prev / scans_prev) if scans_prev else 0.0

        # ---- charts ----
        daily_series = self.scans.daily_counts(start, end)
        tools_usage  = self.tools.usage_between(start, end, limit=10)


        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "cards": {
                "total_users": {
                    "value": total_users_now,
                    "delta_vs_prev": self._pct_delta(total_users_now, total_users_prev),
                },
                "success_rate": {
                    "value": success_rate_now,
                    "delta_vs_prev": (success_rate_now - success_rate_prev) * 100.0,
                },
                "new_registrations": {
                    "value": new_regs_now,
                    "delta_vs_prev": self._pct_delta(new_regs_now, new_regs_prev),
                },
                "scan_count": {
                    "value": scans_now,
                    "delta_vs_prev": self._pct_delta(scans_now, scans_prev),
                },
            },
            "charts": {
                "daily_scans": daily_series,
                "tools_usage": tools_usage,
            },
        }

    # ---------- helpers ----------
    def _window_for(self, period):
        """Return (start, end) in UTC for the requested period."""
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
            # fallback to 7d
            start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    def _previous_window(self, start, end):
        delta = end - start
        prev_start = start - delta
        prev_end = start
        return prev_start, prev_end

    def _pct_delta(self, curr, prev) :
        if prev <= 0:
            return 100.0 if curr > 0 else 0.0
        return ( (curr - prev) / prev ) * 100.0
    
    def _total_users_before(self, end_dt) -> int:
        q = select(func.count()).select_from(User).where(User.created_at < end_dt)
        return int(self.session.execute(q).scalar() or 0)

