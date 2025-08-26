# from datetime import datetime
# from sqlalchemy import func, select, and_, case
# from admin.repositories import BaseRepo
# from tools.models import ToolScanHistory  # adjust if your model name differs
# from typing import List, Dict

# class ScansRepo(BaseRepo):

#     def count_between(self, start: datetime, end: datetime) -> int:
#         ts = ToolScanHistory
#         q = (
#             select(func.count())
#             .select_from(ts)
#             .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
#         )
#         return int(self.session.execute(q).scalar() or 0)

#     def success_count_between(self, start: datetime, end: datetime) -> int:
#         ts = ToolScanHistory
#         q = (
#             select(func.count())
#             .select_from(ts)
#             .where(
#                 and_(
#                     ts.scanned_at >= start,
#                     ts.scanned_at < end,
#                     ts.scan_success_state.is_(True),
#                 )
#             )
#         )
#         return int(self.session.execute(q).scalar() or 0)

#     def daily_counts(self, start: datetime, end: datetime) -> List[Dict]:
#         """
#         Returns [{"day": "YYYY-MM-DD", "total": n, "success": m}, ...] within [start,end).
#         Uses DATE(scanned_at) which works across Postgres/MySQL/SQLite.
#         """
#         ts = ToolScanHistory
#         day_expr = func.date(ts.scanned_at)

#         total_q = (
#             select(day_expr.label("day"), func.count().label("total"))
#             .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
#             .group_by("day")
#             .order_by("day")
#         )
#         totals = {str(r.day): int(r.total) for r in self.session.execute(total_q).all()}

#         succ_q = (
#             select(day_expr.label("day"), func.count().label("success"))
#             .where(
#                 and_(
#                     ts.scanned_at >= start,
#                     ts.scanned_at < end,
#                     ts.scan_success_state.is_(True),
#                 )
#             )
#             .group_by("day")
#             .order_by("day")
#         )
#         succs = {str(r.day): int(r.success) for r in self.session.execute(succ_q).all()}

#         days = sorted(set(totals) | set(succs))
#         return [{"day": d, "total": totals.get(d, 0), "success": succs.get(d, 0)} for d in days]


# admin/repositories/scans_repo.py
# from __future__ import annotations
# from datetime import datetime
# from typing import List, Dict, Optional, Tuple

# from sqlalchemy import func, select, and_, or_, desc, asc, literal
# from sqlalchemy.orm import aliased, joinedload

# from admin.repositories import BaseRepo
# from tools.models import ToolScanHistory, ScanDiagnostics
# from auth.models import User

# class ScansRepo(BaseRepo):
#     # ----- counts / series -----
#     def count_between(self, start: datetime, end: datetime) -> int:
#         ts = ToolScanHistory
#         q = (
#             select(func.count())
#             .select_from(ts)
#             .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
#         )
#         return int(self.session.execute(q).scalar() or 0)

#     def success_count_between(self, start: datetime, end: datetime) -> int:
#         ts = ToolScanHistory
#         q = (
#             select(func.count())
#             .select_from(ts)
#             .where(
#                 and_(
#                     ts.scanned_at >= start,
#                     ts.scanned_at < end,
#                     ts.scan_success_state.is_(True),
#                 )
#             )
#         )
#         return int(self.session.execute(q).scalar() or 0)

#     def avg_duration_between(self, start: datetime, end: datetime) -> Optional[float]:
#         d = ScanDiagnostics
#         ts = ToolScanHistory
#         q = (
#             select(func.avg(d.execution_ms))
#             .select_from(d)
#             .join(ts, ts.id == d.scan_id)
#             .where(and_(ts.scanned_at >= start, ts.scanned_at < end, d.execution_ms.isnot(None)))
#         )
#         v = self.session.execute(q).scalar()
#         return float(v) if v is not None else None

#     def daily_counts(self, start: datetime, end: datetime) -> List[Dict]:
#         ts = ToolScanHistory
#         d = ScanDiagnostics
#         day_expr = func.date(ts.scanned_at)

