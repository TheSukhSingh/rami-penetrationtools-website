from typing import Any, Optional, Tuple
from extensions import db

class BaseRepo:
    def __init__(self, session=None):
        self.session = session or db.session

    def add(self, obj: Any):
        self.session.add(obj)
        return obj

    def delete(self, obj: Any):
        self.session.delete(obj)

    def commit_or_rollback(self):
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def paginate(self, query, page: int, per_page: int) -> Tuple[list, int]:
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        return items, total
