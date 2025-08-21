# # admin/services/scan_service.py
# from __future__ import annotations
# from datetime import datetime, timedelta, timezone
# from typing import Dict, Any, Tuple, List, Optional

# from sqlalchemy import func, select
# from admin.services import BaseService
# from admin.repositories.scans_repo import ScansRepo

# UTC_NOW = lambda: datetime.now(timezone.utc)

# class ScanService(BaseService):
#     """
#     Computes scan metrics & provides list/detail for the admin Scans page.
#     """

#     def __init__(self):
#         super().__init__()
#         self.repo = ScansRepo(self.session)

#     # --------- ranges / helpers ----------
#     def _range_from_period(self, period: str) -> Tuple[datetime, datetime]:
#         p = (period or "7d").lower()
#         end = UTC_NOW()
#         if p == "1d":
#             start = end - timedelta(days=1)
#         elif p == "7d":
#             start = end - timedelta(days=7)
#         elif p == "30d":
#             start = end - timedelta(days=30)
#         elif p == "90d":
#             start = end - timedelta(days=90)
#         else:  # "all" -> last 12 months as overview does
#             start = end - timedelta(days=365)
#         return start, end

#     def _prev_range(self, start: datetime, end: datetime) -> Tuple[datetime, datetime]:
#         delta = end - start
#         return (start - delta, start)

#     def _pct_delta(self, curr: float, prev: float) -> float:
#         if prev <= 0:
#             return 100.0 if curr > 0 else 0.0
#         return ((curr - prev) / prev) * 100.0

#     # --------- public API ----------
#     def summary(self, period: str) -> Dict[str, Any]:
#         start, end = self._range_from_period(period)
#         pstart, pend = self._prev_range(start, end)

#         scans_now   = self.repo.count_between(start, end)
#         scans_prev  = self.repo.count_between(pstart, pend)

#         succ_now    = self.repo.success_count_between(start, end)
#         succ_prev   = self.repo.success_count_between(pstart, pend)

#         fail_now    = max(scans_now - succ_now, 0)
#         fail_prev   = max(scans_prev - succ_prev, 0)

#         avg_ms_now  = self.repo.avg_duration_between(start, end) or 0
#         avg_ms_prev = self.repo.avg_duration_between(pstart, pend) or 0

#         success_rate_now  = (succ_now / scans_now) if scans_now else 0.0
#         success_rate_prev = (succ_prev / scans_prev) if scans_prev else 0.0

#         daily_series = self.repo.daily_counts(start, end)
#         tools_usage  = self.repo.tools_usage_between(start, end, limit=10)

#         return {
#             "computed_at": UTC_NOW().isoformat(),
#             "range": {"start": start.isoformat(), "end": end.isoformat()},
#             "cards": {
#                 "scan_count": {
#                     "value": scans_now,
#                     "delta_vs_prev": self._pct_delta(scans_now, scans_prev),
#                 },
#                 "success_rate": {
#                     "value": success_rate_now,
#                     "delta_vs_prev": self._pct_delta(success_rate_now, success_rate_prev),
#                 },
#                 "failures": {
#                     "value": fail_now,
#                     "delta_vs_prev": self._pct_delta(fail_now, fail_prev),
#                 },
#                 "avg_duration_ms": {
#                     "value": int(avg_ms_now),
#                     "delta_vs_prev": self._pct_delta(avg_ms_now, avg_ms_prev),
#                 },
#             },
#             "charts": {
#                 # {day:"YYYY-MM-DD", total:int, success:int}
#                 "daily_scans": daily_series,
#                 # [{tool:"subfinder", count: 123}, ...]
#                 "tools_usage": tools_usage,
#             },
#         }

#     def list_scans(
#         self,
#         page: int,
#         per_page: int,
#         q: Optional[str],
#         tool: Optional[str],
#         status: Optional[str],
#         user: Optional[str],
#         start: Optional[datetime],
#         end: Optional[datetime],
#         sort_field: str,
#         is_desc: bool,
#     ) -> Tuple[List[Dict[str, Any]], int]:
#         return self.repo.list_scans(
#             page=page,
#             per_page=per_page,
#             q=q,
#             tool=tool,
#             status=status,
#             user=user,
#             start=start,
#             end=end,
#             sort_field=sort_field,
#             is_desc=is_desc,
#         )

