from datetime import datetime
from dateutil import tz

from django.db import models, transaction
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models.signals import m2m_changed
from django.db.models import Avg, Count, F

from accounts.models import SteamProfile, Account, Squad
from api import NAV_SUPPORTED_MAPS, api, fetch_match_details, SteamAPIUser, InvalidSharecodeError
from discordbot.models import ScheduledNotification
from .features import Features, FeatureContext
from . import potw

import awpy.data
import numpy as np
import logging

from datetime import datetime, timedelta


log = logging.getLogger(__name__)


def csgo_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp)


def csgo_timestamp_to_datetime(timestamp, fmt='%-d %b %Y %H:%M'):
    return csgo_timestamp(timestamp).strftime(fmt)


class GamingSession(models.Model):

    squad       = models.ForeignKey(Squad, related_name='sessions', on_delete=models.CASCADE)
    is_closed   = models.BooleanField(default=False)
    rising_star = models.ForeignKey(SteamProfile, on_delete=models.CASCADE, null=True, blank=True)

    def close(self):
        was_already_closed = self.is_closed
        self.is_closed = True
        self.save()
        if was_already_closed: return

        # Compute the performance of the players
        participated_steamids = self.participated_steamids
        comments = list()
        top_player, top_player_trend_rel = None, 0
        participated_squad_members = 0
        for player in self.squad.members.all():
            if player.steamid not in participated_steamids: continue
            participated_squad_members += 1
            pv_today = Features.pv(FeatureContext.create_default(player, trend_shift = 0, days = 0.5))['value']
            pv_ref   = Features.pv(FeatureContext.create_default(player, trend_shift = 0))['value']
            if pv_today is None or pv_ref is None: continue
            pv_trend = pv_today - pv_ref
            kpi = dict(value = pv_today, trend_rel = 0 if pv_trend == 0 else (pv_trend / pv_ref if pv_ref > 0 else np.infty))
            if top_player is None or kpi['trend_rel'] > top_player_trend_rel:
                top_player = player
                top_player_trend_rel = kpi['trend_rel']
            if abs(kpi['trend_rel']) > 0.0005:
                icon = '📈' if kpi['trend_rel'] > 0 else '📉'
                comments.append(f' <{player.steamid}> {icon} {100 * kpi["trend_rel"]:+.1f}% ({kpi["value"]:.2f})')
            else:
                comments.append(f' <{player.steamid}> ±0.00% ({kpi["value"]:.2f})')
        text = 'Looks like your session has ended!'
        if len(comments) > 0:
            text += ' Here is your current performance compared to your 30-days average: ' + ', '.join(comments)
            text += ', with respect to the *player value*.'
        ScheduledNotification.objects.create(squad = self.squad, text = text)

        # Create a summary of the matches
        text = 'Matches played in this session:'
        for pmatch in self.matches.filter(
            matchparticipation__player__in = self.squad.members.all()
        ).distinct().order_by('timestamp').annotate(
            result = F('matchparticipation__result')
        ):
            text += f'\n- *{pmatch.map_name}*, **{pmatch.score_team1}:{pmatch.score_team2}**, '
            text += dict(
                w = 'won 🤘',
                l = 'lost 💩',
                t = 'ended in a draw 🥵',
            )[pmatch.result]
        ScheduledNotification.objects.create(squad = self.squad, text = text)

        # Determine the rising star
        if participated_squad_members > 1 and top_player is not None and top_player_trend_rel > 0.01:
            from .plots import trends as plot_trends
            notification = ScheduledNotification.objects.create(squad = self.squad, text = f'And today\'s **rising star** was: 🌟 <{top_player.steamid}>!')
            plot = plot_trends(self.squad, top_player, Features.MANY)
            notification.attach(plot)
            self.rising_star = top_player
            self.save()

    @staticmethod
    def sessions_changed(sender, action, pk_set, instance, **kwargs):
        if action == 'pre_add':
            added_sessions = [GamingSession.objects.get(pk = session_pk) for session_pk in pk_set]
            for session in added_sessions:
                if session.is_closed: continue
                if GamingSession.objects.filter(squad = session.squad, is_closed = True, matches__timestamp__gt = instance.timestamp_end).exists():
                    log.info(f'Setting session {session.pk} added to match {instance.pk} (str(instance)) to closed since a new closed session of the same squad exists')
                    session.is_closed = True
                    session.save() 

    @property
    def participated_steamids(self):
        steamids = set()
        for pmatch in self.matches.all():
            for mp in pmatch.matchparticipation_set.all():
                steamids.add(mp.player.steamid)
        return steamids

    @property
    def participants(self):
        return [SteamProfile.objects.get(steamid = steamid) for steamid in self.participated_steamids]

    @property
    def participated_squad_members(self):
        return self.squad.members.filter(steamid__in = self.participated_steamids, matchparticipation__pmatch__in = self.matches.values_list('pk', flat = True)) \
            .values('steamid', 'name', *[f'avatar_{c}' for c in 'sml']).annotate(avg_position = Avg('matchparticipation__position')) \
            .order_by('avg_position')

    @property
    def first_match(self):
        if not self.matches.exists(): return None
        return self.matches.earliest('timestamp')

    @property
    def last_match(self):
        if not self.matches.exists(): return None
        return self.matches.latest('timestamp')

    @property
    def started(self):
        return None if self.first_match is None else self.first_match.timestamp

    @property
    def ended(self):
        return None if self.last_match is None else self.last_match.timestamp + self.last_match.duration

    @property
    def started_datetime(self):
        return '–' if self.started is None else datetime.fromtimestamp(self.started).strftime('%-d %b %Y %H:%M')

    @property
    def started_date(self):
        return '–' if self.started is None else datetime.fromtimestamp(self.started).strftime('%-d %b %Y')

    @property
    def started_time(self):
        return '–' if self.started is None else datetime.fromtimestamp(self.started).strftime('%H:%M')

    @property
    def ended_datetime(self):
        return '–' if self.ended is None else datetime.fromtimestamp(self.ended).strftime('%-d %b %Y %H:%M')

    @property
    def ended_time(self):
        return '–' if self.ended is None else datetime.fromtimestamp(self.ended).strftime('%H:%M')

    @property
    def started_weekday(self):
        return '' if self.started is None else datetime.fromtimestamp(self.started).strftime('%A')

    @property
    def started_weekday_short(self):
        return '' if self.started is None else datetime.fromtimestamp(self.started).strftime('%a')

    def __str__(self):
        try:
            if self.matches.all().exists():
                return f'{self.started_datetime} — {self.ended_datetime} ({self.pk})'
        except:
            pass
        return f'Empty Gaming Session ({self.pk})'


