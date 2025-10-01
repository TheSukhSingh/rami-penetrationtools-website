# tools/seed_config.py
from __future__ import annotations

from extensions import db
from tools.models import (
    Tool, ToolConfigField, ToolConfigFieldType,
    ToolCategory, ToolCategoryLink
)

# ---------------------------
# Canonical categories (single link per tool)
# ---------------------------
CATEGORIES = [
    # (slug, name, description, sort_order)
    ("recon",        "Recon Tools",            "Discovery, validation, and enrichment tools", 10),
    ("scanners",     "Vulnerability Scanners", "Web/app scanner tools",                       30),
    ("bruteforce",   "Brute Force",            "Fuzzing and credential attacks",              40),
    ("exploitation", "Exploitation Tools",     "Exploit and post-exploit utilities",          50),
    ("reporting",    "Reporting",              "Visualization and reporting helpers",         70),
]

# ---------------------------
# Full catalog (slug -> display name)
# ---------------------------
TOOLS = {
    # Recon / Validation / Enrichment
    "subfinder": "Subfinder",
    "crt_sh": "crt.sh",
    "github_subdomains": "GitHub Subdomains",
    "theharvester": "TheHarvester",
    "dnsx": "DNSx",
    "naabu": "Naabu",
    "httpx": "HTTPx",
    "katana": "Katana",
    "gau": "GAU",
    "arjun": "Arjun",
    "whatweb": "WhatWeb",
    "gowitness": "GoWitness",
    # Scanners
    "nikto": "Nikto",
    "nuclei": "Nuclei",
    "dalfox": "DalFox",
    "zap": "OWASP ZAP",
    "s3scanner": "S3Scanner",
    "wpscan": "WPScan",
    "wafw00f": "Wafw00f",
    "xsstrike": "XSStrike",
    "retire_js": "Retire.js",
    # Exploitation
    "sqlmap": "SQLMap",
    "commix": "Commix",
    "fuxploider": "FUXploider",
    "dotdotpwn": "DotDotPwn",
    "ssrfmap": "SSRFmap",
    # Brute force / fuzz
    "ffuf": "FFuF",
    "gobuster": "Gobuster",
    "hydra": "Hydra",
    # Remaining (place by use)
    "jwt_crack": "JWT-Crack",
    "paramspider": "ParamSpider",
    "john": "John the Ripper",
    "linkfinder": "LinkFinder",
    "qlgraph": "QLGraph",
}

# ---------------------------
# Category assignment (single category per tool)
# ---------------------------
TOOL_CATEGORY = {
    # Recon Tools
    "subfinder": "recon",
    "crt_sh": "recon",
    "github_subdomains": "recon",
    "theharvester": "recon",
    "dnsx": "recon",
    "naabu": "recon",
    "httpx": "recon",
    "katana": "recon",
    "gau": "recon",
    "arjun": "recon",
    "whatweb": "recon",
    "gowitness": "recon",
    # Vulnerability Scanners
    "nikto": "scanners",
    "nuclei": "scanners",
    "dalfox": "scanners",
    "zap": "scanners",
    "s3scanner": "scanners",
    "wpscan": "scanners",
    "wafw00f": "scanners",
    "xsstrike": "scanners",
    "retire_js": "scanners",
    # Exploitation
    "sqlmap": "exploitation",
    "commix": "exploitation",
    "fuxploider": "exploitation",
    "dotdotpwn": "exploitation",
    "ssrfmap": "exploitation",
    "jwt_crack": "exploitation",
    # Brute Force
    "ffuf": "bruteforce",
    "gobuster": "bruteforce",
    "hydra": "bruteforce",
    "john": "bruteforce",
    # Remaining (by use)
    "paramspider": "recon",
    "linkfinder": "recon",
    "qlgraph": "reporting",
}

# ---------------------------
# Shared config fields for all tools
# ---------------------------
COMMON_FIELDS = [
    {
        "name": "input_method", "label": "Input Source",
        "type": "select", "default": "manual", "order_index": 0,
        "choices": [
            {"value": "manual", "label": "Manual value"},
            {"value": "file",   "label": "Server file"},
        ],
    },
    {
        "name": "value", "label": "Value / Target",
        "type": "string", "placeholder": "example.com", "order_index": 1,
    },
    {
        "name": "file_path", "label": "Input File Path",
        "type": "path", "order_index": 2,
    },
]

