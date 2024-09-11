from stats.models import (
    MatchBadge,
    MatchParticipation,
)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.safestring import mark_safe

from .forms import (
    AccountChangeForm,
    AccountCreationForm,
    SteamProfileCreationForm,
)
from .models import (
    Account,
    Invitation,
    Squad,
    SquadMembership,
    SteamProfile,
)


class MatchParticipationInline(admin.TabularInline):
    model = MatchParticipation
    fields = ('datetime', 'result', 'kills', 'assists', 'deaths', 'score', 'mvps', 'headshots')
    readonly_fields = ('datetime',)

    def datetime(self, mp):
        return mp.pmatch.datetime


@admin.action(description = 'Fetch matches')
def fetch_matches(modeladmin, request, queryset):
    for account in queryset.all():
        account.update_matches(force = True)


@admin.action(description = 'Award match badges')
def award_match_badges(modeladmin, request, queryset):
    for account in queryset.all():
        old_participations = list()
        for participation in MatchParticipation.objects.filter(
            player = account.steam_profile,
        ).order_by('pmatch__timestamp'):
            MatchBadge.award(participation, old_participations, dry = True)
            old_participations.append(participation)


@admin.register(Account)
class AccountAdmin(UserAdmin):

    add_form = AccountCreationForm
    form     = AccountChangeForm
    model    = Account

    actions = [fetch_matches, award_match_badges]

    list_display = (
        'name',
        'steamid',
        'email_address',
        'discord_name',
        'is_staff',
        'enabled',
        '_last_scheduled_update',
        '_last_completed_update',
    )
    list_filter = ('is_staff', 'enabled',)

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'steam_profile',
                    'clean_name',
                    'steam_auth',
                    'email_address',
                    'discord_name',
                    'last_sharecode',
                    'enabled',
                )
            },
        ),
        (
            'Permissions',
            {
                'fields': ('is_staff', 'is_active')
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'steam_profile',
                    'password1',
                    'password2',
                    'steam_auth',
                    'discord_name',
                    'last_sharecode',
                    'is_staff',
                    'is_active',
                    'enabled',
                )
            },
        ),
    )
    search_fields = ('steam_profile', 'clean_name')
    ordering = ('steam_profile',)

    def _last_scheduled_update(self, account):
        if account.last_queued_update is None:
            return None
        else:
            url = reverse('admin:stats_updatetask_change', args=(account.last_queued_update.pk,))
            return mark_safe(f'<a href="{url}">{account.last_queued_update.scheduled_datetime}</a>')

    def _last_completed_update(self, account):
        if account.last_completed_update is None:
            return None
        else:
            url = reverse('admin:stats_updatetask_change', args=(account.last_completed_update.pk,))
            return mark_safe(f'<a href="{url}">{account.last_completed_update.completed_datetime}</a>')


@admin.register(SteamProfile)
class SteamProfileAdmin(admin.ModelAdmin):

    add_form = SteamProfileCreationForm
    model    = SteamProfile

    list_display = ('steamid', 'name', 'squad_list', '_actions')
    fieldsets = (
        (None, {'fields': ('steamid', 'name', '_avatar_s', '_avatar_m', '_avatar_l', 'squad_list')}),
    )
    readonly_fields = ('steamid', 'squad_list', 'name', '_avatar_s', '_avatar_m', '_avatar_l')
    search_fields = ('steamid', 'name', 'account__clean_name')

    def has_add_permission(self, request, obj = None):
        return False

    @admin.display(description = 'Squads')
    def squad_list(self, steam_profile):
        squads = [m.squad for m in steam_profile.squad_memberships.all()]
        number = len(squads)

        def get_url(squad):
            return reverse('admin:accounts_squad_change', args = (squad.pk,))

        def get_html(squad):
            return f'<a href="{get_url(squad)}">{squad.name}</a>'

        return mark_safe(f'{", ".join([get_html(s) for s in squads])} ({number})' if number > 0 else '&ndash;')

    def _avatar_s(self, sp):
        return mark_safe(f'<img src="{sp.avatar_s}"><br><a href="{sp.avatar_s}">{sp.avatar_s}</a>')

    def _avatar_m(self, sp):
        return mark_safe(f'<a href="{sp.avatar_m}">{sp.avatar_m}</a>')

    def _avatar_l(self, sp):
        return mark_safe(f'<a href="{sp.avatar_l}">{sp.avatar_l}</a>')

    def _actions(self, obj):
        export_csv_url = reverse('csv', args = (obj.pk,))
        create_notebook_url = reverse('notebook', args = (obj.pk,))
        return mark_safe(
            f'<a class="btn" href="{export_csv_url}">Export CSV</a>, '
            f'<a class="btn" href="{create_notebook_url}">Create Notebook</a>'
        )

    inlines = [
        MatchParticipationInline,
    ]


@admin.action(description = 'Announce on Discord')
def announce_on_discord(modeladmin, request, queryset):
    from discordbot.models import ScheduledNotification
    for squad in queryset.all():
        if squad.discord_channel_id:
            url  = squad.absolute_url(request)
            text = f'{url}\nWanna join the cool kids\' club? Type `/join`!'
            ScheduledNotification.objects.create(squad = squad, text = text)


@admin.action(description = 'Update stats')
def update_stats(modeladmin, request, queryset):
    for squad in queryset.all():
        squad.update_stats()


@admin.register(Squad)
class SquadAdmin(admin.ModelAdmin):

    model = Squad

    list_display = ('name', 'uuid', 'members_count')

    actions = [announce_on_discord, update_stats]

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).prefetch_related('memberships')

    @admin.display(description='Members')
    def members_count(self, squad):
        return str(len(squad.memberships.all()))


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):

    model = Invitation
    list_display = ('uuid', 'steam_profile', 'squad', '_url')

    def get_queryset(self, request):
        self.request = request
        return super().get_queryset(request)

    def _url(self, invitation):
        url = invitation.absolute_url(self.request)
        return mark_safe(f'<a href="{url}">{url}</a>')


@admin.register(SquadMembership)
class SquadMembershipAdmin(admin.ModelAdmin):

    model = SquadMembership
    list_display = ('player', 'squad', 'position', 'stats', 'trends')
    list_filter = ('squad',)
