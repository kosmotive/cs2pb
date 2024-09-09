import datetime
import logging
import uuid

from api import api
from stats.features import (
    FeatureContext,
    Features,
)
from stats.updater import queue_update_task
from url_forward import get_redirect_url_to

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

log = logging.getLogger(__name__)

CLEAN_NAME_VALIDATOR = RegexValidator(r'^[0-9a-zA-Z.-_][0-9a-zA-Z.-_ ]+[0-9a-zA-Z.-_]+$')

MIN_BREAK_TIME = 60 * 60 * 2  # 2 hours


class SteamProfile(models.Model):

    steamid  = models.CharField(blank=False, max_length=30, primary_key=True, verbose_name='Steam ID')
    name     = models.CharField(blank=False, max_length=30, db_index=True)
    avatar_s = models.CharField(blank=False, max_length=100, verbose_name='Avatar small')
    avatar_m = models.CharField(blank=False, max_length=100, verbose_name='Avatar medium')
    avatar_l = models.CharField(blank=False, max_length=100, verbose_name='Avatar large')

    def save(self, *args, **kwargs):
        profile = api.fetch_profile(self.steamid)
        self.name     = profile['personaname']
        self.avatar_s = profile['avatar']
        self.avatar_m = profile['avatarmedium']
        self.avatar_l = profile['avatarfull']
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.steamid})'

    @property
    def clean_name(self):
        if getattr(self, 'account', None) is not None and self.account.clean_name:
            return self.account.clean_name
        else:
            return self.name

    def match_badges(self, **kwargs):
        from stats.models import MatchBadge
        return MatchBadge.objects.filter(participation__player = self, **kwargs)

    def matches(self, **kwargs):
        from stats.models import Match
        return Match.objects.filter(matchparticipation__player=self)

    def match_participations(self,  **filters):
        from stats.models import MatchParticipation
        return MatchParticipation.objects.filter(player=self, **filters)

    def find_oldest_sharecode(self):
        matches_played = self.matches()
        assert len(matches_played) > 0
        return matches_played.earliest('timestamp').sharecode

    def invite(self, squad, **kwargs):
        invitations = Invitation.objects.filter(steam_profile = self, squad = squad)
        if len(invitations) == 0:
            return Invitation.objects.create(steam_profile = self, squad = squad, **kwargs)
        else:
            invitation = invitations.get()
            if len(kwargs) > 0:
                for key in kwargs:
                    setattr(invitation, key, kwargs[key])
                invitation.save()
            return invitation