#     def scan_detail(self, scan_id: int) -> Dict[str, Any]:
#         rec = self.repo.scan_detail(scan_id)
#         if not rec:
#             raise ValueError("Scan not found")
#         return rec



# admin/services/scan_service.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List, Optional

from admin.services import BaseService
from admin.repositories.scans_repo import ScansRepo

utcnow = lambda: datetime.now(timezone.utc)

class ScanService(BaseService):
    """Metrics + lists for the Scans page."""

    def __init__(self):
        super().__init__()
        self.repo = ScansRepo(self.session)

    # ---- ranges / helpers ----
    def _range_from_period(self, period: str) -> Tuple[datetime, datetime]:
        p = (period or "7d").lower()
        end = utcnow()
        if p == "1d":   start = end - timedelta(days=1)
        elif p == "7d": start = end - timedelta(days=7)
        elif p == "30d":start = end - timedelta(days=30)
        elif p == "90d":start = end - timedelta(days=90)
        else:           start = end - timedelta(days=365)  # "all" -> last 12 mo window
        return start, end

    def _prev_range(self, start: datetime, end: datetime) -> Tuple[datetime, datetime]:
        delta = end - start
        return (start - delta, start)

    def _pct_delta(self, curr: float, prev: float) -> float:
        if prev <= 0:
            return 100.0 if curr > 0 else 0.0
        return ((curr - prev) / prev) * 100.0

    # ---- public API ----
    def summary(self, period: str, active_window_minutes: int = 30) -> Dict[str, Any]:
        start, end = self._range_from_period(period)
        pstart, pend = self._prev_range(start, end)

        total_now  = self.repo.count_between(start, end)
        total_prev = self.repo.count_between(pstart, pend)

        succ_now   = self.repo.success_count_between(start, end)
        succ_prev  = self.repo.success_count_between(pstart, pend)

        fail_now   = max(total_now - succ_now, 0)
        fail_prev  = max(total_prev - succ_prev, 0)

        success_rate_now  = (succ_now / total_now) if total_now else 0.0
        success_rate_prev = (succ_prev / total_prev) if total_prev else 0.0

        avg_ms_now  = self.repo.avg_duration_between(start, end) or 0
        avg_ms_prev = self.repo.avg_duration_between(pstart, pend) or 0

        # "Active now": heuristic = scans without diagnostics (i.e., not finished) within window
        window_start = utcnow() - timedelta(minutes=active_window_minutes)
        active_now = self.repo.active_since(window_start)

        daily_series = self.repo.daily_counts(start, end)
        tools_usage  = self.repo.tools_usage_between(start, end, limit=10)

        return {
            "computed_at": utcnow().isoformat(),
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "cards": {
                "scan_count": {
                    "value": total_now,
                    "delta_vs_prev": self._pct_delta(total_now, total_prev),
                },
                "active_now": {
                    "value": active_now,
                    "delta_vs_prev": 0.0,  # point-in-time metric; no period delta
                },
                "failures": {
                    "value": fail_now,
                    "delta_vs_prev": self._pct_delta(fail_now, fail_prev),
                },
                "success_rate": {
                    "value": success_rate_now,
                    "delta_vs_prev": self._pct_delta(success_rate_now, success_rate_prev),
                },
                "avg_duration_ms": {
                    "value": int(avg_ms_now),
                    "delta_vs_prev": self._pct_delta(avg_ms_now, avg_ms_prev),
                },
            },
            "charts": {
                "daily_scans": daily_series,
                "tools_usage": tools_usage,
            },
        }

    def list_scans(
        self,
        page: int,
        per_page: int,
        q: Optional[str],
        tool: Optional[str],
        status: Optional[str],
        user: Optional[str],
        start: Optional[datetime],
        end: Optional[datetime],
        sort_field: str,
        is_desc: bool,
    ):
        return self.repo.list_scans(
            page=page, per_page=per_page,
            q=q, tool=tool, status=status, user=user,
            start=start, end=end,
            sort_field=sort_field, is_desc=is_desc,
        )

    def scan_detail(self, scan_id: int) -> Dict[str, Any]:
        data = self.repo.scan_detail(scan_id)
        if not data:
            raise ValueError("Scan not found")
        return data
