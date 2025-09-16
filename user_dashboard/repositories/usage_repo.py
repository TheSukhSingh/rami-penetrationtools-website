def repo_get_analytics(range="30d", tool=None):
    # TODO: read ToolUsageDaily or compute from history
    return {
        "series": [],
        "totals": {"runs": 0, "unique_users": 1},
    }
