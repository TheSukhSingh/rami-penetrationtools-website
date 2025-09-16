def repo_get_analytics(user_id: int, days: int = 30, tool=None):
    # TODO: read ToolUsageDaily or compute from history
    return {
        "series": [],
        "totals": {"runs": 0, "unique_users": 1},
    }
