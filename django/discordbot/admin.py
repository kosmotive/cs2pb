from discordbot.models import (
    InvitationDraft,
    ScheduledNotification,
)

from django.contrib import admin


@admin.register(ScheduledNotification)
class ScheduledNotificationAdmin(admin.ModelAdmin):

    model = ScheduledNotification
    list_display = ('scheduling_date_and_time', 'squad', '_text')

    list_filter = ('squad',)

    def _text(self, notification):
        return str(notification)


@admin.register(InvitationDraft)
class InvitationDraftAdmin(admin.ModelAdmin):

    model = InvitationDraft
    list_display = ('steam_profile', 'discord_name')
