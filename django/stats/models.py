import logging
from datetime import (
    datetime,
    timedelta,
)

import numpy as np
from accounts.models import (
    Account,
    Squad,
    SteamProfile,
)
from cs2pb_typing import (
    FrozenSet,
    List,
    Literal,
    Optional,
    Self,
    Tuple,
)

from django.conf import settings
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
)
from django.db import (
    models,
    transaction,
)
from django.db.models import (
    Avg,
    F,
    QuerySet,
)
from django.db.models.signals import m2m_changed

from . import potw

log = logging.getLogger(__name__)


def csgo_timestamp_to_datetime(timestamp) -> datetime:
    """
    Convert a CSGO timestamp to a `datetime` object.
    """
    return datetime.fromtimestamp(timestamp)


def csgo_timestamp_to_strftime(timestamp: int, fmt: str = r'%b %-d, %Y, %H:%M') -> str:
    """
    Convert a CSGO timestamp to a formatted string.
    """
    return csgo_timestamp_to_datetime(timestamp).strftime(fmt)


class GamingSession(models.Model):
    """
    A gaming session is a period of time during which a squad plays matches.

    The matches do not have to be played together. Possibly, each squad member plays separately.
    """

    squad = models.ForeignKey(Squad, related_name = 'sessions', on_delete = models.CASCADE)
    """
    The squad that played the matches in this session.
    """

    is_closed = models.BooleanField(default = False)
    """
    Whether the session is closed. A closed session is one that has ended and for which the performance of the players
    has been computed.
    """

    rising_star = models.ForeignKey(
        SteamProfile,
        on_delete = models.CASCADE,
        null = True,
        blank = True,
    )
    """
    The player who was the rising star of the session (if any).
    """

    def close(self) -> None:
        """
        Close the session.
        """
        from .features import (
            FeatureContext,
            Features,
        )

        was_already_closed = self.is_closed
        self.is_closed = True
        self.save()

        # Ensure that the session is not closed twice
        if was_already_closed:
            return

        # Process the participated squad members
        participated_steamids = self.participated_steamids
        comments: List[str] = list()
        top_player: Optional[SteamProfile] = None
        top_player_trend_rel: float = 0
        participated_squad_members: int = 0
        feature_contexts = dict()
        for m in self.squad.memberships.all():

            if m.player.steamid not in participated_steamids:
                continue
            participated_squad_members += 1

            # Compute the PV of the player in this session
            feature_contexts[m.player.steamid] = (
                ctx := FeatureContext(
                    MatchParticipation.objects.filter(player = m.player, pmatch__sessions = self),
                    m.player,
                )
            )
            pv_today = Features.player_value(ctx)

            # Skip further consideration if today's PV or the reference PV is not available
            pv_ref = m.stats.get('player_value', None)
            if pv_today is None or pv_ref is None:
                continue

            # Compute the relative trend
            pv_trend = pv_today - pv_ref
            kpi = dict(
                value = pv_today,
                trend_rel = 0 if pv_trend == 0 else (pv_trend / pv_ref if pv_ref > 0 else np.infty),
            )

            # Update the top squad participant
            if top_player is None or kpi['trend_rel'] > top_player_trend_rel:
                top_player = m.player
                top_player_trend_rel = kpi['trend_rel']

            # Proclaim the PV trend of the player, if their relative trend *rounded to 1 decimal* is larger than 0.1%
            if abs(kpi['trend_rel']) > 0.0005:
                icon = '📈' if kpi['trend_rel'] > 0 else '📉'
                comments.append(
                    f' <{m.player.steamid}> {icon} {100 * kpi["trend_rel"]:+.1f}% ({kpi["value"]:.2f})'
                )

            # Otherwise, just proclaim the PV of the player
            else:
                comments.append(
                    f' <{m.player.steamid}> ±0.00% ({kpi["value"]:.2f})'
                )

        # Compose the notification text for Discord out of the comments generated above
        text = 'Looks like your session has ended!'
        if len(comments) > 0:
            text += ' Here is your current performance compared to your 30-days average: ' + ', '.join(comments)
            text += ', with respect to the *player value*.'
        self.squad.notify_on_discord(text)

        # Compose another notification for a summary of the matches
        text = 'Matches played in this session:'
        for pmatch in self.matches.filter(
            matchparticipation__player__in = self.squad.memberships.values_list('player__pk', flat = True)
        ).distinct().order_by('timestamp').annotate(
            result = F('matchparticipation__result')
        ):
            text += f'\n- *{pmatch.map_name}*, **{pmatch.score_team1}:{pmatch.score_team2}**'
            if pmatch.result in 'wl':
                text += ' ' + dict(
                    w = 'won 🤘',
                    l = 'lost 💩',
                )[pmatch.result]
        self.squad.notify_on_discord(text)

        # Determine the rising star (if any)
        if participated_squad_members > 1 and top_player is not None and top_player_trend_rel > 0.01:
            from .plots import trends as plot_trends
            notification = self.squad.notify_on_discord(
                f'And today\'s **rising star** was: 🌟 <{top_player.steamid}>! '
                f'<{top_player.url(squad = self.squad)}>'
            )
            if notification is not None:
                plot = plot_trends(
                    self.squad.memberships.filter(player = top_player).get(),
                    feature_contexts[top_player.steamid],  # The feature context for the session trends
                    [
                        Features.player_value,
                        Features.assists_per_death,
                        Features.headshot_rate,
                        Features.damage_per_round,
                        Features.kills_per_death,
                    ],
                )
                notification.attach(plot)
            self.rising_star = top_player
            self.save()

    @staticmethod
    def sessions_changed(sender, action, pk_set, instance, **kwargs):
        if action == 'pre_add':
            added_sessions = [GamingSession.objects.get(pk = session_pk) for session_pk in pk_set]
            for session in added_sessions:
                if session.is_closed:
                    continue
                if GamingSession.objects.filter(
                    squad = session.squad,
                    is_closed = True,
                    matches__timestamp__gt = instance.ended_timestamp,
                ).exists():
                    log.info(
                        f'Setting session {session.pk} added to match {instance.pk} (str(instance)) to closed '
                        f'since a new closed session of the same squad exists'
                    )
                    session.is_closed = True
                    session.save()

    @property
    def participated_steamids(self) -> FrozenSet[str]:
        """
        Get the Steam IDs of the players who participated in the session.
        """
        steamids = set()
        for pmatch in self.matches.all():
            for mp in pmatch.matchparticipation_set.all():
                steamids.add(mp.player.steamid)
        return frozenset(steamids)

    @property
    def participants(self) -> List[SteamProfile]:
        """
        Get the players who participated in the session.
        """
        return [SteamProfile.objects.get(steamid = steamid) for steamid in self.participated_steamids]

    @property
    def participated_squad_members_steamids(self) -> QuerySet:
        """
        Get the Steam IDs of the squad members who participated in the session.
        """
        return self.squad.memberships.filter(
            player__steamid__in = self.participated_steamids
        ).values_list('player__steamid', flat = True)

    @property
    def participated_squad_members(self):
        """
        Get the squad members who participated in the session.
        """
        return SteamProfile.objects.filter(
            steamid__in = self.participated_squad_members_steamids,
            matchparticipation__pmatch__in = self.matches.values_list('pk', flat = True),
        ).values(
            'steamid',
            'name',
            *[f'avatar_{c}' for c in 'sml'],
        ).annotate(
            avg_adr = Avg('matchparticipation__adr'),
        ).order_by(
            '-avg_adr',
        )

    @property
    def first_match(self) -> Optional['Match']:
        """
        Get the first match of the session, or `None` if the session has no matches.
        """
        if not self.matches.exists():
            return None
        return self.matches.earliest('timestamp')

    @property
    def last_match(self) -> Optional['Match']:
        """
        Get the last match of the session, or `None` if the session has no matches.
        """
        if not self.matches.exists():
            return None
        return self.matches.latest('timestamp')

    @property
    def started(self) -> Optional[int]:
        """
        The CSGO timestamp of the first match of the session, or `None` if the session has no matches.
        """
        return None if self.first_match is None else self.first_match.timestamp

    @property
    def ended(self) -> Optional[int]:
        """
        The CSGO timestamp of the last match of the session plus the duration of the match (in seconds), or `None` if
        the session has no matches.
        """
        return None if self.last_match is None else self.last_match.ended_timestamp

    @property
    def started_date_and_time(self) -> str:
        """
        Get the human-readable date and time of the start of the session.
        """
        return '-' if self.first_match is None else self.first_match.date_and_time

    @property
    def started_date(self) -> str:
        """
        Get the human-readable date of the start of the session.
        """
        return '-' if self.first_match is None else self.first_match.date

    @property
    def started_time(self) -> str:
        """
        Get the human-readable time of the start of the session.
        """
        return '-' if self.first_match is None else self.first_match.time

    @property
    def ended_date_and_time(self) -> str:
        """
        Get the human-readable date and time of the end of the session.
        """
        return '-' if self.last_match is None else self.last_match.ended_date_and_time

    @property
    def ended_time(self) -> str:
        """
        Get the human-readable time of the end of the session.
        """
        return '-' if self.last_match is None else self.last_match.ended_time

    @property
    def started_weekday(self) -> str:
        """
        Get the human-readable weekday of the start of the session.
        """
        return '-' if self.first_match is None else self.first_match.weekday

    @property
    def started_weekday_short(self) -> str:
        """
        Get the human-readable abbreviation of the weekday of the start of the session.
        """
        return '-' if self.first_match is None else self.first_match.weekday_short

    def __str__(self) -> str:
        """
        Get the string representation of the gaming session.
        """
        try:
            if self.matches.all().exists():
                return f'{self.started_date_and_time} — {self.ended_date_and_time} ({self.pk})'
        except:  # noqa: E722
            pass
        return f'Empty Gaming Session ({self.pk})'


