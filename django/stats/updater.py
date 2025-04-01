import datetime
import logging
import threading
import time

log = logging.getLogger(__name__)

update_thread = None
update_event  = threading.Event()


def run_update_loop():
    try:
        while True:
            update_event.wait()
            update_event.clear()

            # Wait for a while to gather more tasks into a single run, to exploit more `recent_matches`
            time.sleep(1)

            run_pending_tasks()
    finally:
        global update_thread
        update_thread = None


def run_pending_tasks():
    from stats.models import UpdateTask
    pending_tasks = UpdateTask.objects.filter(completion_timestamp=None).order_by('-scheduling_timestamp').all()
    if len(pending_tasks) > 0:
        log.info('Begin processing %d pending task(s)' % len(pending_tasks))
        recent_matches = list()
        for task in pending_tasks:
            try:
                task.run(recent_matches)
            except:  # noqa: E722
                log.critical(f'Failed to update stats.', exc_info = True)
        log.info('Finished processing %d pending task(s)' % len(pending_tasks))


def queue_update_task(account):
    global update_thread
    from stats.models import UpdateTask
    task = UpdateTask.objects.create(
        account = account,
        scheduling_timestamp = datetime.datetime.timestamp(datetime.datetime.now()),
    )
    if update_thread is None:
        update_thread = threading.Thread(target=run_update_loop, daemon=True)
        update_thread.start()
    update_event.set()  # wakeup the thread
    return task
