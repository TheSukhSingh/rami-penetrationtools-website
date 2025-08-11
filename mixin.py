from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property

class PrettyIdMixin:
    _pretty_prefix = "XX"
    _pretty_date_attr = "created_at"

    @hybrid_property
    def pretty_id(self):
        if not getattr(self, "id", None):
            return None
        dt = getattr(self, self._pretty_date_attr, None) or datetime.utcnow()
        return f"{self._pretty_prefix}-{dt.year}-{self.id:06d}"

    @classmethod
    def parse_pretty_id(cls, code: str):
        if not code or "-" not in code:
            return None
        try:
            return int(code.rsplit("-", 1)[-1])
        except ValueError:
            return None