def get_match_result(team_idx, team_scores):
    own_team_score = team_scores[ team_idx]
    opp_team_score = team_scores[(team_idx + 1) % 2]
    if own_team_score < opp_team_score: return 'l'
    if own_team_score > opp_team_score: return 'w'
    return 't'


class Match(models.Model):

    sharecode   = models.CharField(blank=False, max_length=50)
    timestamp   = models.PositiveBigIntegerField()
    score_team1 = models.PositiveSmallIntegerField()
    score_team2 = models.PositiveSmallIntegerField()
    duration    = models.PositiveSmallIntegerField()
    map_name    = models.SlugField()
    sessions    = models.ManyToManyField(GamingSession, related_name='matches', blank=True)

    class Meta:
        verbose_name_plural = "Matches"
        constraints = [
            models.UniqueConstraint(
                fields=['sharecode', 'timestamp'], name='unique_sharecode_timestamp'
            )
        ]

    @staticmethod
    def create_from_data(data):
        existing_matches = Match.objects.filter(sharecode = data['sharecode'], timestamp = data['timestamp'])
        if len(existing_matches) != 0: return existing_matches.get()

        fetch_match_details(data)

        with transaction.atomic():
            m = Match()
            m.sharecode = data['sharecode']
            m.timestamp = data['timestamp']
            m.score_team1 = data['summary'].team_scores[0]
            m.score_team2 = data['summary'].team_scores[1]
            m.duration = data['summary'].match_duration
            m.map_name = data['map']
            m.save()

            slices = [
                data['steam_ids'],
                data['summary'].enemy_kills,
                data['summary'].assists,
                data['summary'].deaths,
                data['summary'].scores,
                data['summary'].mvps,
                data['summary'].enemy_headshots,
            ]
            players = list()
            for pos, (steamid, kills, assists, deaths, score, mvps, headshots) in enumerate(zip(*slices)):

                steam_profiles = SteamProfile.objects.filter(steamid = steamid)
                if len(steam_profiles) == 0:
                    steam_profile = SteamProfile.objects.create(steamid = steamid)
                else:
                    steam_profile = steam_profiles[0]
                    steam_profile.save() # updates data from Steam API

                players.append(steam_profile)

                mp = MatchParticipation(player = steam_profile, pmatch = m)
                mp.position  =     pos  % 5 # this is the CSGO scoreboard position (corresponds to the score), in CS2 it is not used
                mp.team      = 1 + pos // 5
                mp.result    = get_match_result(mp.team - 1, (m.score_team1, m.score_team2))
                mp.kills     = kills
                mp.assists   = assists
                mp.deaths    = deaths
                mp.score     = score
                mp.mvps      = mvps
                mp.headshots = headshots
                mp.adr       = float(data['adr'][str(steam_profile.steamid)] or 0)
                mp.save()

            for kill_data in data['kills'].to_dict(orient='records'):
                if kill_data['attacker_team_name'] == kill_data['victim_team_name'] or kill_data['attacker_steamid'] == 'None': continue
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
                kev.save()

            squad_ids = set()
            for player in players:
                account = getattr(player, 'account', None)
                if account is None: continue
                for squad in account.steam_profile.squads.all():
                    squad_ids.add(squad.pk)
            for squad_id in squad_ids:
                squad = Squad.objects.get(uuid = squad_id)
                squad.handle_new_match(m)

            return m

    def __str__(self):
        return f'{self.map_name} ({self.datetime})'

    @property
    def rounds(self):
        return self.score_team1 + self.score_team2

    @property
    def timestamp_end(self):
        return self.timestamp + self.duration

    @property
    def datetime(self):
        return csgo_timestamp_to_datetime(self.timestamp)

    @property
    def datetime_end(self):
        return csgo_timestamp_to_datetime(self.timestamp + self.duration)

    @property
    def time(self):
        return csgo_timestamp_to_datetime(self.timestamp, fmt='%H:%M')

    @property
    def time_end(self):
        return csgo_timestamp_to_datetime(self.timestamp + self.duration, fmt='%H:%M')

    def get_participation(self, player):
        if isinstance(player, str):
            return self.matchparticipation_set.get(player__steamid = player)
        else:
            return self.matchparticipation_set.get(player = player)

    def get_session(self, squad):
        return get_or_none(self.sessions, squad__pk = squad.pk)


