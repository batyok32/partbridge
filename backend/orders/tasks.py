from __future__ import annotations

from celery import shared_task


@shared_task
def placeholder_task() -> dict:
    """Placeholder — old tasks removed with v4 model rewrite."""
    return {}
