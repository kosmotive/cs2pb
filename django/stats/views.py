from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseNotFound
from django.db.models import F, Max, Value
from django.urls import reverse
from django.core.mail import send_mail
from django.db.models import Count

from accounts.models import SteamProfile, Account, Squad
from .models import Match, MatchParticipation, PlayerOfTheWeek, UpdateTask, GamingSession
from .features import Features, FeatureContext, escape_none
import gitinfo

import os
import numpy as np
import logging


log = logging.getLogger(__name__)


ADMIN_MAIL_ADDRESS = os.environ['CS2PB_ADMIN_MAIL_ADDRESS']
assert len(ADMIN_MAIL_ADDRESS) > 0


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
    for badge in player.match_badges().filter(badge_type__is_minor = False).values('badge_type').annotate(count = Count('badge_type')).order_by('badge_type'):
        if badge['count'] > 0:
            badges.append(dict(slug=badge['badge_type'], count=badge['count']))
    rising_star_count = GamingSession.objects.filter(squad = squad, rising_star = player).count()
    if rising_star_count > 0: badges.append(dict(slug='rising-star', count=rising_star_count))
    return badges


def compute_card(player, squad, features, orders=[np.inf]):
    context = FeatureContext.create_default(player, squad)
    stats   = [feature(context) for feature in features]
    badges  = get_badges(squad, player)
    card_data = {
        'profile': player,
        'stats': stats,
        'stats_dict': {s['name']: s['value'] for s in stats},
        'badges': badges,
    }
    if getattr(player, 'account', None) is None and squad is not None:
        card_data['invite_url'] = reverse('invite', kwargs=dict(steamid=player.steamid, squadid=squad.pk))
    for stat_idx, stat in enumerate(card_data['stats']):
        for order, idx_max in enumerate(orders, start=1):
            if stat_idx < idx_max:
                stat['order'] = order
                break
    return card_data


def sorted_cards(cards, kpi='Player value'):
    cards = [card for card in cards if not all(stat['value'] is None for stat in card['stats'])]
    get_kpi = lambda p: escape_none({stat['name']: stat['value'] for stat in p['stats']}[kpi], 0)
    return sorted(cards, key=get_kpi, reverse=True)


def get_maps_played_by_squad(squad):
    maps = list()
    for m in squad.members.all():
        for mp in MatchParticipation.objects.filter(player = m).all():
            maps.append(mp.pmatch.map_name)
    return sorted(frozenset(maps))


def squad_expanded_stats(request, squad):
    return squads(request, squad, expanded_stats=True)


def squads(request, squad=None, expanded_stats=False):
    context = dict()

    if squad is not None:
        try:
            squad_list = [Squad.objects.get(uuid=squad)]
            context['squad'] = squad
        except Squad.DoesNotExist:
            return HttpResponseNotFound('No such squad')

    elif getattr(request.user, 'steam_profile', None) is not None:
        squad_list = Squad.objects.filter(members = request.user.steam_profile).order_by('name')

    else:
        return redirect('login')

    features = [Features.pv, Features.pe, Features.acc]
    if expanded_stats:
        features += [Features.adr, Features.kd]

    context['squads'] = list()
    for squad in squad_list:
        for account in Account.objects.filter(steam_profile__in = squad.members.all()):
            account.update_matches()
        PlayerOfTheWeek.create_missing_badges(squad)
        played_maps = get_maps_played_by_squad(squad)
        cards = sorted_cards([compute_card(m, squad, features, [2,3,np.inf]) for m in squad.members.all()])
        kd_by_member = {m.steamid: Features.kd(FeatureContext.create_default(m, squad))['value'] for m in squad.members.all()}
        kd_list = [kd_by_member[card['profile'].steamid] for card in cards]
        try:
            upcoming_potw = PlayerOfTheWeek.get_next_badge_data(squad)
        except Match.DoesNotExist:
            log.error(f'Failed to fetch upcoming Player of the Week', exc_info=True)
            upcoming_potw = None
        squad_data = {
            'name': squad.name,
            'share_link': squad.absolute_url(request),
            'expand_url': None if expanded_stats else reverse('squad_expanded_stats', kwargs=dict(squad = squad.uuid)),
            'members': cards,
            'upcoming_player_of_the_week': upcoming_potw,
        }
        if upcoming_potw is not None and len(upcoming_potw['leaderboard']) > 0:
            potw_max_kills   = max([player_data['kills' ] for player_data in upcoming_potw['leaderboard']])
            potw_max_deaths  = max([player_data['deaths'] for player_data in upcoming_potw['leaderboard']])
            potw_denominator = max((potw_max_kills, potw_max_deaths))
            for player_data in upcoming_potw['leaderboard']:
                player_data[ 'kills_rel'] = player_data[ 'kills'] / potw_denominator
                player_data['deaths_rel'] = player_data['deaths'] / potw_denominator
        context['squads'].append(squad_data)

    context['request'] = request
    add_globals_to_context(context)
    return render(request, 'stats/squads.html', context)


def matches(request, squad=None, last_timestamp=None):
    context = dict(request = request)

    if squad is None:
        if getattr(request.user, 'steam_profile', None) is not None:
            members = SteamProfile.objects.filter(squads__in = request.user.steam_profile.squads.all())
        else:
            return redirect('login')
    else:
        members = SteamProfile.objects.filter(squads = squad)
        context['squad'] = squad

    for m in members:
        if getattr(m, 'account', None) is not None:
            m.account.update_matches()

    sessions = GamingSession.objects.filter(matches__matchparticipation__player__in = members).annotate(timestamp = Max('matches__timestamp')).order_by('-timestamp')
    if last_timestamp is not None:
        sessions = sessions.filter(timestamp__lt = last_timestamp)
    sessions = sessions[:3]
    for session in sessions:
        session.matches_list = session.matches.filter(matchparticipation__player__in = members).distinct().order_by('-timestamp').annotate(result = F('matchparticipation__result'))
    context['sessions'] = sessions
    context['last_timestamp'] = session.timestamp if sessions.exists() else None

    if last_timestamp is None:
        add_globals_to_context(context)
        return render(request, 'stats/sessions.html', context)
    else:
        return render(request, 'stats/sessions-list.html', context)


def add_globals_to_context(context):
    context['version'] = gitinfo.get_head_info()
    context['changelog'] = gitinfo.changelog
    qs = UpdateTask.objects.filter(completed_timestamp = None)
    qs = qs.values('account').annotate(count = Count('account'))
    if qs.count() > 0 and qs.latest('count')['count'] > 1:
        msg = 'There is a temporary malfunction of the Steam Client API.'
        context['error'] = f'{msg} Come back later.'
        send_mail('Steam API malfunction', msg, ADMIN_MAIL_ADDRESS, [ADMIN_MAIL_ADDRESS], fail_silently=True)