m2m_changed.connect(GamingSession.sessions_changed, sender=Match.sessions.through)


class MatchParticipation(models.Model):

    player = models.ForeignKey(SteamProfile, on_delete=models.PROTECT, verbose_name='Player')
    pmatch = models.ForeignKey(Match, on_delete=models.CASCADE, verbose_name='Match')

    position = models.PositiveSmallIntegerField() # scoreboard position
    team     = models.PositiveSmallIntegerField() # team 1 or team 2
    result   = models.CharField(blank=False, max_length=1) # (t) tie, (w) win, (l) loss

    kills     = models.PositiveSmallIntegerField() # enemy kills
    assists   = models.PositiveSmallIntegerField()
    deaths    = models.PositiveSmallIntegerField()
    score     = models.PositiveSmallIntegerField()
    mvps      = models.PositiveSmallIntegerField()
    headshots = models.PositiveSmallIntegerField() # enemy headshots
    adr       = models.FloatField()                # average damage per round

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'pmatch'], name='unique_player_pmatch'
            ),
            models.UniqueConstraint(
                fields=['pmatch', 'team', 'position'], name='unique_pmatch_team_position',
            ),
        ]
        ordering = ['-adr'] # in CSGO, this was `position` (corresponding to the score), but in CS2 the ordering is determiend by the ADR

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
            if kev.round is None: continue
            rounds[kev.round] += 1
        return (rounds == n).sum()

    @staticmethod
    def filter(qs, period):
        return qs if period is None else qs.filter(**period.filters())

    class Period:

        LONG_TERM_TREND_SHIFT  = -60 * 60 * 24 * 7 # 7 days to the past
        SHORT_TERM_TREND_SHIFT = -60 * 60 * 12     # half a day to the past
        DEFAULT_DAYS = 30

        def __init__(self):
            timestamp_now = datetime.timestamp(datetime.now())
            self.start = None
            self.end   = timestamp_now

        def without_old(self, days=DEFAULT_DAYS):
            timestamp_now = datetime.timestamp(datetime.now())
            self.start = timestamp_now - days * 24 * 60 * 60
            return self

        def shift(self, seconds):
            if self.start is not None: self.start += seconds
            if self.end   is not None: self.end   += seconds
            return self

        def filters(self):
            filters = dict()
            if self.start is not None: filters['pmatch__timestamp__gte'] = self.start
            if self.end   is not None: filters['pmatch__timestamp__lte'] = self.end
            return filters


