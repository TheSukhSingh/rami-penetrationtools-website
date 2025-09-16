from flask import Blueprint
from extensions import db
tools_bp = Blueprint(
    'tools',
    __name__,
    url_prefix="/tools",
    template_folder='templates',    
    static_folder='static',  
    cli_group="tools",      
)
from .models import Tool, ToolCategory, ToolCategoryLink
import click

@tools_bp.cli.command("seed")
def seed_tools():
    """Seed default tool categories and tools (aligned to models: sort_order, slug, meta_info)."""
    # Categories in display order
    cats = [
        {"name": "Reconnaissance", "slug": "recon",     "order": 1},
        {"name": "Discovery",      "slug": "discovery", "order": 2},
        {"name": "Vulnerability",  "slug": "vuln",      "order": 3},
    ]

    cat_by_slug = {}
    for c in cats:
        cat = ToolCategory.query.filter_by(slug=c["slug"]).first()
        if not cat:
            cat = ToolCategory(slug=c["slug"])
            db.session.add(cat)
        cat.name = c["name"]
        # Your model uses sort_order + enabled
        setattr(cat, "sort_order", c["order"])
        setattr(cat, "enabled", True)
        cat_by_slug[c["slug"]] = cat

    # Canonical tools (map our desired metadata into Tool.meta_info)
    tools = [
        # Recon
        {"slug":"subfinder",         "name":"subfinder",         "type":"recon",     "time":"~30s", "desc":"Passive subdomain discovery",        "cat":"recon"},
        {"slug":"dnsx",              "name":"dnsx",              "type":"recon",     "time":"~10s", "desc":"DNS probe & resolve",                 "cat":"recon"},
        {"slug":"httpx",             "name":"httpx",             "type":"recon",     "time":"~15s", "desc":"Probe web services",                  "cat":"recon"},
        {"slug":"gau",               "name":"gau",               "type":"recon",     "time":"~20s", "desc":"Fetch archived URLs",                  "cat":"recon"},
        {"slug":"gospider",          "name":"gospider",          "type":"recon",     "time":"~40s", "desc":"Fast web spidering",                   "cat":"recon"},
        # Discovery
        {"slug":"hakrawler",         "name":"hakrawler",         "type":"discovery", "time":"~25s", "desc":"Crawl endpoints quickly",              "cat":"discovery"},
        {"slug":"katana",            "name":"katana",            "type":"discovery", "time":"~35s", "desc":"Modern web crawler",                   "cat":"discovery"},
        {"slug":"linkfinder",        "name":"linkfinder",        "type":"discovery", "time":"~20s", "desc":"Find JS endpoints",                    "cat":"discovery"},
        # Vuln
        {"slug":"naabu",             "name":"naabu",             "type":"vuln",      "time":"~30s", "desc":"Fast port scanner",                   "cat":"vuln"},
        {"slug":"github-subdomains", "name":"github-subdomains", "type":"vuln",      "time":"~15s", "desc":"Find subdomains via code search",     "cat":"vuln"},
    ]

    tool_by_slug = {}
    for i, t in enumerate(tools, start=1):
        tool = Tool.query.filter_by(slug=t["slug"]).first()
        if not tool:
            tool = Tool(slug=t["slug"])
            db.session.add(tool)
        tool.name = t["name"]
        setattr(tool, "enabled", True)
        # Your routes expect meta_info: desc/type/time
        tool.meta_info = {"desc": t["desc"], "type": t["type"], "time": t["time"]}
        tool_by_slug[t["slug"]] = tool

    db.session.flush()  # ensure IDs exist for link rows

    # Link tools to categories (use sort_order on link)
    for i, t in enumerate(tools, start=1):
        cat = cat_by_slug[t["cat"]]
        tool = tool_by_slug[t["slug"]]
        link = ToolCategoryLink.query.filter_by(category_id=cat.id, tool_id=tool.id).first()
        if not link:
            link = ToolCategoryLink(category_id=cat.id, tool_id=tool.id)
            db.session.add(link)
        setattr(link, "sort_order", i)

    db.session.commit()
    click.echo("Seeded tool categories and tools (models: sort_order/enabled + Tool.meta_info).")

from . import routes