def get_match_result(team_idx: int, team_scores: Tuple[int, int]) -> Literal['w', 'l', 't']:
    """
    Get the result of a match for a given team.

    Arguments:
        team_idx: The index of the team for which to get the result (0 or 1).
        team_scores: The scores of the two teams in the match.

    Returns:
        The result is either a win ('w'), a loss ('l'), or a tie ('t').
    """
    assert 0 <= team_idx < 2, f'Invalid team index: {team_idx}'
    own_team_score = team_scores[ team_idx]
    opp_team_score = team_scores[(team_idx + 1) % 2]
    if own_team_score < opp_team_score:
        return 'l'
    if own_team_score > opp_team_score:
        return 'w'
    return 't'


class Match(models.Model):
    """
    A match that has been played and finished.
    """

    sharecode = models.CharField(blank = False, max_length = 50)
    """
    The share code of the match.
    """

    timestamp = models.PositiveBigIntegerField()
    """
    The CSGO timestamp of the match.
    """

    score_team1 = models.PositiveSmallIntegerField()
    """
    The score of team 1 (first five players) in the match.
    """

    score_team2 = models.PositiveSmallIntegerField()
    """
    The score of team 2 (last five players) in the match.
    """

    duration = models.PositiveSmallIntegerField()
    """
    The duration of the match in seconds.
    """

    map_name = models.SlugField()
    """
    The name of the map on which the match was played.
    """

    sessions = models.ManyToManyField(GamingSession, related_name = 'matches', blank = True)
    """
    The gaming sessions in which the match was played.
    """

    MTYPE_COMPETITIVE = 'Competitive'
    MTYPE_WINGMAN = 'Wingman'
    MTYPE_DANGER_ZONE = 'Danger Zone'
    MTYPE_PREMIER = 'Premier'

    mtype = models.CharField(
        blank = True,
        max_length = 20,
        verbose_name = 'Match type',
        choices = [
            ('', 'Unknown'),
            (MTYPE_COMPETITIVE, 'Competitive'),
            (MTYPE_WINGMAN, 'Wingman'),
            (MTYPE_DANGER_ZONE, 'Danger Zone'),
            (MTYPE_PREMIER, 'Premier'),
        ],
    )
    """
    The type of the match. This is either MTYPE_COMPETITIVE, MTYPE_WINGMAN, MTYPE_DANGER_ZONE, MTYPE_PREMIER, or empty
    if the type of the match is unknown.
    """

    class Meta:

        verbose_name_plural = 'Matches'
        """
        The plural name of the model (this is how it appears in the admin console).
        """

        constraints = [
            models.UniqueConstraint(
                fields = ['sharecode', 'timestamp'], name = 'unique_sharecode_timestamp',
            )
        ]
        """
        The combination of the share code and the timestamp must be unique.
        """

    @staticmethod
    def from_summary(data: dict) -> Self:
        """
        Get a :class:`Match` object corresponding to the given data.

        The following data must be supplied via the `data` dictionary:

        - `sharecode`: The share code of the match.
        - `timestamp`: The CSGO timestamp of the match.
        - `steam_ids`: List of the Steam IDs of the participated players. The first five players are in team 1, and the
          last five players are in team 2.
        - `summary`: The summary of the match, that is an object with the following attributes:
            - `map`: The URL of the demo file of the match.
            - `team_scores`: Tuple of the scores of the two teams.
            - `match_duration`: The duration of the match in seconds.
            - `enemy_kills`: List of the number of enemy kills for each player.
            - `enemy_headshots`: List of the number of enemy headshots for each player.
            - `assists`: List of the number of assists for each player.
            - `deaths`: List of the number of deaths for each player.
            - `scores`: List of the scores for each player.
            - `mvps`: List of the number of MVPs for each player.

        The values for `enemy_kills`, `enemy_headshots`, `assists`, `deaths`, `scores`, `mvps` must be given in the same
        order as the `steam_ids`.

        Returns:
            If a match with the same share code and timestamp already exists, then the corresponding object is returned.
            Otherwise, a new :class:`Match` object is created from the given data and returned.
        """
        existing_matches = Match.objects.filter(sharecode = data['sharecode'], timestamp = data['timestamp'])
        if len(existing_matches) != 0:
            return existing_matches.get()

        # Fetch the match details (download and parse the demo file)
        import cs2_client
        cs2_client.fetch_match_details(data)

        with transaction.atomic():
            m = Match()
            m.sharecode = data['sharecode']
            m.timestamp = data['timestamp']
            m.score_team1 = data['summary']['team_scores'][0]
            m.score_team2 = data['summary']['team_scores'][1]
            m.duration = data['summary']['match_duration']
            m.map_name = data['map']
            m.mtype = data['type']
            m.save()

            slices = [
                data['steam_ids'],
                data['summary']['enemy_kills'],
                data['summary']['assists'],
                data['summary']['deaths'],
                data['summary']['scores'],
                data['summary']['mvps'],
                data['summary']['enemy_headshots'],
            ]
            players = list()
            for pos, (steamid, kills, assists, deaths, score, mvps, headshots) in enumerate(zip(*slices)):

                steam_profiles = SteamProfile.objects.filter(steamid = steamid)
                if len(steam_profiles) == 0:
                    steam_profile = SteamProfile.objects.create(steamid = steamid)
                else:
                    steam_profile = steam_profiles[0]
                    steam_profile.save()  # Updates data from Steam API

                players.append(steam_profile)

                mp = MatchParticipation(player = steam_profile, pmatch = m)
                mp.team      = 1 + pos // 5
                mp.result    = get_match_result(mp.team - 1, (m.score_team1, m.score_team2))
                mp.kills     = kills
                mp.assists   = assists
                mp.deaths    = deaths
                mp.score     = score
                mp.mvps      = mvps
                mp.headshots = headshots
                mp.adr       = float(data['adr'][str(steam_profile.steamid)] or 0)
                mp.old_rank  = data['ranks'][str(steam_profile.steamid)]['old']
                mp.new_rank  = data['ranks'][str(steam_profile.steamid)]['new']
                mp.save()

            for kill_data in data['kills'].to_dict(orient='records'):

                if any(
                    (
                        kill_data['attacker_team_name'] == kill_data['victim_team_name'],
                        kill_data['attacker_steamid'] == 'None',
                    ),
                ):
                    continue

                kev = KillEvent()
                kev.killer = MatchParticipation.objects.filter(pmatch = m, player = kill_data['attacker_steamid']).get()
                kev.victim = MatchParticipation.objects.filter(pmatch = m, player = kill_data[  'victim_steamid']).get()
                kev.killer_x = kill_data['attacker_X']
                kev.killer_y = kill_data['attacker_Y']
                kev.killer_z = kill_data['attacker_Z']
                kev.victim_x = kill_data['victim_X']
                kev.victim_y = kill_data['victim_Y']
                kev.victim_z = kill_data['victim_Z']
                kev.round    = kill_data['round']
                kev.kill_type = 1 if kill_data['attacker_team_name'] == 'TERRORIST' else 2
                kev.bomb_planted = kill_data['is_bomb_planted']
                kev.weapon = kill_data['weapon']
                kev.save()

            squad_ids = set()
            for player in players:
                account = getattr(player, 'account', None)
                if account is None:
                    continue
                for membership in account.steam_profile.squad_memberships.all():
                    squad_ids.add(membership.squad.pk)
            for squad_id in squad_ids:
                squad = Squad.objects.get(uuid = squad_id)
                squad.handle_new_match(m)

            m.award_badges()
            return m

    def award_badges(self, mute_discord = False):
        """
        Award the badges for all who participated in this match.

        This does not include badges which require the previous match history.
        """
        for mp in self.matchparticipation_set.all():
            MatchBadge.award(mp, mute_discord = mute_discord)

    def __str__(self):
        return f'{self.map_name} ({self.date_and_time})'

    @property
    def rounds(self):
        return self.score_team1 + self.score_team2

    @property
    def ended_timestamp(self):
        return self.timestamp + self.duration

    @property
    def date_and_time(self) -> str:
        """
        Get the human-readable date and time of the start of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp)

    @property
    def ended_date_and_time(self) -> str:
        """
        Get the human-readable date and time of the end of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp + self.duration)

    @property
    def time(self) -> str:
        """
        Get the human-readable time of the start of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp, fmt = r'%H:%M')

    @property
    def ended_time(self) -> str:
        """
        Get the human-readable time of the end of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp + self.duration, fmt = r'%H:%M')

    @property
    def date(self) -> str:
        """
        Get the human-readable date of the start of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp, fmt = r'%b %-d, %Y')

    @property
    def weekday(self) -> str:
        """
        Get the human-readable weekday of the start of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp, fmt = r'%A')

    @property
    def weekday_short(self) -> str:
        """
        Get the human-readable abbreviation of the weekday of the start of the match.
        """
        return csgo_timestamp_to_strftime(self.timestamp, fmt = r'%a')

    def get_participation(self, player):
        if isinstance(player, str):
            return self.matchparticipation_set.get(player__steamid = player)
        else:
            return self.matchparticipation_set.get(player = player)

    def get_session(self, squad):
        return get_or_none(self.sessions, squad__pk = squad.pk)