def get_or_none(qs, **kwargs):
    try:
        return qs.get(**kwargs)
    except ObjectDoesNotExist:
        return None
    except MultipleObjectsReturned:
        print('-' * 10)
        for obj in qs.filter(**kwargs).all():
            print(obj)
        print('-' * 10)
        raise


class KillEvent(models.Model):

    killer = models.ForeignKey(MatchParticipation, related_name= 'kill_events', on_delete=models.CASCADE)
    victim = models.ForeignKey(MatchParticipation, related_name='death_events', on_delete=models.CASCADE)

    round = models.PositiveSmallIntegerField(null=True, blank=True)
    kill_type = models.PositiveSmallIntegerField() # 1 if T kills CT and 2 if CT kills T
    bomb_planted = models.BooleanField(null=False) # True iff bomb was already planted

    killer_x = models.FloatField()
    killer_y = models.FloatField()
    killer_z = models.FloatField()

    victim_x = models.FloatField()
    victim_y = models.FloatField()
    victim_z = models.FloatField()


class PlayerOfTheWeek(models.Model):

    timestamp = models.PositiveBigIntegerField()
    player1   = models.ForeignKey(SteamProfile, null=True , on_delete=models.SET_NULL, blank=True, related_name='potw1') # gold
    player2   = models.ForeignKey(SteamProfile, null=True , on_delete=models.SET_NULL, blank=True, related_name='potw2') # silver
    player3   = models.ForeignKey(SteamProfile, null=True , on_delete=models.SET_NULL, blank=True, related_name='potw3') # bronze
    squad     = models.ForeignKey(Squad       , null=False, on_delete=models.CASCADE)
    mode      = models.CharField(blank=False, max_length=20)

    @property
    def competition_start_timestamp(self):
        date = datetime.fromtimestamp(self.timestamp)
        return round(datetime.timestamp(date - timedelta(days = 7)))

    @property
    def competition_end_timestamp(self):
        return self.timestamp

    @property
    def competition_start(self):
        return csgo_timestamp(self.competition_start_timestamp)

    @property
    def competition_end(self):
        return csgo_timestamp(self.competition_end_timestamp)

    @property
    def competition_end_datetime(self):
        return csgo_timestamp_to_datetime(self.competition_end_timestamp)

    @property
    def week(self):
        return self.competition_end.isocalendar()[1]

    @property
    def year(self):
        return self.competition_end.year

    @staticmethod
    def create_prehistoric_badge(squad):
        prehistoric_match = squad.matches().earliest('timestamp')
        prehistoric_match_date = datetime.fromtimestamp(prehistoric_match.timestamp)
        prehistoric_badge_date = prehistoric_match_date + timedelta(days = -prehistoric_match_date.weekday())
        prehistoric_badge_date = prehistoric_badge_date.replace(hour=4, minute=0)
        prehistoric_timestamp  = round(datetime.timestamp(prehistoric_badge_date))
        prehistoric_badge = PlayerOfTheWeek(timestamp = prehistoric_timestamp, squad = squad, mode = potw.mode_cycle[-1].id)
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
                player_data = dict(player = SteamProfile.objects.get(pk = steamid)) | {field: player_stats[steamid][field] for field in stat_fields}
                fail_requirements = mode.does_fail_requirements(player_stats[steamid])
                if fail_requirements != None:
                    player_data['place_candidate'] = None
                    player_data['unfulfilled_requirement'] = str(fail_requirements)
                elif next_place <= 3 and len(top_steamids) > next_place:
                    player_data['place_candidate'] = next_place
                    next_place += 1
                else:
                    player_data['place_candidate'] = None
                result['leaderboard'].append(player_data)
        draft_badge = PlayerOfTheWeek(timestamp = result['timestamp'], squad = squad, mode = mode.id)
        result['competition_end'] = draft_badge.competition_end_datetime
        result['week'] = draft_badge.week - 1
        result['year'] = draft_badge.year
        result['mode'] = draft_badge.mode
        return result

    @staticmethod
    def create_badge(badge_data):
        if datetime.timestamp(csgo_timestamp(badge_data['timestamp'])) > datetime.timestamp(datetime.now()): return None
        badge = PlayerOfTheWeek(timestamp = badge_data['timestamp'], squad = badge_data['squad'], mode = badge_data['mode'])
        for player_data in badge_data['leaderboard']:
            if   player_data['place_candidate'] == 1: badge.player1 = player_data['player']
            elif player_data['place_candidate'] == 2: badge.player2 = player_data['player']
            elif player_data['place_candidate'] == 3: badge.player3 = player_data['player']
        badge.save()
        mode = potw.get_mode_by_id(badge.mode)
        text = f'Attention now, the results of the *{mode.name}* are in! 🥇 <{badge.player1.steamid}> is the **Player of the Week {badge.week}/{badge.year}**!'
        if badge.player2 is not None:
            if badge.player3 is None: text = f'{text} Second place goes to 🥈 <{badge.player2.steamid}>.'
            else: text = f'{text} Second and third places go to 🥈 <{badge.player2.steamid}> and 🥉 <{badge.player3.steamid}>, respectively.'
        ScheduledNotification.objects.create(squad=badge_data['squad'], text=text)
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
                    if next_badge is None: break
            except Match.DoesNotExist:
                log.error(f'Failed to create missing badges.', exc_info=True)

    class Meta:
        verbose_name        = 'Player-of-the-Week badge';
        verbose_name_plural = 'Player-of-the-Week badges';

    def __str__(self):
        return f'{self.week}/{self.year}'


