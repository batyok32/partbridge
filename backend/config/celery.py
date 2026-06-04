import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("lookmypart")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "analytics-cleanup-old": {
        "task": "analytics.tasks.cleanup_old_analyses",
        "schedule": crontab(day_of_month=1, hour=4, minute=0),
    },
    "expire-buy-now-listings": {
        "task": "vehicles.tasks.expire_buy_now_listings",
        "schedule": crontab(minute="*/15"),
    },
    "orders-enforce-first-sale-verification": {
        "task": "orders.tasks.enforce_first_sale_verification_deadline",
        "schedule": crontab(minute="*/30"),
    },
    "orders-auto-cancel-unconfirmed": {
        "task": "orders.tasks.auto_cancel_unconfirmed_paid_orders",
        "schedule": crontab(minute="*/15"),
    },
    # Auto-deliver shipped orders after AUTO_DELIVER_DAYS days
    "orders-auto-deliver-shipped": {
        "task": "orders.tasks.auto_deliver_shipped_orders",
        "schedule": crontab(minute=0, hour="*/4"),  # every 4 hours
    },
    # Transfer seller earnings for orders past their hold period
    "orders-process-seller-payouts": {
        "task": "orders.tasks.process_seller_payouts",
        "schedule": crontab(minute=30, hour="*/2"),  # every 2 hours
    },
}
