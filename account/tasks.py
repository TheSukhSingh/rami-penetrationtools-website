# account/tasks.py
from __future__ import annotations
from celery_app import celery as celery_app
from account.services.privacy import execute_due_deletions

@celery_app.task(name="account.execute_due_deletions")
def task_execute_due_deletions():
    return execute_due_deletions()
