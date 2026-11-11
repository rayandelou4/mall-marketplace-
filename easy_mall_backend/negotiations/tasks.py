from celery import shared_task

from .services import expire_stale_negotiations


@shared_task(name="negotiations.expire_stale_negotiations")
def expire_stale_negotiations_task():
    return expire_stale_negotiations()