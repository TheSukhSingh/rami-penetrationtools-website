
from contextlib import contextmanager
from typing import Any, Dict
from extensions import db
from admin.errors import AdminError, NotFound

class BaseService:
    def __init__(self):
        self.session = db.session

    @contextmanager
    def atomic(self):
        try:
            yield
            self.session.commit()
        except AdminError:
            self.session.rollback()
            raise
        except Exception:
            self.session.rollback()
            raise

    def ensure_found(self, obj: Any, *, message: str = "Object not found"):
        if obj is None:
            raise NotFound(message)
        return obj
