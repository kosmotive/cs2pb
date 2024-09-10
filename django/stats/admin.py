from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse

from stats.models import Match, MatchParticipation, PlayerOfTheWeek, MatchBadge, MatchBadgeType, UpdateTask, GamingSession


class MatchParticipationInline(admin.TabularInline):
    model = MatchParticipation
    ordering = ('team', '-adr')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):

    model = Match

    def has_add_permission(self, request, obj=None):
        return False

    list_display = ('map_name', 'date_and_time', 'score_team1', 'score_team2', 'session_list')
    list_filter = ('map_name',)

    search_fields = ('map_name', 'timestamp', 'sharecode')
    ordering = ('-timestamp',)

    inlines = [
        MatchParticipationInline,
    ]

    @admin.display(description='Session')
    def session_list(self, pmatch):
        sessions = pmatch.sessions.all()
        number = len(sessions)
        get_url  = lambda session: reverse('admin:stats_gamingsession_change', args=(session.pk,))
        get_html = lambda session: f'<a href="{get_url(session)}">{session.pk}</a>'
        return mark_safe(f'{", ".join([get_html(s) for s in sessions])}' if number > 0 else '&ndash;')


@admin.register(PlayerOfTheWeek)
class PlayerOfTheWeekAdmin(admin.ModelAdmin):

    model = PlayerOfTheWeek

    list_display = ('name', 'challenge_end_datetime', 'squad', 'player1', 'player2', 'player3')
    list_filter = ('squad',)
    readonly_fields = ('timestamp', 'squad')

    def name(self, potw):
        return str(potw)


@admin.register(MatchBadgeType)
class MatchBadgeTypeAdmin(admin.ModelAdmin):

    model = MatchBadgeType

    list_display = ('slug', 'name')

    readonly_fields = ()

    def get_readonly_fields(self, request, obj=None):
        if obj: return self.readonly_fields + ('slug',)
        else: return self.readonly_fields


@admin.register(MatchBadge)
class MatchBadgeAdmin(admin.ModelAdmin):

    model = MatchBadge

    list_display = ('_badge_type', '_match', '_player')
    list_filter = ('badge_type__name',)
    search_fields = ('participation__pmatch__map_name', 'participation__player__name', 'participation__player__steamid')

    def _badge_type(self, badge):
        return badge.badge_type.name

    def _match(self, badge):
        return badge.participation.pmatch

    def _player(self, badge):
        return badge.participation.player


@admin.register(UpdateTask)
class UpdateTaskAdmin(admin.ModelAdmin):

    model = UpdateTask

    list_display = ('account', '_is_completed', 'scheduling_datetime', '_execution_datetime', '_completion_datetime', '_actions')
    list_filter = (('completion_timestamp', admin.EmptyFieldListFilter),)

    def _execution_datetime(self, task):
        return task.execution_date_and_time or 'Pending'

    def _completion_datetime(self, task):
        return task.completion_date_and_time or 'Pending'

    def _is_completed(self, task):
        return task.is_completed

    _is_completed.boolean = True

    def _actions(self, obj):
        url = reverse('admin:stats_updatetask_delete', args=(obj.pk,))
        return mark_safe(f'<a class="btn" href="{url}">Delete</a>')


@admin.action(description='Close selected gaming sessions')
def close_session(modeladmin, request, queryset):
    for session in queryset.all():
        session.close()


@admin.register(GamingSession)
class GamingSessionAdmin(admin.ModelAdmin):

    model = GamingSession

    list_display = ('id', 'squad', 'participants_list', 'is_closed', 'started_date_and_time', 'ended_date_and_time')
    list_filter = ('squad',)

    fieldsets = (
        (None, {'fields': ('squad', 'is_closed', 'started_date_and_time', 'ended_date_and_time', 'rising_star')}),
    )
    add_fieldsets = (
        (None, {'fields': ('squad', 'rising_star')}),
    )
    readonly_fields = ('started_date_and_time', 'ended_date_and_time')

    actions = [close_session]

    @admin.display(description='Participants')
    def participants_list(self, gs):
        participants = gs.participants
        number = len(participants)
        get_url  = lambda player: reverse('admin:accounts_steamprofile_change', args=(player.pk,))
        get_html = lambda player: f'<a href="{get_url(player)}">{player.name}</a>'
        return mark_safe(f'{", ".join([get_html(p) for p in participants])} ({number})' if number > 0 else '&ndash;')

    def get_fieldsets(self, request, obj=None):                                  
        if not obj: return self.add_fieldsets                                            
        else: return super().get_fieldsets(request, obj)