# ---------------------------
# Extras per tool (only a few sensible knobs; expand as needed)
# ---------------------------
WORDLIST_TIER_FIELD = {
    "name": "wordlist_tier",
    "label": "Wordlist Tier",
    "type": "select",
    "default": "medium",
    "choices": [
        {"value": "small",  "label": "Small (1k–10k)"},
        {"value": "medium", "label": "Medium (10k–100k)"},
        {"value": "large",  "label": "Large (100k–1M)"},
        {"value": "ultra",  "label": "Ultra (1M+)"},
    ],
    "order_index": 50,
    "help_text": "Standard tiers; upload custom lists per-run if needed.",
}

EXTRAS = {
    # Recon
    "subfinder": [
        {"name": "threads", "label": "Threads", "type": "integer", "default": 10, "order_index": 10},
        {"name": "timeout_s", "label": "Timeout (s)", "type": "integer", "default": 60, "order_index": 11},
        {"name": "all_sources", "label": "Use all sources", "type": "boolean", "default": False, "order_index": 12},
    ],
    "crt_sh": [],
    "github_subdomains": [],
    "theharvester": [
        {"name": "sources", "label": "Sources", "type": "string", "default": "all", "order_index": 10},
    ],
    "dnsx": [
        {"name": "resolvers", "label": "Resolvers file", "type": "path", "order_index": 10},
    ],
    "naabu": [
        {"name": "top_ports", "label": "Top Ports", "type": "string", "default": "100", "order_index": 10},
        {"name": "timeout_s", "label": "Timeout (s)", "type": "integer", "default": 60, "order_index": 11},
    ],
    "httpx": [
        {"name": "threads", "label": "Threads", "type": "integer", "default": 50, "order_index": 10},
        {"name": "follow_redirects", "label": "Follow redirects", "type": "boolean", "default": True, "order_index": 11},
        {"name": "timeout_s", "label": "Timeout (s)", "type": "integer", "default": 20, "order_index": 12},
    ],
    "katana": [
        {"name": "depth", "label": "Crawl depth", "type": "integer", "default": 2, "order_index": 10},
    ],
    "gau": [
        {"name": "providers", "label": "Providers", "type": "string", "default": "wayback,otx,commoncrawl", "order_index": 10},
    ],
    "arjun": [
        WORDLIST_TIER_FIELD,
        {"name": "methods", "label": "HTTP Methods", "type": "string", "default": "GET,POST", "order_index": 10},
    ],
    "whatweb": [],
    "gowitness": [
        {"name": "chrome_path", "label": "Chrome path", "type": "path", "order_index": 10},
    ],
    "paramspider": [
        WORDLIST_TIER_FIELD,
        {"name": "depth", "label": "Depth", "type": "integer", "default": 2, "order_index": 10},
    ],
    "linkfinder": [],

    # Scanners
    "nikto": [],
    "nuclei": [
        {"name": "templates", "label": "Templates dir", "type": "path", "order_index": 10},
        {"name": "severity", "label": "Severity filter", "type": "string", "placeholder": "info,low,medium,high,critical", "order_index": 11},
    ],
    "dalfox": [
        WORDLIST_TIER_FIELD,
        {"name": "blind", "label": "Blind mode", "type": "boolean", "default": False, "order_index": 10},
    ],
    "zap": [
        {"name": "active_scan", "label": "Active scan", "type": "boolean", "default": True, "order_index": 10},
    ],
    "s3scanner": [],
    "wpscan": [
        {"name": "api_token", "label": "WPScan API token", "type": "string", "order_index": 10, "advanced": True, "visible": True},
    ],
    "wafw00f": [],
    "xsstrike": [
        WORDLIST_TIER_FIELD,
    ],
    "retire_js": [],

    # Exploitation
    "sqlmap": [
        {"name": "risk", "label": "Risk", "type": "integer", "default": 1, "order_index": 10},
        {"name": "level", "label": "Level", "type": "integer", "default": 1, "order_index": 11},
    ],
    "commix": [],
    "fuxploider": [],
    "dotdotpwn": [],
    "ssrfmap": [],

    # Brute force / fuzz
    "ffuf": [WORDLIST_TIER_FIELD, {"name": "threads", "label": "Threads", "type": "integer", "default": 40, "order_index": 10}],
    "gobuster": [WORDLIST_TIER_FIELD, {"name": "mode", "label": "Mode", "type": "select", "default": "dir",
                                       "choices": [{"value": "dir", "label": "Directories"}, {"value": "dns", "label": "DNS"}],
                                       "order_index": 10}],
    "hydra": [WORDLIST_TIER_FIELD],

    # Remaining
    "jwt_crack": [],
    "john": [WORDLIST_TIER_FIELD],
    "qlgraph": [],
}

