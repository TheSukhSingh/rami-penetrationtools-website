from ..repositories.scans_repo import (
    repo_get_overview,
    repo_list_scans,
    repo_get_scan_detail,

)
from ..repositories.usage_repo import repo_get_analytics
from ..repositories.account_repo import repo_resolve_download_path

def get_overview(user_id: int, days: int = 30):
    return repo_get_overview(user_id=user_id, days=days)

def list_scans(
    user_id: int,
    tool=None,
    status=None,
    q=None,
    page: int = 1,
    per_page: int = 20,
    date_from=None,
    date_to=None,
):
    return repo_list_scans(
        user_id=user_id,
        tool=tool,
        status=status,
        q=q,
        page=page,
        per_page=per_page,
        date_from=date_from,
        date_to=date_to,
    )


def get_scan_detail(user_id: int, scan_id: int):
    return repo_get_scan_detail(user_id=user_id, scan_id=scan_id)


def get_analytics(user_id: int, days: int = 30, tool=None):
    return repo_get_analytics(user_id=user_id, days=days, tool=tool)

def get_download_path(user_id: int, scan_id: int):
    return repo_resolve_download_path(user_id=user_id, scan_id=scan_id)