#         totals = dict(
#             (str(r.day), int(r.total))
#             for r in self.session.execute(
#                 select(day_expr.label("day"), func.count().label("total"))
#                 .select_from(ts)
#                 .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
#                 .group_by("day")
#                 .order_by("day")
#             ).all()
#         )
#         succs = dict(
#             (str(r.day), int(r.success))
#             for r in self.session.execute(
#                 select(day_expr.label("day"), func.count().label("success"))
#                 .select_from(ts)
#                 .where(and_(ts.scanned_at >= start, ts.scanned_at < end, ts.scan_success_state.is_(True)))
#                 .group_by("day")
#                 .order_by("day")
#             ).all()
#         )
#         days = sorted(set(totals) | set(succs))
#         return [{"day": d, "total": totals.get(d, 0), "success": succs.get(d, 0)} for d in days]

#     def tools_usage_between(self, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
#         ts = ToolScanHistory
#         rows = self.session.execute(
#             select(ts.tool, func.count().label("count"))
#             .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
#             .group_by(ts.tool)
#             .order_by(desc("count"))
#             .limit(limit)
#         ).all()
#         return [{"tool": r.tool, "count": int(r.count)} for r in rows]

#     # ----- list / detail -----
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
#     ) -> Tuple[List[Dict], int]:

#         ts = ToolScanHistory
#         d  = ScanDiagnostics
#         u  = aliased(User)

#         filters = []
#         if start and end:
#             filters.append(and_(ts.scanned_at >= start, ts.scanned_at < end))
#         if tool:
#             filters.append(ts.tool == tool)
#         if status:
#             # allow "success"/"failure"/"queued"/etc; with our schema we have success/failure via boolean + diag enum
#             s = status.strip().lower()
#             if s in ("success", "ok", "passed"):
#                 filters.append(ts.scan_success_state.is_(True))
#             elif s in ("failure", "fail", "error", "crash"):
#                 filters.append(ts.scan_success_state.is_(False))
#         if user:
#             # user can be id or email/username
#             if user.isdigit():
#                 filters.append(ts.user_id == int(user))
#             else:
#                 filters.append(
#                     or_(
#                         u.email.ilike(f"%{user}%"),
#                         u.username.ilike(f"%{user}%"),
#                         u.name.ilike(f"%{user}%"),
#                     )
#                 )
#         if q:
#             filters.append(
#                 or_(
#                     ts.command.ilike(f"%{q}%"),
#                     ts.parameters.cast(str).ilike(f"%{q}%"),
#                     ts.filename_by_user.ilike(f"%{q}%"),
#                     ts.tool.ilike(f"%{q}%"),
#                 )
#             )

#         # base selectable
#         base = (
#             select(
#                 ts.id.label("id"),
#                 ts.scanned_at.label("scanned_at"),
#                 ts.tool.label("tool"),
#                 ts.parameters.label("parameters"),
#                 ts.command.label("command"),
#                 ts.scan_success_state.label("success"),
#                 ts.filename_by_user.label("filename"),
#                 u.id.label("user_id"),
#                 u.email.label("user_email"),
#                 u.username.label("user_username"),
#                 d.execution_ms.label("execution_ms"),
#                 d.status.label("diag_status"),
#                 d.error_reason.label("error_reason"),
#             )
#             .select_from(ts)
#             .join(u, u.id == ts.user_id, isouter=True)
#             .join(d, d.scan_id == ts.id, isouter=True)
#             .where(and_(*filters) if filters else literal(True))
#         )

#         # sorting
#         sort_map = {
#             "created_at": ts.scanned_at,  # alias
#             "scanned_at": ts.scanned_at,
#             "tool": ts.tool,
#             "status": ts.scan_success_state,
#             "duration": d.execution_ms,
#             "user": u.username,
#         }
#         col = sort_map.get(sort_field or "scanned_at", ts.scanned_at)
#         order_by = desc(col) if is_desc else asc(col)

#         # total
#         total = int(self.session.execute(select(func.count()).select_from(base.subquery())).scalar() or 0)

