def repo_get_overview(user_id: int, days: int = 30):
    # TODO: wire to ToolScanHistory + ScanDiagnostics
    return {
        "total_scans": 0,
        "last_scan_at": None,
        "success_count": 0,
        "failure_count": 0,
        "top_tools": [],
    }

def repo_list_scans(
    user_id: int,
    tool=None,
    status=None,
    q=None,
    page: int = 1,
    per_page: int = 20,
    date_from=None,
    date_to=None,
):
    # TODO: query ToolScanHistory joined with ScanDiagnostics + Tool
    return {"items": [], "page": page, "per_page": per_page, "total": 0}

def repo_get_scan_detail(user_id: int, scan_id: int):
    # TODO: fetch one scan + diagnostics + output preview
    return {
        "id": scan_id,
        "tool": {"slug": "", "name": ""},
        "scanned_at": None,
        "status": "UNKNOWN",
        "parameters": {},
        "command": "",
        "raw_output_preview": "",
        "diagnostics": {},
    }
