import logging
import numbers
import os

import gitinfo
import numpy as np
from accounts.models import (
    Account,
    Squad,
    SquadMembership,
    SteamProfile,
)
from cs2pb_typing import (
    List,
    Optional,
)

from django.core.mail import send_mail
from django.db.models import (
    Count,
    F,
    Max,
)
from django.http import HttpResponseNotFound
from django.shortcuts import (
    redirect,
    render,
)
from django.urls import reverse

from . import potw
from .features import (
    Feature,
    Features,
)
from .models import (
    GamingSession,
    Match,
    MatchParticipation,
    PlayerOfTheWeek,
    UpdateTask,
)

log = logging.getLogger(__name__)


ADMIN_MAIL_ADDRESS = os.environ['CS2PB_ADMIN_MAIL_ADDRESS']
assert len(ADMIN_MAIL_ADDRESS) > 0


badge_order = [
    'potw-1',
    'potw-2',
    'potw-3',
    'carrier',
    'rising-star',
    'surpass-yourself',
    'peach',
    'ace',
    'quad-kill',
]


all_features_collapsed = [
    Features.player_value,
    Features.participation_effect,
    Features.headshot_rate,
]


all_features_expanded = all_features_collapsed + [
    Features.damage_per_round,
    Features.kills_per_death,
]


def get_badges(squad, player):
    potw = [
        len(PlayerOfTheWeek.objects.filter(player1 = player)),
        len(PlayerOfTheWeek.objects.filter(player2 = player)),
        len(PlayerOfTheWeek.objects.filter(player3 = player)),
    ]
    badges = list()
    for place, count in enumerate(potw, start=1):
        if count > 0:
            badges.append(dict(slug=f'potw-{place}', count=count))
    for badge in player.match_badges().all().values(
        'badge_type'
    ).annotate(
        count = Count('badge_type'),
    ).order_by(
        'badge_type',
    ):
        if badge['count'] > 0:
            badges.append(
                dict(
                    slug = badge['badge_type'],
                    count = badge['count'],
                )
            )
    rising_star_count = GamingSession.objects.filter(squad = squad, rising_star = player).count()
    if rising_star_count > 0:
        badges.append(dict(slug = 'rising-star', count = rising_star_count))
    badges.sort(key = lambda badge: badge_order.index(badge['slug']))
    if len(badges) > 0:
        badges = badges[:5]
    return badges


def compute_card(
        squad_membership: SquadMembership,
        features: List[Feature],
        orders: List[numbers.Real] = [2, 3, np.inf],
    ):

    def stat(feature):
        value = squad_membership.stats.get(feature.slug, None)

        # Compute the maximum value of the squad for normalization
        max_value = squad_membership.squad.memberships.values(
            f'stats__{feature.slug}',
        ).exclude(
            **{f'stats__{feature.slug}': None},  # https://stackoverflow.com/a/49956014/1444073
        ).order_by(
            f'-stats__{feature.slug}',
        )[0][
            f'stats__{feature.slug}'
        ] if value is not None else None

        # Check logics: `max_value` can only be None if `value` is None
        assert value is None or (value is not None and max_value is not None), (feature.slug, value, max_value)

        # Format the trend string
        trend = squad_membership.trends.get(feature.slug)
        trend_str = feature.format.format(trend) if trend is not None else ''
        if len(trend_str) > 0 and float(trend_str) == 0:
            trend_str = ''
            trend = 0  # pretend that the trend is zero if it is too small

        # Compose and return the full feature information for the squad member
        return {
            'name': feature.name,
            'value': value,
            'load': None if value is None else 100 * min((1, value / max_value)),
            'load_raw': None if value is None else value / max_value,
            'max_value': max_value,
            'trend': trend,
            'trend_str': trend_str,
            'label': feature.format.format(value) if value is not None else '',
        }

    stats   = [stat(feature) for feature in features]
    badges  = get_badges(squad_membership.squad, squad_membership.player)
    card_data = {
        'profile': squad_membership.player,
        'stats': stats,
        'stats_dict': {s['name']: s['value'] for s in stats},
        'badges': badges,
    }
    if getattr(squad_membership.player, 'account', None) is None and squad_membership.squad is not None:
        card_data['invite_url'] = reverse(
            'invite',
            kwargs = dict(
                steamid = squad_membership.player.steamid,
                squadid = squad_membership.squad.pk,
            ),
        )
    for stat_idx, stat in enumerate(card_data['stats']):
        for order, idx_max in enumerate(orders, start = 1):
            if stat_idx < idx_max:
                stat['order'] = order
                break
    return card_data


def squad_expanded_stats(request, squad):
    return squads(request, squad, expanded_stats=True)


def split_into_chunks(data, n):
    chunks = [data]
    while True:
        if len(chunks[-1]) > n:
            chunks = chunks[:-1] + [chunks[-1][:n]] + [chunks[-1][n:]]
        else:
            break
    return chunks


def split_into_chunks_ex(data, n_min, n_max):
    """
    Split data into chunks of variable length by avoiding short tails.
    """
    splits = {n: split_into_chunks(data, n) for n in range(n_min, n_max + 1)}
    tail_size_by_n = {n: len(splits[n][-1]) for n in splits.keys()}
    return splits[max(tail_size_by_n, key = tail_size_by_n.get)]