#         # page
#         rows = self.session.execute(base.order_by(order_by).limit(per_page).offset((page - 1) * per_page)).all()

#         items: List[Dict] = []
#         for r in rows:
#             items.append({
#                 "id": r.id,
#                 "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
#                 "tool": r.tool,
#                 "command": r.command,
#                 "parameters": r.parameters or {},
#                 "success": bool(r.success),
#                 "filename": r.filename,
#                 "user": {
#                     "id": r.user_id,
#                     "email": r.user_email,
#                     "username": r.user_username,
#                 },
#                 "duration_ms": int(r.execution_ms) if r.execution_ms is not None else None,
#                 "status": (r.diag_status.value if r.diag_status is not None else ("SUCCESS" if r.success else "FAILURE")),
#                 "error_reason": (r.error_reason.value if r.error_reason is not None else None),
#             })

#         return items, total

#     def scan_detail(self, scan_id: int) -> Optional[Dict[str, any]]:
#         ts = ToolScanHistory
#         d  = ScanDiagnostics
#         u  = User

#         row = (
#             self.session.query(ts, d, u)
#             .outerjoin(d, d.scan_id == ts.id)
#             .outerjoin(u, u.id == ts.user_id)
#             .filter(ts.id == scan_id)
#             .first()
#         )
#         if not row:
#             return None

#         ts_rec, d_rec, u_rec = row
#         return {
#             "id": ts_rec.id,
#             "scanned_at": ts_rec.scanned_at.isoformat() if ts_rec.scanned_at else None,
#             "tool": ts_rec.tool,
#             "command": ts_rec.command,
#             "parameters": ts_rec.parameters or {},
#             "success": bool(ts_rec.scan_success_state),
#             "filename_by_user": ts_rec.filename_by_user,
#             "filename_by_be": ts_rec.filename_by_be,
#             "user": {
#                 "id": getattr(u_rec, "id", None),
#                 "email": getattr(u_rec, "email", None),
#                 "username": getattr(u_rec, "username", None),
#                 "name": getattr(u_rec, "name", None),
#             },
#             "diagnostics": None if not d_rec else {
#                 "status": d_rec.status.value if d_rec.status else None,
#                 "execution_ms": d_rec.execution_ms,
#                 "file_size_b": d_rec.file_size_b,
#                 "total_domain_count": d_rec.total_domain_count,
#                 "valid_domain_count": d_rec.valid_domain_count,
#                 "invalid_domain_count": d_rec.invalid_domain_count,
#                 "duplicate_domain_count": d_rec.duplicate_domain_count,
#                 "error_reason": d_rec.error_reason.value if d_rec.error_reason else None,
#                 "error_detail": d_rec.error_detail,
#                 "value_entered": d_rec.value_entered,
#                 "created_at": d_rec.created_at.isoformat() if d_rec.created_at else None,
#             },
#         }





# admin/repositories/scans_repo.py
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from sqlalchemy import func, select, and_, or_, desc, asc, literal
from sqlalchemy.orm import aliased

from admin.repositories import BaseRepo
from tools.models import ToolScanHistory, ScanDiagnostics
from auth.models import User, UserIPLog  # adjust if your module name differs

