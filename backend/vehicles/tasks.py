"""Celery tasks for vehicles (v4 — stub)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import close_old_connections

logger = logging.getLogger(__name__)


@shared_task
def placeholder_task() -> dict:
    """Placeholder — old vehicle tasks removed with v4 model rewrite."""
    return {}