class AccountManager(BaseUserManager):

    def create_user(self, steamid, password, **extra_fields):
        assert steamid
        steam_profile = SteamProfile.objects.create(steamid=steamid)
        account = self.model(steam_profile=steam_profile, **extra_fields)
        account.set_password(password)
        account.save()
        return account

    def create_superuser(self, steamid, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        assert extra_fields.get('is_staff') is not False
        assert extra_fields.get('is_superuser') is not False
        return self.create_user(steamid, password, **extra_fields)


class Account(AbstractUser):

    username = None

    steam_profile  = models.OneToOneField(
        SteamProfile,
        on_delete = models.PROTECT,
        related_name = 'account',
        primary_key = True,
    )
    steam_auth = models.CharField(
        blank = False,
        max_length = 30,
        verbose_name = 'Match History Authentication Code',
    )
    email_address = models.EmailField(
        max_length = 200,
        blank = False,
        unique = True,
    )
    discord_name = models.CharField(
        blank = True,
        max_length = 30,
    )
    last_sharecode = models.CharField(
        blank = True,
        max_length = 50,
    )
    clean_name = models.CharField(
        blank = True,
        max_length = 30,
        validators = [CLEAN_NAME_VALIDATOR],
    )
    enabled = models.BooleanField(
        default = True,
        help_text = 'Designates whether updates for this user are fetched from the Steam API '
                    '(turned off if the API refuses a sharecode).',
    )

    USERNAME_FIELD = 'steam_profile'
    REQUIRED_FIELDS = ['steam_auth']

    objects = AccountManager()

    def __str__(self):
        return str(self.steam_profile)

    @property
    def name(self):
        return self.steam_profile.name

    @property
    def steamid(self):
        return self.steam_profile.steamid

    def matches(self, **kwargs):
        return self.steam_profile.matches(**kwargs)

    def match_participations(self, **kwargs):
        return self.steam_profile.match_participations(**kwargs)

    @property
    def sharecode(self):
        # FIXME: `find_oldest_sharecode` should be the sharecode of a match,
        # where this user participated, and not just any
        return self.steam_profile.find_oldest_sharecode() if len(self.last_sharecode) == 0 else self.last_sharecode

    @property
    def last_queued_update(self):
        return None if len(self.update_tasks.all()) == 0 else self.update_tasks.latest('scheduled_timestamp')

    @property
    def last_completed_update(self):
        qs = self.update_tasks.exclude(completed_timestamp=None)
        return None if len(qs) == 0 else qs.latest('scheduled_timestamp')

    @property
    def last_match(self):
        return self.matches().latest('timestamp')

    @property
    def had_break_after_last_match(self):
        if self.last_completed_update is None or self.last_match is None:
            return False
        return self.last_completed_update.completed_timestamp - (
            self.last_match.timestamp + self.last_match.duration
        ) >= MIN_BREAK_TIME

    def update_matches(self, force=False):
        last_queued_update = self.last_queued_update
        if last_queued_update is None or force or (
            datetime.datetime.now() - last_queued_update.scheduled
        ).total_seconds() / 60 >= 5:
            return queue_update_task(self)
        else:
            return None

    def handle_finished_update(self):
        for m in self.steam_profile.squad_memberships.all():
            last_session = m.squad.last_session
            if last_session is None or last_session.is_closed:
                continue
            session_ended = True
            for account in m.squad.accounts:
                if not account.had_break_after_last_match:
                    session_ended = False
                    break
            if session_ended:
                last_session.close()


class Squad(models.Model):

    uuid = models.UUIDField(
        primary_key = True,
        default = uuid.uuid4,
        editable = False,
    )
    name = models.CharField(
        blank = False,
        max_length = 100,
    )
    discord_channel_id = models.CharField(
        blank = True,
        max_length = 50,
        verbose_name = 'Discord Channel ID',
        unique = True,  # FIXME: Should be nullable, so that there can be more than one squad without a Discord channel?
    )
    last_changelog_announcement = models.CharField(
        blank = True,
        max_length = 40,
        default = '',
    )

    def __str__(self):
        return self.name

    def matches(self, **kwargs):
        from stats.models import Match
        return Match.objects.filter(
            matchparticipation__player__in = self.memberships.values_list('player__pk', flat = True),
            **kwargs,
        )

    def match_participations(self, **kwargs):
        from stats.models import MatchParticipation
        return MatchParticipation.objects.filter(
            player__in = self.memberships.values_list('player__pk', flat = True),
            **kwargs,
        )

    @property
    def url(self):
        return reverse('squads', kwargs = dict(squad = self.uuid))

    def absolute_url(self, request):
        return request.build_absolute_uri(self.url)

    @property
    def last_session(self):
        from stats.models import GamingSession
        sessions = GamingSession.objects.filter(squad = self)
        if len(sessions) == 0:
            return None
        return sessions.latest('matches__timestamp')

    def handle_new_match(self, pmatch):
        from stats.models import GamingSession
        last_session = self.last_session
        if last_session is None or last_session.is_closed or pmatch.timestamp - last_session.ended > MIN_BREAK_TIME:
            if last_session is not None:
                last_session.close()
            log.info(f'Assigning match {pmatch.pk} to new gaming session')
            last_session = GamingSession.objects.create(squad = self)
        else:
            log.info(f'Assigning match {pmatch.pk} to current gaming session')
        if last_session.matches.exists() and pmatch.timestamp < last_session.ended:
            log.info(f'Not assigning match {pmatch.pk} to any gaming session (it was in the past)')
            return
        pmatch.sessions.add(last_session)
        pmatch.save()

    @property
    def accounts(self):
        for m in self.memberships.all():
            account = getattr(m.player, 'account', None)
            if account is not None:
                yield account

    def do_changelog_announcements(self, base_url='', changelog=None):
        if changelog is None:
            from gitinfo import changelog

        # Do not make announcements for new squads, or those which do not have a Discord channel
        if self.last_changelog_announcement != '' and self.discord_channel_id != '':

            announcements = list()
            for entry in changelog:

                if entry['sha'] == self.last_changelog_announcement:
                    break
                else:
                    announcements.append(entry)

            if len(announcements) > 0:

                def obscure_url(url):
                    return base_url + get_redirect_url_to(url)

                def fmt(entry):
                    return f'\n\n🚀 **{entry["date"]}:** {entry["message"]} [More info]({obscure_url(entry["url"])})'

                text = 'I have just received some updates:' + ''.join(fmt(entry) for entry in announcements)
                self.notify_on_discord(text)

        self.last_changelog_announcement = changelog[0]['sha']
        self.save()

    def update_stats(self) -> None:
        """
        Update the stats, trends, and leaderboard positions of the squad members.
        """
        for m in self.memberships.all():
            m.update_stats()

        # Store the current positions for later comparison
        old_positions = {m: m.position for m in self.memberships.all()}

        # Update the positions according to the KPI
        kpis = {m: m.stats['player_value'] for m in self.memberships.all()}
        memberships = sorted(
            (m for m in kpis.keys() if kpis[m] is not None),
            key = lambda m: kpis[m],
            reverse = True,
        )
        for position, m in enumerate(memberships):
            m.position = position
            m.save()
        for m in self.memberships.exclude(pk__in = [m.pk for m in memberships]):
            m.position = None
            m.save()

        # Check if the leaderboard has changed
        changes = {
            m: m.position - old_positions[m] for m in self.memberships.all()
            if m.position is not None and old_positions[m] is not None
        }
        if len([m for m in old_positions.keys() if old_positions[m] is not None]) > 0 and (
            any(change != 0 for change in changes.values()) or (
                {
                    m.player.steamid for m in old_positions.keys() if old_positions[m] is not None
                } != {
                    m.player.steamid for m in memberships
                }
            )
        ):
            text = 'We have changes in the 30-days leaderboard! 🎆\n'

            # Check if the positions have changed
            for mnum, m in enumerate(self.memberships.filter(position__isnull = False).order_by('position'), start = 1):
                text += f'\n{mnum}. <{m.player.steamid}>'
                if m not in changes:
                    text += f' 🆕'
                else:
                    if changes[m] > 0:
                        text += f' ⬇️'
                    if changes[m] < 0:
                        text += f' ⬆️'

            # Check if players have been removed from the leaderboard (e.g., due to inactivity)
            missed_memberships = [
                m for m in old_positions.keys()
                if old_positions[m] is not None and m.pk not in self.memberships.filter(
                    position__isnull = False,
                ).values_list('pk', flat = True)
            ]
            if len(missed_memberships) > 0:
                text += '\n'
                for m in missed_memberships:
                    text += f'\n<{m.player.steamid}> is no longer present 👋'

            # Schedule a notification on Discord
            self.notify_on_discord(text)

    def notify_on_discord(self, text: str):
        if self.discord_channel_id:
            from discordbot.models import ScheduledNotification
            return ScheduledNotification.objects.create(squad = self, text = text)
        else:
            return None


class SquadMembership(models.Model):

    squad = models.ForeignKey(
        Squad,
        related_name = 'memberships',
        on_delete = models.CASCADE,
    )
    player = models.ForeignKey(
        SteamProfile,
        related_name = 'squad_memberships',
        on_delete = models.CASCADE,
    )
    position = models.PositiveSmallIntegerField(
        null = True,
        default = None,
    )
    stats = models.JSONField(
        default = dict,
    )
    trends = models.JSONField(
        default = dict,
    )

    @property
    def accounted_match_participations(self):
        """
        Return the match participations of the squad member that are relevant for the stats computation
        """
        return self.squad.match_participations(
            pmatch__timestamp__gte = datetime.datetime.timestamp(
                datetime.datetime.now()
            ) - 30 * 24 * 60 * 60,  # 30 days ago
            pmatch__sessions__is_closed = True,  # Exclude matches from sessions that did not end yet
        )

    def update_stats(self):
        """
        Update the stats and trends of the squad member based on their performance in the last 30 days.
        """

        # Store the current stats for later comparison
        previous_stats = dict(self.stats)

        # Update the stats
        ctx = FeatureContext(self.accounted_match_participations, self.player)
        self.stats.clear()
        for feature in Features.all:
            self.stats[feature.slug] = feature(ctx)

        # Prune dangling trends from old versions of the feature set
        for feature in list(self.trends.keys()):
            if feature not in self.stats:
                del self.trends[feature]

        # Compute the trends
        for feature in Features.all:
            feature_value = self.stats.get(feature.slug)
            previous_feature_value = previous_stats.get(feature.slug)

            # Compute the trend if both the current and previous feature values are available
            if feature_value is not None and previous_feature_value is not None:
                trend = feature_value - previous_feature_value

                # Preserve the previous trend value if nothing has changed since the last update
                if trend != 0:
                    self.trends[feature.slug] = trend

            # Otherwise, the trend is undefined
            else:
                self.trends[feature.slug] = None

        # Save the updated data
        self.save()


class Invitation(models.Model):

    uuid          = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    steam_profile = models.OneToOneField(SteamProfile, on_delete = models.PROTECT)
    squad         = models.ForeignKey(Squad, on_delete = models.CASCADE, related_name = 'invitations')
    discord_name  = models.CharField(blank = True , max_length = 30)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['steam_profile', 'squad'], name = 'unique_steam_profile_squad'
            ),
        ]

    @property
    def url(self):
        return reverse('join', args = (self.pk,))

    def absolute_url(self, request):
        return request.build_absolute_uri(self.url)