class ScansRepo(BaseRepo):
    # ---- counts / series ----
    def count_between(self, start: datetime, end: datetime) -> int:
        ts = ToolScanHistory
        q = select(func.count()).select_from(ts).where(and_(ts.scanned_at >= start, ts.scanned_at < end))
        return int(self.session.execute(q).scalar() or 0)

    def success_count_between(self, start: datetime, end: datetime) -> int:
        ts = ToolScanHistory
        q = (
            select(func.count())
            .select_from(ts)
            .where(and_(ts.scanned_at >= start, ts.scanned_at < end, ts.scan_success_state.is_(True)))
        )
        return int(self.session.execute(q).scalar() or 0)

    def avg_duration_between(self, start: datetime, end: datetime) -> Optional[float]:
        ts, d = ToolScanHistory, ScanDiagnostics
        q = (
            select(func.avg(d.execution_ms))
            .select_from(d).join(ts, ts.id == d.scan_id)
            .where(and_(ts.scanned_at >= start, ts.scanned_at < end, d.execution_ms.isnot(None)))
        )
        v = self.session.execute(q).scalar()
        return float(v) if v is not None else None

    def daily_counts(self, start: datetime, end: datetime) -> List[Dict]:
        ts = ToolScanHistory
        day = func.date(ts.scanned_at)

        total = {
            str(r.day): int(r.total)
            for r in self.session.execute(
                select(day.label("day"), func.count().label("total"))
                .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
                .group_by("day").order_by("day")
            ).all()
        }
        succ = {
            str(r.day): int(r.success)
            for r in self.session.execute(
                select(day.label("day"), func.count().label("success"))
                .where(and_(ts.scanned_at >= start, ts.scanned_at < end, ts.scan_success_state.is_(True)))
                .group_by("day").order_by("day")
            ).all()
        }
        days = sorted(set(total) | set(succ))
        return [{"day": d, "total": total.get(d, 0), "success": succ.get(d, 0)} for d in days]

    def tools_usage_between(self, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
        ts = ToolScanHistory
        rows = self.session.execute(
            select(ts.tool, func.count().label("count"))
            .where(and_(ts.scanned_at >= start, ts.scanned_at < end))
            .group_by(ts.tool).order_by(desc("count")).limit(limit)
        ).all()
        return [{"tool": r.tool, "count": int(r.count)} for r in rows]

    def active_since(self, since: datetime) -> int:
        """Heuristic: scans with no diagnostics and not marked success, started since `since`."""
        ts, d = ToolScanHistory, ScanDiagnostics
        q = (
            select(func.count())
            .select_from(ts)
            .join(d, d.scan_id == ts.id, isouter=True)
            .where(and_(ts.scanned_at >= since, d.id.is_(None), ts.scan_success_state.is_(False)))
        )
        return int(self.session.execute(q).scalar() or 0)

    # ---- list / detail ----
    def _extract_target_sql(self, ts: ToolScanHistory):
        """Try to pull a reasonable 'target' string from parameters JSON."""
        # SQL-agnostic approach: we’ll return full parameters here; FE will derive final display.
        return ts.parameters

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
    ) -> Tuple[List[Dict], int]:

        ts, d = ToolScanHistory, ScanDiagnostics
        u = aliased(User)
        ul = aliased(UserIPLog)

        filters = []
        if start and end:
            filters.append(and_(ts.scanned_at >= start, ts.scanned_at < end))
        if tool:
            filters.append(ts.tool == tool)
        if status:
            s = status.strip().lower()
            if s in ("success", "ok", "passed"):
                filters.append(ts.scan_success_state.is_(True))
            elif s in ("failure", "fail", "error", "crash"):
                filters.append(ts.scan_success_state.is_(False))
        if user:
            if user.isdigit():
                filters.append(ts.user_id == int(user))
            else:
                filters.append(or_(u.email.ilike(f"%{user}%"), u.username.ilike(f"%{user}%"), u.name.ilike(f"%{user}%")))
        if q:
            filters.append(
                or_(
                    ts.tool.ilike(f"%{q}%"),
                    ts.command.ilike(f"%{q}%"),
                    ts.parameters.cast(str).ilike(f"%{q}%"),
                    ts.filename_by_user.ilike(f"%{q}%"),
                )
            )

        # "Last known location": join to the most recent UserIPLog for that user.
        sub_last_ip = (
            select(ul.user_id, func.max(ul.created_at).label("mx"))
            .group_by(ul.user_id)
        ).subquery()
        ul2 = aliased(UserIPLog)

        base = (
            select(
                ts.id.label("id"),
                ts.scanned_at.label("scanned_at"),
                ts.tool.label("tool"),
                ts.parameters.label("parameters"),
                ts.command.label("command"),
                ts.scan_success_state.label("success"),
                u.id.label("user_id"),
                u.email.label("user_email"),
                u.username.label("user_username"),
                d.execution_ms.label("execution_ms"),
                d.status.label("diag_status"),
                d.error_reason.label("error_reason"),
                ul2.ip.label("ip"),
                ul2.geo_city.label("geo_city"),
                ul2.geo_country.label("geo_country"),
            )
            .select_from(ts)
            .join(u, u.id == ts.user_id, isouter=True)
            .join(d, d.scan_id == ts.id, isouter=True)
            .join(sub_last_ip, sub_last_ip.c.user_id == ts.user_id, isouter=True)
            .join(
                ul2,
                and_(ul2.user_id == ts.user_id, ul2.created_at == sub_last_ip.c.mx),
                isouter=True,
            )
            .where(and_(*filters) if filters else literal(True))
        )

        sort_map = {
            "created_at": ts.scanned_at,
            "scanned_at": ts.scanned_at,
            "tool": ts.tool,
            "status": ts.scan_success_state,
            "duration": d.execution_ms,
            "user": u.username,
        }
        col = sort_map.get(sort_field or "scanned_at", ts.scanned_at)
        order_by = desc(col) if is_desc else asc(col)

        total = int(self.session.execute(select(func.count()).select_from(base.subquery())).scalar() or 0)
        rows = self.session.execute(base.order_by(order_by).limit(per_page).offset((page - 1) * per_page)).all()

        items: List[Dict] = []
        for r in rows:
            # derive display target from parameters
            params = r.parameters or {}
            target = None
            for key in ("target","domain","url","host","ip","file","query"):
                if key in params and params[key]:
                    target = str(params[key]); break

            status_str = (
                (r.diag_status.value if r.diag_status is not None else None)
                or ("SUCCESS" if r.success else "FAILURE")
            )

            items.append({
                "id": r.id,
                "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                "tool": r.tool,
                "target": target,
                "user": {"id": r.user_id, "email": r.user_email, "username": r.user_username},
                "status": status_str,
                "success": bool(r.success),
                "duration_ms": int(r.execution_ms) if r.execution_ms is not None else None,
                "location": {
                    "ip": r.ip,
                    "city": r.geo_city,
                    "country": r.geo_country,
                },
            })

        return items, total

    def scan_detail(self, scan_id: int) -> Optional[Dict]:
        ts, d, u = ToolScanHistory, ScanDiagnostics, User
        row = (
            self.session.query(ts, d, u)
            .outerjoin(d, d.scan_id == ts.id)
            .outerjoin(u, u.id == ts.user_id)
            .filter(ts.id == scan_id)
            .first()
        )
        if not row:
            return None
        ts_rec, d_rec, u_rec = row
        return {
            "id": ts_rec.id,
            "scanned_at": ts_rec.scanned_at.isoformat() if ts_rec.scanned_at else None,
            "tool": ts_rec.tool,
            "command": ts_rec.command,
            "parameters": ts_rec.parameters or {},
            "success": bool(ts_rec.scan_success_state),
            "filename_by_user": ts_rec.filename_by_user,
            "filename_by_be": ts_rec.filename_by_be,
            "user": {
                "id": getattr(u_rec, "id", None),
                "email": getattr(u_rec, "email", None),
                "username": getattr(u_rec, "username", None),
                "name": getattr(u_rec, "name", None),
            },
            "diagnostics": None if not d_rec else {
                "status": d_rec.status.value if d_rec.status else None,
                "execution_ms": d_rec.execution_ms,
                "file_size_b": d_rec.file_size_b,
                "total_domain_count": d_rec.total_domain_count,
                "valid_domain_count": d_rec.valid_domain_count,
                "invalid_domain_count": d_rec.invalid_domain_count,
                "duplicate_domain_count": d_rec.duplicate_domain_count,
                "error_reason": d_rec.error_reason.value if d_rec.error_reason else None,
                "error_detail": d_rec.error_detail,
                "value_entered": d_rec.value_entered,
                "created_at": d_rec.created_at.isoformat() if d_rec.created_at else None,
            },
        }
