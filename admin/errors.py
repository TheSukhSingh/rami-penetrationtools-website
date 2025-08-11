from typing import Any, Dict, Optional

class AdminError(Exception):
    status_code = 400
    code = "admin_error"

    def __init__(self, message: str = "", *, details: Optional[Dict[str, Any]] = None, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.message = message or self.code.replace("_", " ").title()
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload = {"ok": False, "error": {"code": self.code, "message": self.message}}
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class BadRequest(AdminError):       status_code = 400; code = "bad_request"
class Unauthorized(AdminError):     status_code = 401; code = "unauthorized"
class Forbidden(AdminError):        status_code = 403; code = "forbidden"
class NotFound(AdminError):         status_code = 404; code = "not_found"
class Conflict(AdminError):         status_code = 409; code = "conflict"
class Unprocessable(AdminError):    status_code = 422; code = "validation_error"
class RateLimited(AdminError):      status_code = 429; code = "rate_limited"
class ServerError(AdminError):      status_code = 500; code = "server_error"
