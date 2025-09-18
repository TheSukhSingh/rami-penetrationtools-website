# celery_app.py
from celery import Celery
import os

# Create a Celery app WITHOUT importing Flask app here
celery = Celery(
    __name__,
    include=[
        'tools.tasks',  # register tasks module
    ],
)

# Minimal config from environment so worker can boot without Flask import
celery.conf.update(
    broker=os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=os.getenv('CELERY_TIMEZONE', 'UTC'),
    enable_utc=True,
    task_ignore_result=False,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# Push a Flask app context lazily when a task actually runs
class AppContextTask(celery.Task):
    _flask_app = None

    def __call__(self, *args, **kwargs):
        if self._flask_app is None:
            # Import here to avoid circular import during Flask app startup / migrations
            from app import create_app
            self._flask_app = create_app()
        with self._flask_app.app_context():
            return self.run(*args, **kwargs)

celery.Task = AppContextTask