def squads(request, squad = None, expanded_stats = False):
    context = dict()

    if squad is not None:
        try:
            squad_list = [Squad.objects.get(uuid = squad)]
            context['squad'] = squad_list[0]
        except Squad.DoesNotExist:
            return HttpResponseNotFound('No such squad')

    elif getattr(request.user, 'steam_profile', None) is not None:
        squad_list = Squad.objects.filter(memberships__player = request.user.steam_profile).order_by('name')

    else:
        return redirect('login')

    context['squads'] = list()
    for squad in squad_list:
        squad.update_stats()
        for account in Account.objects.filter(
            steam_profile__in = squad.memberships.values_list('player__pk', flat = True)
        ):
            account.update_matches()
        PlayerOfTheWeek.create_missing_badges(squad)
        cards = [
            compute_card(
                squad_membership,
                all_features_expanded if expanded_stats else all_features_collapsed,
            )
            for squad_membership in squad.memberships.exclude(
                position__isnull = True,
            ).order_by(
                'position',
            )
        ]

        # Split the cards into rows
        rows = split_into_chunks_ex(cards, n_min = 4, n_max = 7)

        try:
            upcoming_potw = PlayerOfTheWeek.get_next_badge_data(squad)
            upcoming_potw_mode = potw.get_mode_by_id(upcoming_potw['mode'])
        except Match.DoesNotExist:
            log.warning(
                f'Failed to fetch upcoming Player of the Week because no matches were added yet',
                exc_info = True,
            )
            upcoming_potw = None
            upcoming_potw_mode = None
        squad_data = {
            'name': squad.name,
            'uuid': squad.uuid,
            'share_link': squad.absolute_url(request),
            'expand_url': None if expanded_stats else reverse(
                'squad_expanded_stats',
                kwargs = dict(squad = squad.uuid),
            ),
            'card_rows': rows,
            'upcoming_player_of_the_week': upcoming_potw,
            'upcoming_player_of_the_week_mode': upcoming_potw_mode,
        }
        if upcoming_potw is not None and len(upcoming_potw['leaderboard']) > 0:

            # The maximum value is used as the denominator for normalization
            potw_denominator = max(
                max([player_data[field] for player_data in upcoming_potw['leaderboard']])
                for field in upcoming_potw_mode.fields
            )

            for player_data in upcoming_potw['leaderboard']:
                player_data[f'details'] = upcoming_potw_mode.details(player_data)
                for fidx, field in enumerate(upcoming_potw_mode.fields):
                    player_data[f'field{fidx + 1}'] = player_data[field]
                    player_data[f'field{fidx + 1}_rel'] = player_data[field] / potw_denominator

        context['squads'].append(squad_data)

    context['request'] = request
    add_globals_to_context(context)
    return render(request, 'stats/squads.html', context)


def matches(request, squad=None, last_timestamp=None):
    context = dict(request = request)

    if squad is None:
        if getattr(request.user, 'steam_profile', None) is not None:
            members = SteamProfile.objects.filter(
                squad_memberships__squad__in = request.user.steam_profile.squad_memberships.values_list(
                    'squad__pk',
                    flat = True,
                ),
            )
        else:
            return redirect('login')
    else:
        members = SteamProfile.objects.filter(squad_memberships__squad = squad)
        squad = Squad.objects.get(uuid = squad)
        context['squad'] = squad

    for m in members:
        if getattr(m, 'account', None) is not None:
            m.account.update_matches()

    sessions = GamingSession.objects.filter(
        matches__matchparticipation__player__in = members,
    ).annotate(
        timestamp = Max('matches__timestamp'),
    ).order_by(
        '-timestamp',
    )
    if last_timestamp is not None:
        sessions = sessions.filter(timestamp__lt = last_timestamp)
    sessions = sessions[:3]
    for session in sessions:
        session.matches_list = session.matches.filter(
            matchparticipation__player__in = members,
        ).distinct().order_by(
            '-timestamp',
        ).annotate(
            result = F('matchparticipation__result'),
        )
    context['sessions'] = sessions
    context['last_timestamp'] = session.timestamp if sessions.exists() else None

    if last_timestamp is None:
        add_globals_to_context(context)
        return render(request, 'stats/sessions.html', context)
    else:
        return render(request, 'stats/sessions-list.html', context)


def add_globals_to_context(context):
    context['version'] = gitinfo.get_head_info()
    qs = UpdateTask.objects.filter(completed_timestamp = None)
    qs = qs.values('account').annotate(count = Count('account'))
    if qs.count() > 0 and qs.latest('count')['count'] > 1:
        msg = 'There is a temporary malfunction of the Steam Client API.'
        context['error'] = f'{msg} Come back later.'
        send_mail('Steam API malfunction', msg, ADMIN_MAIL_ADDRESS, [ADMIN_MAIL_ADDRESS], fail_silently=True)


def player(request, squad, steamid):
    squad = Squad.objects.get(uuid = squad)
    squad.update_stats()
    player = SteamProfile.objects.get(pk = steamid)
    squad_membership = squad.memberships.filter(player = player).first()

    # Compute the player card
    card = compute_card(squad_membership, all_features_expanded)

    # Fetch the player's match participations
    participations = MatchParticipation.objects.filter(player = player).order_by('pmatch__timestamp')

    # Determine the start and end of the period for accounted period
    accounted_participations = squad_membership.accounted_match_participations
    accounted_period_start: Optional[int] = None
    accounted_period_end: Optional[int] = None
    for pidx, participation in enumerate(participations):
        if participation.pk in accounted_participations.values_list('pk', flat = True):
            if accounted_period_start is None:
                accounted_period_start = pidx
            accounted_period_end = pidx + 1

    # Compose the context for the player page
    context = dict(
        squad = squad,
        request = request,
        player = card,
        participations = participations,
        period_start = accounted_period_start,
        period_end = accounted_period_end,
        period_average = squad_membership.stats.get('player_value'),
    )

    # Add the global context and render the player page
    add_globals_to_context(context)
    return render(request, 'stats/player.html', context)
