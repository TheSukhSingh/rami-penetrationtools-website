from datetime import datetime
from typing import List, Dict
from sqlalchemy import func, select, and_
from admin.repositories import BaseRepo
from tools.models import ToolUsageDaily, Tool  


class ToolsRepo(BaseRepo):

    def usage_between(self, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
        """
        Top tools by total runs in [start,end) using the daily aggregate.
        ToolUsageDaily.day is a DATE; compare to start.date()/end.date().
        """
        day_start = start.date()
        day_end   = end.date()

        q = (
            select(Tool.name.label("tool"), func.sum(ToolUsageDaily.runs).label("count"))
            .select_from(ToolUsageDaily)
            .join(Tool, Tool.id == ToolUsageDaily.tool_id)
            .where(and_(ToolUsageDaily.day >= day_start, ToolUsageDaily.day < day_end))
            .group_by(Tool.name)
            .order_by(func.sum(ToolUsageDaily.runs).desc())
            .limit(limit)
        )
        return [{"tool": r.tool, "count": int(r.count)} for r in self.session.execute(q).all()]
