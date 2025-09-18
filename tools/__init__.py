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

@tools_bp.cli.command("wf-sample")
def wf_sample():
    """
    Create a sample workflow definition with 2 steps, and a stub run/steps.
    This is only for local sanity checks of the schema.
    """
    from .models import Tool, WorkflowDefinition, WorkflowRun, WorkflowRunStep, WorkflowRunStatus, WorkflowStepStatus, utcnow
    from extensions import db

    # pick two tools if present
    t1 = Tool.query.filter_by(slug="subfinder").first()
    t2 = Tool.query.filter_by(slug="httpx").first()
    if not t1 or not t2:
        click.echo("Seed tools first: flask tools seed")
        return

    graph = {
        "nodes": [
            {"id":"n1","tool_slug": t1.slug, "x": 200, "y": 150, "config": {}},
            {"id":"n2","tool_slug": t2.slug, "x": 520, "y": 150, "config": {}},
        ],
        "edges": [{"from":"n1","to":"n2"}],
    }

    wf = WorkflowDefinition(title="Sample Recon Chain", description="subfinder → httpx", graph_json=graph)
    db.session.add(wf); db.session.flush()

    run = WorkflowRun(workflow_id=wf.id, status=WorkflowRunStatus.QUEUED, total_steps=2, current_step_index=0)
    db.session.add(run); db.session.flush()

    s0 = WorkflowRunStep(run_id=run.id, step_index=0, tool_id=t1.id, status=WorkflowStepStatus.QUEUED)
    s1 = WorkflowRunStep(run_id=run.id, step_index=1, tool_id=t2.id, status=WorkflowStepStatus.QUEUED)
    db.session.add_all([s0, s1]); db.session.commit()

    click.echo(f"Created workflow #{wf.id} with run #{run.id} and 2 steps.")

@tools_bp.cli.command("celery-ping")
def celery_ping():
    """Queue a ping task to verify celery worker wiring."""
    from .tasks import ping
    r = ping.delay("hello-celery")
    click.echo(f"queued ping: {r.id}")

@tools_bp.cli.command("wf-run")
@click.argument("workflow_id", type=int)
@click.option("--user", "user_id", type=int, default=None, help="Run as user id")
def wf_run(workflow_id, user_id):
    """Create a run from a workflow and enqueue it."""
    from .runner import create_run_from_definition
    from .tasks import advance_run
    from extensions import db
    run = create_run_from_definition(workflow_id, user_id)
    advance_run.delay(run.id)
    click.echo(f"Enqueued run #{run.id} for workflow #{workflow_id}")

@tools_bp.cli.command("wf-advance")
@click.argument("run_id", type=int)
def wf_advance(run_id):
    """Manually enqueue the coordinator for a run id."""
    from .tasks import advance_run
    r = advance_run.delay(run_id)
    click.echo(f"advance_run queued: {r.id}")


from . import routes