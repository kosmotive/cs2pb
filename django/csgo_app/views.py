import os

import gitinfo

from django.core.mail import send_mail
from django.db.models import Count

ADMIN_MAIL_ADDRESS = os.environ['CS2PB_ADMIN_MAIL_ADDRESS']
assert len(ADMIN_MAIL_ADDRESS) > 0


def add_globals_to_context(context):
    from stats.models import UpdateTask
    context['version'] = gitinfo.get_head_info()
    qs = UpdateTask.objects.filter(completion_timestamp = None)
    qs = qs.values('account').annotate(count = Count('account'))
    if qs.count() > 0 and qs.latest('count')['count'] > 1:
        msg = 'There is a temporary malfunction of the Steam Client API.'
        context['error'] = f'{msg} Come back later.'
        send_mail('Steam API malfunction', msg, ADMIN_MAIL_ADDRESS, [ADMIN_MAIL_ADDRESS], fail_silently=True)
