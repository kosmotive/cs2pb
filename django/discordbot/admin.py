from django.contrib import admin

from discordbot.models import ScheduledNotification, InvitationDraft


@admin.register(ScheduledNotification)
class ScheduledNotificationAdmin(admin.ModelAdmin):

    model = ScheduledNotification
    list_display = ('scheduled_datetime', 'squad', '_text')

    list_filter = ('squad',)

    def _text(self, notification):
        return str(notification)


@admin.register(InvitationDraft)
class InvitationDraftAdmin(admin.ModelAdmin):

    model = InvitationDraft
    list_display = ('steam_profile', 'discord_name')