m2m_changed.connect(GamingSession.sessions_changed, sender=Match.sessions.through)


class MatchParticipation(models.Model):

    player = models.ForeignKey(SteamProfile, on_delete = models.PROTECT, verbose_name = 'Player')
    """
    The player who participated in the match.
    """

    pmatch = models.ForeignKey(Match, on_delete = models.CASCADE, verbose_name = 'Match')
    """
    The match in which the player participated.
    """

    team = models.PositiveSmallIntegerField()
    """
    The team in which the player participated (must be either 1 or 2).
    """

    result = models.CharField(blank = False, max_length = 1)
    """
    The result of the match for the player. Must be either 'w' (win), 'l' (loss), or 't' (tie).
    """

    kills = models.PositiveSmallIntegerField()
    """
    The number of enemy kills the player scored in the match.
    """

    assists = models.PositiveSmallIntegerField()
    """
    The number of assists the player scored in the match.
    """

    deaths = models.PositiveSmallIntegerField()
    """
    The number of deaths the player had in the match.
    """

    score = models.PositiveSmallIntegerField()
    """
    The score of the player in the match.
    """

    mvps = models.PositiveSmallIntegerField()
    """
    The number of MVPs the player scored in the match.
    """

    headshots = models.PositiveSmallIntegerField()
    """
    The number of headshots on enemies the player scored in the match.
    """

    adr = models.FloatField()
    """
    The average damage per round the player scored in the match.
    """

    old_rank = models.IntegerField(null = True, blank = True)
    """
    The rank of the player before the match (None if unranked).
    """

    new_rank = models.IntegerField(null = True, blank = True)
    """
    The rank of the player after the match (None if unranked).
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['player', 'pmatch'], name = 'unique_player_pmatch'
            ),
            models.CheckConstraint(
                check = ~models.Q(old_rank = 0), name = 'old_rank_not_zero'
            ),
            models.CheckConstraint(
                check = ~models.Q(new_rank = 0), name = 'new_rank_not_zero'
            ),
        ]
        ordering = ['-adr']

    def clean(self, *args, **kwargs):
        if self.team not in (1, 2):
            raise ValueError('Team must be 1 or 2')
        if self.result not in ('w', 'l', 't'):
            raise ValueError('Result must be "w", "l", or "t"')
        super().clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def kd(self):
        return self.kills / max((1, self.deaths))

    def streaks(self, n):
        """
        Count the number of streaks of length n.

        A streak of length n is a round played where the player scored n kills.
        """
        rounds = np.zeros(100, int)
        for kev in self.kill_events.all():
            if kev.round is None:
                continue
            rounds[kev.round] += 1
        return (rounds == n).sum()

    @staticmethod
    def filter(qs, period):
        return qs if period is None else qs.filter(**period.filters())


def get_or_none(qs, **kwargs):
    try:
        return qs.get(**kwargs)
    except ObjectDoesNotExist:
        return None
    except MultipleObjectsReturned:
        raise


class KillEvent(models.Model):
    """
    A kill event in a match.
    """

    killer = models.ForeignKey(MatchParticipation, related_name =  'kill_events', on_delete = models.CASCADE)
    """
    The player who scored the kill.
    """

    victim = models.ForeignKey(MatchParticipation, related_name = 'death_events', on_delete = models.CASCADE)
    """
    The player who was killed.
    """

    round = models.PositiveSmallIntegerField(null = True, blank = True)
    """
    The round number in which the kill occurred.
    """

    kill_type = models.PositiveSmallIntegerField()
    """
    The type of the kill. Must be either 1 (T kills CT) or 2 (CT kills T).
    """

    bomb_planted = models.BooleanField(null = False)
    """
    Whether the bomb was already planted when the kill occurred.
    """

    weapon = models.CharField(max_length = 50, blank = True)
    """
    The weapon used to score the kill.
    """

    killer_x = models.FloatField()
    killer_y = models.FloatField()
    killer_z = models.FloatField()

    victim_x = models.FloatField()
    victim_y = models.FloatField()
    victim_z = models.FloatField()


class PlayerOfTheWeek(models.Model):
    """
    The outcome of a weekly challenge.
    """

    timestamp = models.PositiveBigIntegerField()
    """
    The CSGO timestamp of when the challenge ended or will end.
    """

    player1 = models.ForeignKey(
        SteamProfile,
        null = True ,
        on_delete = models.SET_NULL,
        blank = True,
        related_name = 'potw1',
    )
    """
    The player who won the first place.
    """

    player2 = models.ForeignKey(
        SteamProfile,
        null = True ,
        on_delete = models.SET_NULL,
        blank = True,
        related_name = 'potw2',
    )
    """
    The player who won the second place.
    """

    player3 = models.ForeignKey(
        SteamProfile,
        null = True ,
        on_delete = models.SET_NULL,
        blank = True,
        related_name = 'potw3',
    )
    """
    The player who won the third place.
    """

    squad = models.ForeignKey(Squad, null = False, on_delete = models.CASCADE)
    """
    The squad that this weekly challenge is or was for.
    """

    mode = models.CharField(blank = False, max_length = 20)
    """
    The mode of the challenge.
    """

    @property
    def challenge_start_timestamp(self) -> int:
        """
        Get the CSGO timestamp of the start of the challenge.
        """
        date = datetime.fromtimestamp(self.timestamp)
        return round(datetime.timestamp(date - timedelta(days = 7)))

    @property
    def challenge_end_timestamp(self) -> int:
        """
        Get the CSGO timestamp of the end of the challenge.
        """
        return self.timestamp

    @property
    def challenge_start_datetime(self) -> datetime:
        """
        Get the datetime object of the start of the challenge.
        """
        return csgo_timestamp_to_datetime(self.challenge_start_timestamp)

    @property
    def challenge_end_datetime(self) -> datetime:
        """
        Get the datetime object of the end of the challenge.
        """
        return csgo_timestamp_to_datetime(self.challenge_end_timestamp)

    @property
    def challenge_end_date_and_time(self) -> str:
        """
        Get the human-readable date and time of the end of the challenge.
        """
        return csgo_timestamp_to_strftime(self.challenge_end_timestamp)

    @property
    def week(self) -> int:
        """
        Get the week number of the challenge.
        """
        return self.challenge_end_datetime.isocalendar()[1]

    @property
    def year(self) -> int:
        """
        Get the year of the challenge.
        """
        return self.challenge_end_datetime.year

    @staticmethod
    def create_prehistoric_badge(squad):
        prehistoric_match = squad.matches().earliest('timestamp')
        prehistoric_match_date = datetime.fromtimestamp(prehistoric_match.timestamp)
        prehistoric_badge_date = prehistoric_match_date + timedelta(days = -prehistoric_match_date.weekday())
        prehistoric_badge_date = prehistoric_badge_date.replace(hour=4, minute=0)
        prehistoric_timestamp  = round(datetime.timestamp(prehistoric_badge_date))
        prehistoric_badge = PlayerOfTheWeek(
            timestamp = prehistoric_timestamp,
            squad = squad,
            mode = potw.mode_cycle[-1].id,
        )
        return prehistoric_badge

    @staticmethod
    def get_latest_badge(squad):
        badges = PlayerOfTheWeek.objects.filter(squad = squad)
        if len(badges) == 0:
            return PlayerOfTheWeek.create_prehistoric_badge(squad)
        else:
            return badges.latest('timestamp')

    @staticmethod
    def get_next_badge_data(squad, force_mode = None):
        prev_badge = PlayerOfTheWeek.get_latest_badge(squad)
        prev_date  = datetime.fromtimestamp(prev_badge.timestamp)
        mode = potw.get_next_mode(prev_badge.mode) if force_mode is None else potw.get_mode_by_id(force_mode)
        next_timestamp = round(datetime.timestamp(prev_date + timedelta(days = 7)))
        player_stats   = dict()
        match_participations = squad.match_participations(
            pmatch__timestamp__gt  = prev_badge.timestamp,
            pmatch__timestamp__lte = next_timestamp)

        # Accumulate stats
        stat_fields = {'score'}
        for mp in match_participations:
            if mp.player.steamid not in player_stats:
                player_stats[mp.player.steamid] = dict(wins = 0)
            mode.accumulate(player_stats[mp.player.steamid], mp)
            stat_fields |= frozenset(player_stats[mp.player.steamid].keys()) - frozenset(['wins'])
            if mp.result == 'w':
                player_stats[mp.player.steamid]['wins'] += 1

        # Aggregate stats
        for steamid in player_stats:
            player_stats[steamid]['score'] = mode.aggregate(player_stats[steamid])

        top_steamids = sorted(player_stats.keys(), key=lambda steamid: player_stats[steamid]['score'], reverse=True)
        result = {
            'timestamp':   next_timestamp,
            'squad':       squad,
            'leaderboard': list(),
        }
        if len(top_steamids) < 2:
            result['unfulfilled_requirement'] = 'Will not be awarded unless at least two players participate.'
        else:
            next_place = 1
            for steamid in top_steamids:
                player_data = dict(
                    player = SteamProfile.objects.get(pk = steamid),
                ) | {
                    field: player_stats[steamid][field]
                    for field in stat_fields
                }
                fail_requirements = mode.does_fail_requirements(player_stats[steamid])
                if fail_requirements is not None:
                    player_data['place_candidate'] = None
                    player_data['unfulfilled_requirement'] = str(fail_requirements)
                elif next_place <= 3 and len(top_steamids) > next_place:
                    player_data['place_candidate'] = next_place
                    next_place += 1
                else:
                    player_data['place_candidate'] = None
                result['leaderboard'].append(player_data)
        draft_badge = PlayerOfTheWeek(timestamp = result['timestamp'], squad = squad, mode = mode.id)
        result['challenge_end'] = draft_badge.challenge_end_date_and_time
        result['week'] = draft_badge.week - 1
        result['year'] = draft_badge.year
        result['mode'] = draft_badge.mode
        return result

    @staticmethod
    def create_badge(badge_data):
        if (
            datetime.timestamp(csgo_timestamp_to_datetime(badge_data['timestamp']))
            >
            datetime.timestamp(datetime.now())
        ):
            return None
        badge = PlayerOfTheWeek(
            timestamp = badge_data['timestamp'],
            squad = badge_data['squad'],
            mode = badge_data['mode'],
        )
        for player_data in badge_data['leaderboard']:
            match player_data['place_candidate']:
                case 1:
                    badge.player1 = player_data['player']
                case 2:
                    badge.player2 = player_data['player']
                case 3:
                    badge.player3 = player_data['player']
        badge.save()
        mode = potw.get_mode_by_id(badge.mode)
        text = (
            f'Attention now, the results of the *{mode.name}* are in! '
            f'🥇 <{badge.player1.steamid}> is the **Player of the Week {badge.week}/{badge.year}**!'
        )
        if badge.player2 is not None:
            if badge.player3 is None:
                text = f'{text} Second place goes to 🥈 <{badge.player2.steamid}>.'
            else:
                text = (
                    f'{text} Second and third places go to 🥈 <{badge.player2.steamid}> '
                    f'and 🥉 <{badge.player3.steamid}>, respectively.'
                )
        badge_data['squad'].notify_on_discord(text)
        return badge

    @staticmethod
    def create_missing_badges(squad=None):
        if squad is None:
            for squad in Squad.objects.all():
                PlayerOfTheWeek.create_missing_badges(squad)
        else:
            try:
                while True:
                    next_badge_data = PlayerOfTheWeek.get_next_badge_data(squad)
                    next_badge = PlayerOfTheWeek.create_badge(next_badge_data)
                    if next_badge is None:
                        break
            except Match.DoesNotExist:
                log.error(f'Failed to create missing badges.', exc_info=True)

    class Meta:
        verbose_name        = 'Player-of-the-Week badge'
        verbose_name_plural = 'Player-of-the-Week badges'

    def __str__(self):
        return f'{self.week}/{self.year}'


class MatchBadgeType(models.Model):

    slug = models.SlugField(primary_key = True)
    name = models.CharField(max_length = 100, unique = True)

    class Meta:
        verbose_name        = 'Match-based badge type'
        verbose_name_plural = 'Match-based badge types'


class MatchBadge(models.Model):

    participation = models.ForeignKey(MatchParticipation, related_name = 'badges', on_delete = models.PROTECT)
    badge_type    = models.ForeignKey(MatchBadgeType, related_name = 'badges', on_delete = models.PROTECT)
    frequency     = models.PositiveSmallIntegerField(null = False, default = 1)

    @staticmethod
    def award(participation, **kwargs):
        MatchBadge.award_kills_in_one_round_badges(participation, 5, 'ace', **kwargs)
        MatchBadge.award_kills_in_one_round_badges(participation, 4, 'quad-kill', **kwargs)
        MatchBadge.award_margin_badge(participation, 'carrier', order = '-adr', margin = 1.8, emoji = '🍆', **kwargs)
        MatchBadge.award_margin_badge(
            participation, 'peach', order = 'adr', margin = 0.67, emoji = '🍑', max_adr = 50, max_kd = 0.5, **kwargs,
        )
        MatchBadge.award_weapon_badge(participation, 'knife', emoji = '🔪', **kwargs)

    @staticmethod
    def award_with_history(participation, old_participations):
        if len(old_participations) >= 10:
            MatchBadge.award_surpass_yourself_badge(participation, old_participations[-20:])

    @staticmethod
    def award_surpass_yourself_badge(participation, old_participations):
        badge_type = MatchBadgeType.objects.get(slug = 'surpass-yourself')
        if MatchBadge.objects.filter(badge_type = badge_type, participation=participation).exists():
            return
        kd_series = [mp.kd for mp in old_participations]
        kd_mean = np.mean(kd_series)
        kd_std  = np.std (kd_series)
        threshold = kd_mean + 2 * kd_std
        if participation.kd > threshold:
            log.info(
                f'Surpass-yourself badge awarded to {participation.player.name} '
                f'for K/D {participation.kd} where threshold was {threshold}'
            )
            MatchBadge.objects.create(badge_type=badge_type, participation=participation)
            text = (
                f'🎖️ <{participation.player.steamid}> has been awarded the **Surpass-yourself Badge** in recognition '
                f'of their far-above average performance on *{participation.pmatch.map_name}* recently!'
            )
            for m in participation.player.squad_memberships.all():
                m.squad.notify_on_discord(text)

    @staticmethod
    def award_kills_in_one_round_badges(participation, kill_number, badge_type_slug, mute_discord = False):
        badge_type = MatchBadgeType.objects.get(slug = badge_type_slug)
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists():
            return
        number = participation.streaks(n = kill_number)
        if number > 0:
            log.info(f'{participation.player.name} achieved {badge_type.name} {number} time(s)')
            MatchBadge.objects.create(badge_type = badge_type, participation = participation, frequency = number)
            frequency = '' if number == 1 else f' {number} times'
            text = (
                f'<{participation.player.steamid}> has achieved **{badge_type.name}**{frequency} on '
                f'*{participation.pmatch.map_name}* recently!'
            )
            if not mute_discord:
                for m in participation.player.squad_memberships.all():
                    m.squad.notify_on_discord(text)

    @staticmethod
    def award_margin_badge(participation, badge_type_slug, order, margin, emoji, mute_discord = False, **bounds):
        kpi = order[1:] if order[0] in '+-' else order
        badge_type = MatchBadgeType.objects.get(slug = badge_type_slug)
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists():
            return
        teammates = participation.pmatch.matchparticipation_set.filter(team = participation.team).order_by(order)

        # Define the requirements for the badge
        requirements = [
            teammates[0].pk == participation.pk,
            any(
                (
                    order[0] == '-' and getattr(teammates[0], kpi) > margin * getattr(teammates[1], kpi),
                    order[0] != '-' and getattr(teammates[0], kpi) < margin * getattr(teammates[1], kpi),
                )
            ),
        ]

        # Add the bound checks to the requirements
        req_bounds = list()
        for bound_key, bound_val in bounds.items():
            func_name, attr_name = bound_key.split('_')
            attr = getattr(participation, attr_name)
            match func_name:
                case 'min':
                    req_bounds.append(attr >= bound_val)
                case 'max':
                    req_bounds.append(attr <= bound_val)
                case _:
                    raise ValueError(f'Invalid function name: "{func_name}"')
        if req_bounds:
            requirements.append(any(req_bounds))

        # Check the requirements and award the badge
        if all(requirements):
            log.info(f'{participation.player.name} received the {badge_type.name}')
            MatchBadge.objects.create(badge_type = badge_type, participation = participation)
            text = (
                f'{emoji} <{participation.player.steamid}> has qualified for the **{badge_type.name}** '
                f'on *{participation.pmatch.map_name}*!'
            )
            if not mute_discord:
                for m in participation.player.squad_memberships.all():
                    m.squad.notify_on_discord(text)

    @staticmethod
    def award_weapon_badge(participation, weapon, emoji, mute_discord = False):
        badge_type = MatchBadgeType.objects.get(slug = f'weapon-{weapon}')
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists():
            return
        number = participation.kill_events.filter(weapon = weapon).count()
        if number > 0:
            log.info(f'{participation.player.name} achieved {badge_type.name} {number} time(s)')
            MatchBadge.objects.create(badge_type = badge_type, participation = participation, frequency = number)
            frequency = '' if number == 1 else f' {number} times'
            text = (
                f'{emoji} <{participation.player.steamid}> had **{badge_type.name}**{frequency} on '
                f'*{participation.pmatch.map_name}*!'
            )
            if not mute_discord:
                for m in participation.player.squad_memberships.all():
                    m.squad.notify_on_discord(text)

    class Meta:
        verbose_name        = 'Match-based badge'
        verbose_name_plural = 'Match-based badges'

        constraints = [
            models.UniqueConstraint(
                fields = ['participation', 'badge_type'], name = 'unique_participation_badge_type',
            )
        ]

    def __str__(self):
        return (
            f'{self.frequency}x '
            f'{self.badge_type.name} for {self.participation.player.name} '
            f'({self.participation.player.steamid})'
        )

    def __eq__(self, other):
        return (
            isinstance(other, MatchBadge)
            and self.participation.pk == other.participation.pk
            and self.badge_type.pk == other.badge_type.pk
        )

    def __hash__(self):
        return hash(
            (
                self.participation.pk,
                self.badge_type.pk,
                self.frequency,
            )
        )


class UpdateTask(models.Model):
    """
    A task that fetches new matches for an account and triggers all subsequent updates.
    """

    account = models.ForeignKey(Account, related_name = 'update_tasks', on_delete = models.CASCADE)
    """
    The account for which to fetch new matches.
    """

    scheduling_timestamp = models.PositiveBigIntegerField(verbose_name = 'Scheduled')
    """
    The timestamp when the task was scheduled.
    """

    execution_timestamp = models.PositiveBigIntegerField(
        null = True,
        blank = True,
        verbose_name = 'Execution started',
    )
    """
    The timestamp when the task started executing.
    """

    completion_timestamp = models.PositiveBigIntegerField(
        null = True,
        blank = True,
        verbose_name = 'Completed',
    )
    """
    The timestamp when the task completed.
    """

    @property
    def scheduling_datetime(self) -> datetime:
        """
        Get the datetime object of when the task was scheduled.
        """
        return datetime.fromtimestamp(self.scheduling_timestamp)

    @property
    def execution_datetime(self) -> Optional[datetime]:
        """
        Get the datetime object of when the task started executing.
        """
        if self.execution_timestamp is None:
            return None
        else:
            return datetime.fromtimestamp(self.execution_timestamp)

    @property
    def completion_datetime(self) -> Optional[datetime]:
        """
        Get the datetime object of when the task completed.
        """
        if self.completion_timestamp is None:
            return None
        else:
            return datetime.fromtimestamp(self.completion_timestamp)

    @property
    def scheduling_date_and_time(self) -> str:
        """
        Get the human-readable date and time of when the task was scheduled.
        """
        return self.scheduling_datetime.strftime(r'%b %-d, %Y, %H:%M')

    @property
    def execution_date_and_time(self) -> Optional[str]:
        """
        Get the human-readable date and time of when the task started executing.
        """
        if self.execution_datetime is None:
            return None
        else:
            return self.execution_datetime.strftime(r'%b %-d, %Y, %H:%M')

    @property
    def completion_date_and_time(self) -> Optional[str]:
        """
        Get the human-readable date and time of when the task completed.
        """
        if self.completion_datetime is None:
            return None
        else:
            return self.completion_datetime.strftime(r'%b %-d, %Y, %H:%M')

    @property
    def is_completed(self) -> bool:
        """
        Check if the task has been completed
        """
        return self.completion_timestamp is not None

    def run(self, recent_matches: list[Match]):
        import cs2_client

        self.execution_timestamp = datetime.timestamp(datetime.now())
        self.save()

        if self.account.enabled and settings.CSGO_API_ENABLED:
            try:

                # Determine the first sharecode to fetch the match for
                first_sharecode = self.account.sharecode

                # Determine if this is the inital update for the account
                is_initial_update = (len(self.account.last_sharecode) == 0)

                new_match_data: list[dict | Match] = cs2_client.fetch_matches(
                    first_sharecode,
                    cs2_client.SteamAPIUser(self.account.steamid, self.account.steam_auth),
                    list(recent_matches),

                    # Only process the match for `first_sharecode` if this is the inital update for the account
                    skip_first = not is_initial_update,
                )

                for match_data in new_match_data:
                    if isinstance(match_data, dict):
                        pmatch: Match = Match.from_summary(match_data)
                        recent_matches.append(pmatch)
                    else:
                        pmatch: Match = match_data

                    self.account.last_sharecode = pmatch.sharecode
                    self.account.save()

                    participation = pmatch.get_participation(self.account.steam_profile)
                    old_participations = list(
                        self.account.match_participations().order_by('pmatch__timestamp').filter(
                            pmatch__timestamp__lt = pmatch.timestamp,
                        )
                    )
                    MatchBadge.award_with_history(participation, list(old_participations))

            except cs2_client.InvalidSharecodeError:
                self.account.enabled = False
                self.account.save()

        self.completion_timestamp = datetime.timestamp(datetime.now())
        self.save()

        self.account.handle_finished_update()

        kept_tasks = UpdateTask.objects.order_by('-scheduling_timestamp')[:100]
        UpdateTask.objects.exclude(pk__in = kept_tasks.values_list('pk', flat = True)).delete()
