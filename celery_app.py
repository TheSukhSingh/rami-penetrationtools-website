from celery import Celery
from app import create_app  # your existing factory
from datetime import timedelta

def make_celery(flask_app=None):
    app = flask_app or create_app()
    celery = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND'],
        include=[
            'tools.tasks',  # register tasks module
        ],
    )
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
        enable_utc=True,
        task_ignore_result=False,
        worker_max_tasks_per_child=100,
        broker_connection_retry_on_startup=True,
        task_routes=app.config.get('CELERY_TASK_ROUTES', {}),
        beat_schedule={
            # example: heartbeat/log pruning later if you want
            # 'prune-old-results': {
            #     'task': 'tools.tasks.prune_results',
            #     'schedule': timedelta(hours=6),
            # },
        },
    )

    class AppContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            # Push Flask app context for DB/Config access inside tasks
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = AppContextTask
    return celery

celery = make_celery()
