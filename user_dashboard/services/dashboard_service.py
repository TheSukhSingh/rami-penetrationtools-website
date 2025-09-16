from ..repositories.scans_repo import repo_list_scans, repo_get_scan_detail, repo_get_overview
from ..repositories.usage_repo import repo_get_analytics
from ..repositories.account_repo import repo_resolve_download_path

def get_overview():
    return repo_get_overview()

def list_scans(tool=None, status=None, q=None, page=1, per_page=20, date_from=None, date_to=None):
    return repo_list_scans(tool, status, q, page, per_page, date_from, date_to)

def get_scan_detail(scan_id: int):
    return repo_get_scan_detail(scan_id)

def get_analytics(range="30d", tool=None):
    return repo_get_analytics(range, tool)

def get_download_path(scan_id: int):
    return repo_resolve_download_path(scan_id)