# ---------------------------
# Helpers
# ---------------------------
def upsert_category(slug: str, name: str, desc: str, order: int) -> ToolCategory:
    cat = ToolCategory.query.filter_by(slug=slug).first()
    if not cat:
        cat = ToolCategory(slug=slug, name=name, description=desc, sort_order=order, enabled=True)
        db.session.add(cat)
    else:
        cat.name = name
        cat.description = desc
        cat.sort_order = order
        cat.enabled = True
    return cat

def upsert_tool(slug: str, name: str) -> Tool:
    tool = Tool.query.filter_by(slug=slug).first()
    if not tool:
        tool = Tool(slug=slug, name=name, enabled=True, meta_info={"desc": name})
        db.session.add(tool)
    else:
        tool.name = name
        tool.enabled = True
    return tool

def link_tool_to_category(tool: Tool, category: ToolCategory, order_index: int = 100) -> None:
    link = ToolCategoryLink.query.filter_by(category_id=category.id, tool_id=tool.id).first()
    if not link:
        link = ToolCategoryLink(category_id=category.id, tool_id=tool.id, sort_order=order_index)
        db.session.add(link)
    else:
        link.sort_order = order_index

def seed_fields_for_tool(tool: Tool, fields: list[dict]) -> None:
    # Clear existing fields to keep it deterministic
    ToolConfigField.query.filter_by(tool_id=tool.id).delete()
    # Insert in order
    for idx, f in enumerate(fields):
        db.session.add(ToolConfigField(
            tool_id=tool.id,
            name=f["name"],
            label=f.get("label", f["name"]),
            type=ToolConfigFieldType(f.get("type", "string")),
            required=bool(f.get("required", False)),
            help_text=f.get("help_text"),
            placeholder=f.get("placeholder"),
            default=f.get("default"),
            choices=f.get("choices"),
            group=f.get("group"),
            order_index=int(f.get("order_index", idx)),
            advanced=bool(f.get("advanced", False)),
            visible=bool(f.get("visible", True)),
        ))

# ---------------------------
# Entry points
# ---------------------------
def run():
    # 1) Categories
    slug_to_cat = {}
    for slug, name, desc, order in CATEGORIES:
        cat = upsert_category(slug, name, desc, order)
        slug_to_cat[slug] = cat
    db.session.flush()  # ensure IDs

    # 2) Tools
    slug_to_tool = {}
    for slug, name in TOOLS.items():
        t = upsert_tool(slug, name)
        slug_to_tool[slug] = t
    db.session.flush()

    # 3) Fields per tool (COMMON + EXTRAS)
    for slug, tool in slug_to_tool.items():
        fields = list(COMMON_FIELDS) + list(EXTRAS.get(slug, []))
        seed_fields_for_tool(tool, fields)
    db.session.flush()

    # 4) Single category link per tool
    for slug, tool in slug_to_tool.items():
        cat_slug = TOOL_CATEGORY.get(slug)
        if not cat_slug:
            # If missing mapping, put into Recon by default
            cat_slug = "recon"
        cat = slug_to_cat.get(cat_slug)
        if not cat:
            # Shouldn't happen; as a fallback, use recon
            cat = slug_to_cat["recon"]
        link_tool_to_category(tool, cat, order_index=100)
    db.session.commit()
    print("Seed complete: categories, tools, fields, links.")

def main():
    from app import create_app
    app = create_app()
    with app.app_context():
        run()

if __name__ == "__main__":
    main()