class MatchBadgeType(models.Model):

    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name        = 'Match-based badge type';
        verbose_name_plural = 'Match-based badge types';


class MatchBadge(models.Model):

    participation = models.ForeignKey(MatchParticipation, related_name='badges', on_delete=models.PROTECT)
    badge_type    = models.ForeignKey(MatchBadgeType, related_name='btype', on_delete=models.PROTECT)
    frequency     = models.PositiveSmallIntegerField(null=False, default=1)

    @staticmethod
    def award(participation, old_participations):
        if len(old_participations) >= 10:
            MatchBadge.award_surpass_yourself_badge(participation, old_participations[-20:])
        MatchBadge.award_kills_in_one_round_badges(participation, 5, 'ace')
        MatchBadge.award_kills_in_one_round_badges(participation, 4, 'quad-kill')
        MatchBadge.award_margin_badge(participation, 'carrier', order='-adr', margin=2, emoji='🍆')
        MatchBadge.award_margin_badge(participation, 'peach', order='adr', margin=0.75, emoji='🍑')

    @staticmethod
    def award_surpass_yourself_badge(participation, old_participations):
        badge_type = MatchBadgeType.objects.get(slug='surpass-yourself')
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists(): return
        kd_series = [mp.kd for mp in old_participations]
        kd_mean = np.mean(kd_series)
        kd_std  = np.std (kd_series)
        threshold = kd_mean + 2 * kd_std
        if participation.kd > threshold:
            log.info(f'Surpass-yourself badge awarded to {participation.player.name} for K/D {participation.kd} whre threshold was {threshold}')
            MatchBadge.objects.create(badge_type=badge_type, participation=participation)
            text = f'🎖️ <{participation.player.steamid}> has been awarded the **Surpass-yourself Badge** in recognition of their far-above average performance on *{participation.pmatch.map_name}* recently!'
            for squad in participation.player.squads.all():
                ScheduledNotification.objects.create(squad=squad, text=text)

    @staticmethod
    def award_kills_in_one_round_badges(participation, kill_number, badge_type_slug):
        badge_type = MatchBadgeType.objects.get(slug = badge_type_slug)
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists(): return
        number = participation.streaks(n = kill_number)
        if number > 0:
            log.info(f'{participation.player.name} achieved {badge_type.name} {number} time(s)')
            MatchBadge.objects.create(badge_type = badge_type, participation = participation, frequency = number)
            frequency = '' if number == 1 else f' {number} times'
            text = f'<{participation.player.steamid}> has achieved **{badge_type.name}**{frequency} on *{participation.pmatch.map_name}* recently!'
            for squad in participation.player.squads.all():
                ScheduledNotification.objects.create(squad=squad, text=text)

    @staticmethod
    def award_margin_badge(participation, badge_type_slug, order, margin, emoji):
        kpi = order[1:] if order[0] in '+-' else order
        badge_type = MatchBadgeType.objects.get(slug = badge_type_slug)
        if MatchBadge.objects.filter(badge_type=badge_type, participation=participation).exists(): return
        teammates = participation.pmatch.matchparticipation_set.filter(team = participation.team).order_by(order)

        awarded = teammates[0].pk == participation.pk and any(
            (
                order[0] == '-' and getattr(teammates[0], kpi) > margin * getattr(teammates[1], kpi),
                order[0] != '-' and getattr(teammates[0], kpi) < margin * getattr(teammates[1], kpi),
            )
        )

        if awarded:
            log.info(f'{participation.player.name} received the {badge_type.name}')
            MatchBadge.objects.create(badge_type = badge_type, participation = participation)
            text = f'{emoji} <{participation.player.steamid}> has qualified for the **{badge_type.name}** on *{participation.pmatch.map_name}*!'
            for squad in participation.player.squads.all():
                ScheduledNotification.objects.create(squad=squad, text=text)

    class Meta:
        verbose_name        = 'Match-based badge'
        verbose_name_plural = 'Match-based badges'

        constraints = [
            models.UniqueConstraint(
                fields=['participation', 'badge_type'], name='unique_participation_badge_type'
            )
        ]


