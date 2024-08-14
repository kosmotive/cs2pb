import datetime
import logging
import threading

from django.db import transaction


log = logging.getLogger(__name__)

update_thread = None
update_event  = threading.Event()


def run_update_loop():
    while True:
        update_event.wait()
        update_event.clear()
        run_pending_tasks()
    update_thread = None  # FIXME: is this obsolete?


def run_pending_tasks():
    from stats.models import UpdateTask
    pending_tasks = UpdateTask.objects.filter(completed_timestamp=None).order_by('-scheduled_timestamp').all()
    for task in pending_tasks:
        try:
            task.run()
        except:
            log.critical(f'Failed to update stats.', exc_info=True)


def queue_update_task(account):
    global update_thread
    from stats.models import UpdateTask
    task = UpdateTask.objects.create(account=account, scheduled_timestamp=datetime.datetime.timestamp(datetime.datetime.now()))
    if update_thread is None:
        update_thread = threading.Thread(target=run_update_loop, daemon=True)
        update_thread.start()
    update_event.set() # wakeup the thread
    return task

