from flask import Blueprint

tools_bp = Blueprint(
    'tools',
    __name__,
    url_prefix="/tools",
    template_folder='templates',    
    static_folder='static',  
    cli_group="tools",      
)

import click

@tools_bp.cli.command("seed")
def seed_tools():
    """Seed the canonical 10 tools, two categories, and links + meta."""
    from extensions import db
    from tools.models import Tool, ToolCategory, ToolCategoryLink

    # --- Categories ---
    cats = [
        {"slug": "reconnaissance", "name": "Reconnaissance", "sort_order": 1, "enabled": True},
        {"slug": "vulnerability", "name": "Vulnerability Scanning", "sort_order": 2, "enabled": True},
    ]
    slug_to_cat = {}
    for c in cats:
        cat = ToolCategory.query.filter_by(slug=c["slug"]).first()
        if not cat:
            cat = ToolCategory(**c)
            db.session.add(cat)
        else:
            cat.name = c["name"]
            cat.sort_order = c["sort_order"]
            cat.enabled = c["enabled"]
        slug_to_cat[c["slug"]] = cat

    # --- Tools (10) ---
    tools = [
        # slug, name, type, time, description
        ("subfinder",        "Subfinder",         "SUBDOMAIN", "30s", "Subdomain discovery via passive sources."),
        ("dnsx",             "DNSx",              "IP",        "20s", "Fast DNS resolution & probing."),
        ("naabu",            "Naabu",             "PORTS",     "45s", "Fast port scanner (SYN/CONNECT)."),
        ("httpx",            "HTTPx",             "URL",       "1m",  "HTTP probing with status, title, TLS, etc."),
        ("gau",              "Gau",               "URL",       "1m",  "Fetch archived URLs from Wayback/OTX/etc."),
        ("katana",           "Katana",            "URL",       "3m",  "High-speed, headless optional web crawler."),
        ("hakrawler",        "Hakrawler",         "URL",       "2m",  "Link/endpoint crawler for reconnaissance."),
        ("gospider",         "GoSpider",          "URL",       "2m",  "Crawl websites & extract endpoints."),
        ("linkfinder",       "LinkFinder",        "PARAM",     "2m",  "Find endpoints/params in JS files."),
        ("github-subdomains","GitHub Subdomains", "SUBDOMAIN", "45s", "Discover subdomains from GitHub code."),
    ]

    slug_to_tool = {}
    for slug, name, ttype, time, desc in tools:
        t = Tool.query.filter_by(slug=slug).first()
        if not t:
            t = Tool(slug=slug, name=name, enabled=True, meta_info={})
            db.session.add(t)
        # keep name/enabled up to date
        t.name = name
        t.enabled = True
        # store display meta in meta_info
        meta = dict(t.meta_info or {})
        meta["type"] = ttype
        meta["estimated_time"] = time
        meta["description"] = desc
        t.meta_info = meta
        slug_to_tool[slug] = t

    db.session.flush()

    # --- Links: all 10 under Reconnaissance in this order ---
    recon = slug_to_cat["reconnaissance"]
    order = 1
    for slug, *_ in tools:
        tool = slug_to_tool[slug]
        link = ToolCategoryLink.query.filter_by(category_id=recon.id, tool_id=tool.id).first()
        if not link:
            link = ToolCategoryLink(category_id=recon.id, tool_id=tool.id, sort_order=order)
            db.session.add(link)
        else:
            link.sort_order = order
        order += 1

    db.session.commit()
    click.echo("Seed complete: categories, tools meta, and links updated.")

from . import routes 