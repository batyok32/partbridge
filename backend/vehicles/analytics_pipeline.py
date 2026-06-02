"""Queue vehicle market analytics after DB commit (Celery)."""

from __future__ import annotations

from django.db import transaction


def attach_analytics_after_commit(vehicle_id: int) -> None:
    def _enqueue() -> None:
        from analytics.tasks import run_vehicle_market_analysis

        run_vehicle_market_analysis.delay(vehicle_id)

    transaction.on_commit(_enqueue)
