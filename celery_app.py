from celery import Celery
import os, sys, pathlib, importlib, importlib.util
from celery.schedules import crontab

# ── Robust project root locator ───────────────────────────────────────────
def _find_project_root():
    anchors = []
    # 1) Env override if you want to hardcode it
    env_root = os.environ.get("PROJECT_ROOT") or os.environ.get("APP_ROOT")
    if env_root:
        anchors.append(pathlib.Path(env_root))

    # 2) Current working directory (where you launched celery)
    anchors.append(pathlib.Path.cwd())

    # 3) Directory of this file (where celery_app.py lives)
    here = pathlib.Path(__file__).resolve().parent
    anchors.append(here)

    # Add all parents too (walk upward)
    all_candidates = []
    for a in anchors:
        all_candidates.append(a)
        all_candidates.extend(a.parents)

    # Pick the first dir that contains app.py or wsgi.py
    for p in all_candidates:
        if (p / "app.py").exists() or (p / "wsgi.py").exists():
            return p

    # Fallback to the folder that has celery_app.py
    return here

PROJECT_ROOT = _find_project_root()

# Make sure the root is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Debug prints so we see exactly what Celery is using
try:
    print(">> PROJECT_ROOT =", PROJECT_ROOT)
    print(">> sys.path[0:3] =", sys.path[0:3])
    print(">> has app.py?", (PROJECT_ROOT / "app.py").exists())
    print(">> has auth folder?", (PROJECT_ROOT / "auth").exists())
    try:
        listing = [p.name for p in PROJECT_ROOT.iterdir()]
    except Exception:
        listing = []
    print(">> ls(PROJECT_ROOT) =", listing[:20])
except Exception:
    pass

# You can override where the factory lives if you ever move it (e.g., wsgi:create_app)
FLASK_FACTORY = os.getenv("FLASK_FACTORY", "app:create_app")

def _load_flask_app():
    module_name, _, factory_name = FLASK_FACTORY.partition(":")
    if not factory_name:
        factory_name = "create_app"

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        # Load from file if import by name fails
        candidate = (PROJECT_ROOT / f"{module_name}.py")
        if not candidate.exists():
            raise
        spec = importlib.util.spec_from_file_location(module_name, str(candidate))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    factory = getattr(module, factory_name, None)
    if factory is not None:
        return factory()
    if hasattr(module, "app"):
        return getattr(module, "app")

    raise RuntimeError(f"Could not find factory '{factory_name}' or 'app' in module '{module_name}'.")


celery = Celery(
    __name__,
    include=[
        "tools.tasks",
        "support.tasks",   # needed because you schedule support.* below
        "account.tasks",   # needed for the privacy task
    ],
)
celery_app = celery
# Celery config (unchanged)
from kombu import Queue
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=os.getenv('CELERY_TIMEZONE', 'UTC'),
    enable_utc=True,
    task_ignore_result=False,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)
celery.conf.beat_schedule = {
    "reconcile-zombies-every-10m": {
        "task": "tools.tasks.reconcile_zombies",
        "schedule": 600.0,  # every 10 minutes
    },
    "prune-history-nightly": {
        "task": "tools.tasks.prune_history",
        "schedule": crontab(hour=3, minute=0),
    },
    "support-pending-reminders": {
        "task": "support.tasks.pending_user_reminders",
        "schedule": crontab(minute=5, hour="*/2"),  # every 2 hours
    },
    "support-auto-close-and-remind": {
        "task": "support.tasks.auto_close_and_remind",
        "schedule": crontab(minute=35, hour="*/2"),  # every 2 hours (staggered)
    },
}

celery.conf.beat_schedule.update({
    "account-execute-due-deletions-every-hour": {
        "task": "account.execute_due_deletions",
        "schedule": crontab(minute=0),  # hourly on the hour
    },
})

celery.conf.task_default_queue = "tools_default"
celery.conf.task_queues = (Queue("tools_default", routing_key="tools_default"),)
celery.conf.task_default_exchange = "tools_default"
celery.conf.task_default_routing_key = "tools_default"
celery.conf.task_routes = {"tools.tasks.*": {"queue": "tools_default"}}

# Ensure every Celery task runs inside Flask app context
class AppContextTask(celery.Task):
    _flask_app = None

    def __call__(self, *args, **kwargs):
        # 🔧 FORCE the project root into sys.path at runtime (child process safe)
        try:
            before = sys.path[:3]
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            # (optional but helpful) also add parent in case you import siblings
            if str(PROJECT_ROOT.parent) not in sys.path:
                sys.path.insert(1, str(PROJECT_ROOT.parent))
            # keep env in sync for any sub-processes the task may spawn
            os.environ["PYTHONPATH"] = os.pathsep.join(
                [str(PROJECT_ROOT), str(PROJECT_ROOT.parent), os.environ.get("PYTHONPATH", "")]
            )
            importlib.invalidate_caches()
            after = sys.path[:3]
            print(">> sys.path before:", before)
            print(">> sys.path after:",  after)
        except Exception as e:
            print(">> sys.path inject error:", repr(e))

        if self._flask_app is None:
            # This now succeeds because 'app' and its imports ('auth', 'tools', …) are resolvable
            self._flask_app = _load_flask_app()

        with self._flask_app.app_context():
            return self.run(*args, **kwargs)


celery.Task = AppContextTask
