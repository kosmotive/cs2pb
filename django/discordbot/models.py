import logging
import re
from datetime import datetime

from accounts.models import (
    Squad,
    SteamProfile,
)

from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver

log = logging.getLogger(__name__)

steamid_pattern = re.compile(r'<([0-9]+)>')
url_pattern = re.compile(r'<(/[a-zA-Z0-9-_/%?&\.]+)>')


def timestamp_now():
    return round(datetime.timestamp(datetime.now()))


class InvitationDraft(models.Model):

    steam_profile = models.OneToOneField(SteamProfile, on_delete = models.PROTECT, unique = True)
    discord_name  = models.CharField(blank = True , max_length = 30, unique = True)

    def create_invitation(self, squad):
        return self.steam_profile.invite(squad, discord_name = self.discord_name)


class ScheduledNotification(models.Model):

    scheduling_timestamp = models.PositiveBigIntegerField(verbose_name = 'Scheduled', default = timestamp_now)
    squad = models.ForeignKey(Squad, related_name = 'notifications', on_delete = models.CASCADE)
    text  = models.TextField(blank = False)

    @property
    def scheduling_datetime(self):
        return datetime.fromtimestamp(self.scheduling_timestamp)

    @property
    def scheduling_date_and_time(self):
        return self.scheduling_datetime.strftime(r'%b %-d, %Y, %H:%M')

    def resolve_text(self, lookup, settings):
        """
        """
        text = self.text

        # Resolve Steam IDs
        for steamid in frozenset(steamid_pattern.findall(self.text)):
            p = SteamProfile.objects.get(steamid = steamid)
            r = None
            if getattr(p, 'account', None) is not None and len(p.account.discord_name) > 0:
                r = lookup(p.account.discord_name)
            if r is None:
                r = p.name
            text = text.replace(f'<{steamid}>', r)

        # Resolve URLs
        for url in frozenset(url_pattern.findall(self.text)):
            text = text.replace(f'<{url}>', f'{settings.get("base_url", "")}{url}')

        # Return resolved text
        return text

    def __str__(self):
        from accounts.models import SteamProfile

        def lookup(steamid):
            try:
                return SteamProfile.objects.get(pk = str(steamid)).name
            except SteamProfile.DoesNotExist:
                log.critical(f'Failed to lookup Steam ID: {steamid}')

        return self.resolve_text(lookup, dict())

    attachments = dict()

    def attach(self, data):
        ScheduledNotification.attachments[self.pk] = data

    def get_attachment(self):
        return ScheduledNotification.attachments.get(self.pk, None)

    @receiver(pre_delete)
    def remove_attachment(sender, instance, **kwargs):
        ScheduledNotification.attachments.pop(instance.pk, None)
