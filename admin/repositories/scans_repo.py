from datetime import datetime
from sqlalchemy import func, select, and_, case
from admin.repositories import BaseRepo
from tools.models import ToolScanHistory  # adjust if your model name differs
from typing import List, Dict

class ScansRepo(BaseRepo):

    def count_between(self, start: datetime, end: datetime) -> int:
        ts = ToolScanHistory
        q = (
            select(func.count())
            .select_from(ts)
            .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
        )
        return int(self.session.execute(q).scalar() or 0)

    def success_count_between(self, start: datetime, end: datetime) -> int:
        ts = ToolScanHistory
        q = (
            select(func.count())
            .select_from(ts)
            .where(
                and_(
                    ts.scanned_at >= start,
                    ts.scanned_at < end,
                    ts.scan_success_state.is_(True),
                )
            )
        )
        return int(self.session.execute(q).scalar() or 0)

    def daily_counts(self, start: datetime, end: datetime) -> List[Dict]:
        """
        Returns [{"day": "YYYY-MM-DD", "total": n, "success": m}, ...] within [start,end).
        Uses DATE(scanned_at) which works across Postgres/MySQL/SQLite.
        """
        ts = ToolScanHistory
        day_expr = func.date(ts.scanned_at)

        total_q = (
            select(day_expr.label("day"), func.count().label("total"))
            .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
            .group_by("day")
            .order_by("day")
        )
        totals = {str(r.day): int(r.total) for r in self.session.execute(total_q).all()}

        succ_q = (
            select(day_expr.label("day"), func.count().label("success"))
            .where(
                and_(
                    ts.scanned_at >= start,
                    ts.scanned_at < end,
                    ts.scan_success_state.is_(True),
                )
            )
            .group_by("day")
            .order_by("day")
        )
        succs = {str(r.day): int(r.success) for r in self.session.execute(succ_q).all()}

        days = sorted(set(totals) | set(succs))
        return [{"day": d, "total": totals.get(d, 0), "success": succs.get(d, 0)} for d in days]