class UpdateTask(models.Model):

    account = models.ForeignKey(Account, related_name='update_tasks', on_delete=models.CASCADE)
    scheduled_timestamp = models.PositiveBigIntegerField(verbose_name='Scheduled')
    execution_timestamp = models.PositiveBigIntegerField(null=True, blank=True, verbose_name='Execution started') # when the execution started
    completed_timestamp = models.PositiveBigIntegerField(null=True, blank=True, verbose_name='Completed') # when the execution finished

    @property
    def scheduled(self):
        return datetime.fromtimestamp(self.scheduled_timestamp)

    @property
    def execution(self):
        if self.execution_timestamp is None: return None
        else: return datetime.fromtimestamp(self.execution_timestamp)

    @property
    def completed(self):
        if self.completed_timestamp is None: return None
        else: return datetime.fromtimestamp(self.completed_timestamp)

    @property
    def scheduled_datetime(self):
        return self.scheduled.strftime('%-d %b %Y %H:%M')

    @property
    def execution_datetime(self):
        if self.execution is None: return None
        else: return self.execution.strftime('%-d %b %Y %H:%M')

    @property
    def completed_datetime(self):
        if self.completed is None: return None
        else: return self.completed.strftime('%-d %b %Y %H:%M')

    @property
    def is_completed(self):
        return self.completed_timestamp is not None

    def run(self):
        self.execution_timestamp = datetime.timestamp(datetime.now())
        self.save()

        if self.account.enabled:
            try:
                first_sharecode = self.account.sharecode
                new_match_data  = api.fetch_matches(first_sharecode, SteamAPIUser(self.account.steamid, self.account.steam_auth))

                old_participations = list(self.account.match_participations().order_by('pmatch__timestamp'))
                for match_data in new_match_data:

                    fast_forward = False
                    try:
                        pmatch = Match.create_from_data(match_data)

                    except FileNotFoundError as ex:
                        if str(ex) == 'JSON path does not exist!':
                            # see: https://github.com/pnxenopoulos/awpy/issues/291
                            log.error(f'Skipping match with sharecode {match_data["sharecode"]} due to error: https://github.com/pnxenopoulos/awpy/issues/291')
                            fast_forward = True
                        else:
                            raise

                    self.account.last_sharecode = match_data['sharecode']
                    self.account.save()
                    if fast_forward: continue

                    participation = pmatch.get_participation(self.account.steam_profile)
                    MatchBadge.award(participation, old_participations)

                    old_participations.append(participation)

            except InvalidSharecodeError:
                self.account.enabled = False
                self.account.save()

        self.completed_timestamp = datetime.timestamp(datetime.now())
        self.save()

        self.account.handle_finished_update()

        kept_tasks = UpdateTask.objects.order_by('-scheduled_timestamp')[:100]
        UpdateTask.objects.exclude(pk__in=kept_tasks.values_list('pk', flat=True)).delete()

