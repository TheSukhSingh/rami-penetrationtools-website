from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


MILLICREDITS = 1000 # 1.0 credit == 1000 millicredits


DAILY_FREE_CREDITS = 10 * MILLICREDITS
PRO_MONTHLY_CREDITS = 100 * MILLICREDITS


# Cost schedule
TOOL_RUN_COST = 1 * MILLICREDITS
CHAT_MESSAGE_COST = int(0.3 * MILLICREDITS) # 300 millicredits
WORKFLOW_DISCOUNT_FACTOR = 0.9 # e.g., 4 tools => 3.6 credits


# Entitlements
FREE_FEATURES = [
    "community_workflows",
    "basic_tool_configs",
    "branded_reports",
    "queue_priority:low",
    ]


PRO_FEATURES = [
    "presets",
    "custom_tool_configs",
    "multi_workspaces",
    "white_label_reports",
    "private_workflows",
    "queue_priority:high",
    ]


@dataclass(frozen=True)
class TopupPack:
    code: str
    credits_mic: int
    price_usd_cents: int


TOPUP_PACKS: Dict[str, TopupPack] = {
    "topup_100": TopupPack("topup_100", 100 * MILLICREDITS, 2500),
    "topup_200": TopupPack("topup_200", 200 * MILLICREDITS, 4000),
    "topup_500": TopupPack("topup_500", 500 * MILLICREDITS, 9000),
}


# Helper for workflow cost given N tools
def workflow_cost_mic(tool_count: int) -> int:
    raw = WORKFLOW_DISCOUNT_FACTOR * tool_count * MILLICREDITS
    return int(raw) # floor; we store exact millicredits