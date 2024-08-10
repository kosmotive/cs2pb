import datetime
import math
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.http import HttpResponseNotFound
from django.test import TestCase, RequestFactory
from django.urls import reverse

from accounts.models import Account, Squad, SteamProfile
import api
from discordbot.models import ScheduledNotification
from stats import models
from stats import potw
from stats import views
from stats import updater
from tests import testsuite
from url_forward import get_redirect_url_to


def create_kill_event(mp_killer, mp_victim, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0):
    return models.KillEvent(
        killer = mp_killer,
        victim = mp_victim,
        round = round,
        kill_type = kill_type,
        bomb_planted = bomb_planted,
        killer_x = killer_x,
        killer_y = killer_y,
        killer_z = killer_z,
        victim_x = victim_x,
        victim_y = victim_y,
        victim_z = victim_z,
    )


class add_globals_to_context(TestCase):

    def test(self):
        ctx = dict()
        views.add_globals_to_context(ctx)

        self.assertTrue('version' in ctx.keys())
        self.assertTrue('sha' in ctx['version'].keys())
        self.assertTrue('date' in ctx['version'].keys())


class Match__create_from_data(TestCase):

    def test(self):
        pmatch_data = {
            'sharecode': 'CSGO-a622L-DjJDC-5zwn4-Gx2tf-YYmQD',
            'timestamp': 1720469310,
            'summary': SimpleNamespace(
                map = testsuite.get_demo_path('003694683536926703955_1352610665'),
                team_scores = (4, 13),
                match_duration = 1653,
                enemy_kills = [
                    17,
                    12,
                    8,
                    10,
                    2,
                    19,
                    16,
                    16,
                    14,
                    8,
                ],
                enemy_headshots = [
                    14,
                    7,
                    4,
                    3,
                    1,
                    4,
                    7,
                    7,
                    7,
                    5,
                ],
                assists = [
                    4,
                    4,
                    4,
                    1,
                    4,
                    6,
                    8,
                    5,
                    4,
                    7,
                ],
                deaths = [
                    15,
                    15,
                    14,
                    14,
                    16,
                    9,
                    14,
                    8,
                    9,
                    9,
                ],
                scores = [
                    41,
                    30,
                    25,
                    21,
                    8,
                    46,
                    40,
                    40,
                    36,
                    25,
                ],
                mvps = [
                    3,
                    1,
                    0,
                    0,
                    0,
                    4,
                    4,
                    3,
                    2,
                    0,
                ],
            ),
            'steam_ids': [
                76561197967680028,
                76561197961345487,
                76561197961748270,
                76561198067716219,
                76561197962477966,
                76561198298259382,
                76561199034015511,
                76561198309743637,
                76561198140806020,
                76561198064174518,
            ],
        }
        pmatch = models.Match.create_from_data(pmatch_data)

        self.assertEqual(pmatch.sharecode, pmatch_data['sharecode'])
        self.assertEqual(pmatch.timestamp, pmatch_data['timestamp'])
        self.assertEqual(pmatch.score_team1, pmatch_data['summary'].team_scores[0])
        self.assertEqual(pmatch.score_team2, pmatch_data['summary'].team_scores[1])
        self.assertEqual(pmatch.duration, pmatch_data['summary'].match_duration)
        self.assertEqual(pmatch.map_name, 'de_vertigo')
        self.assertEqual(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').kills, 17)
        self.assertEqual(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').deaths, 15)
        self.assertEqual(round(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').adr, 1), 104.7)

        return pmatch


class MatchBadge__award(TestCase):

    def test_no_awards(self):
        pmatch = Match__create_from_data().test()
        participation = pmatch.get_participation('76561197967680028')
        models.MatchBadge.award(participation, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(participation = participation)), 0)

    def test_quad_kill(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            [
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
            ]
        )
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'quad-kill')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'quad-kill').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_quad_kill_twice(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            [
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
            ]
        )
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'quad-kill')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'quad-kill').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)

    def test_ace(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            [
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
            ]
        )
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'ace')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_ace_twice(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            [
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
                create_kill_event(mp1, mp2, round = 2),
            ]
        )
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'ace')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)

    def test_carrier_badge(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')

        # Test with ADR right below the threshold
        mp1.adr = 1.99 * mp2.adr
        mp1.save()
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'carrier', participation = mp1)), 0)

        # Test with ADR right above the threshold
        mp1.adr = 2.01 * mp2.adr
        mp1.save()
        models.MatchBadge.award(mp1, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'carrier', participation = mp1)), 1)

    def test_peach_price(self):
        pmatch = Match__create_from_data().test()
        mp4 = pmatch.get_participation('76561198067716219')
        mp5 = pmatch.get_participation('76561197962477966')

        # Test with ADR right below the threshold
        mp5.adr = 0.76 * mp4.adr
        mp5.save()
        models.MatchBadge.award(mp5, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = mp5)), 0)

        # Test with ADR right above the threshold
        mp5.adr = 0.74 * mp4.adr
        mp5.save()
        models.MatchBadge.award(mp5, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = mp5)), 1)


class Squad__do_changelog_announcements(TestCase):

    changelog = [
        {
            'message': 'Fix player cards HTML/CSS',
            'url': 'https://github.com/kodikit/cs2pb/pull/6',
            'sha': '4a7136f55f7db3cd7c12191103eeb36ece7feafd',
            'date': '2024-07-26',
        },
        {
            'message': 'Fix Discord name field in settings/signup',
            'url': 'https://github.com/kodikit/cs2pb/pull/5',
            'sha': 'f229070697d182f1aa55b2594bf3e7f0cf69bd34',
            'date': '2024-07-25',
        },
        {
            'message': 'Reduce memory usage',
            'url': 'https://github.com/kodikit/cs2pb/pull/2',
            'sha': '4fdb97a4c5de5fe0bd7fba1798acbde702c08212',
            'date': '2024-07-24',
        },
    ]

    def test_new_squad(self):
        squad = Squad.objects.create(name='squad', discord_channel_id='xxx')
        squad.do_changelog_announcements(changelog = Squad__do_changelog_announcements.changelog)
        c = {
            'message': 'Hotfix: Minor layout improvements',
            'url': get_redirect_url_to('https://github.com/kodikit/cs2pb/commits/9074a7a848a6ac74ba729757e1b2a4a971586190'),
            'sha': '9074a7a848a6ac74ba729757e1b2a4a971586190',
            'date': '2024-07-26',
        }
        squad.do_changelog_announcements(changelog = [c] + Squad__do_changelog_announcements.changelog)
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.get()
        self.assertEqual(notification.squad.pk, squad.pk)
        text = notification.text
        self.assertIn(c['message'], text)
        self.assertIn(c['date'], text)
        self.assertIn(get_redirect_url_to(c['url']), text)
        for c in Squad__do_changelog_announcements.changelog:
            self.assertNotIn(Squad__do_changelog_announcements.changelog[-1]['url'], text)

    def test_without_discord_channel(self):
        squad = Squad.objects.create(name='squad', last_changelog_announcement=Squad__do_changelog_announcements.changelog[-1]['sha'])
        squad.do_changelog_announcements(changelog = Squad__do_changelog_announcements.changelog)
        self.assertEqual(len(ScheduledNotification.objects.all()), 0)

    def test(self):
        squad = Squad.objects.create(name='squad', discord_channel_id='xxx', last_changelog_announcement=Squad__do_changelog_announcements.changelog[-1]['sha'])
        squad.do_changelog_announcements(changelog = Squad__do_changelog_announcements.changelog)
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.get()
        self.assertEqual(notification.squad.pk, squad.pk)
        text = notification.text
        for c in Squad__do_changelog_announcements.changelog[:-1]:
            self.assertIn(c['message'], text)
            self.assertIn(c['date'], text)
            self.assertIn(get_redirect_url_to(c['url']), text)
        self.assertNotIn(Squad__do_changelog_announcements.changelog[-1]['url'], text)


class get_next_potw_mode(TestCase):

    def test(self):
        self.assertEqual(potw.get_next_mode(potw.mode_cycle[ 0].id), potw.mode_cycle[1])
        self.assertEqual(potw.get_next_mode(potw.mode_cycle[-1].id), potw.mode_cycle[0])


class PlayerOfTheWeek__get_next_badge_data(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.squad = Squad.objects.create(name='squad')
        self.team1 = [
            SteamProfile.objects.create(steamid = '12345678900000001'),
            SteamProfile.objects.create(steamid = '12345678900000002'),
            SteamProfile.objects.create(steamid = '12345678900000003'),
        ]
        self.team2 = [
            SteamProfile.objects.create(steamid = '12345678900000004'),
            SteamProfile.objects.create(steamid = '12345678900000005'),
            SteamProfile.objects.create(steamid = '12345678900000006'),
        ]

        # Add players to squad
        for player in self.players:
            self.squad.members.add(player)

        # Create an initial match
        self.pmatch = self._create_match(0)

    @property
    def players(self):
        return self.team1 + self.team2

    def _create_match(self, timestamp):
        m = models.Match.objects.create(
            sharecode = f'sharecode-{timestamp}',
            timestamp = timestamp,
            score_team1 = 12,
            score_team2 = 13,
            duration = 1653,
            map_name = 'de_dust2',
        )
        for uidx, user in enumerate(self.players):
            mp = models.MatchParticipation(player = user, pmatch = m)
            mp.position  = uidx % 3
            mp.team      = 1 + uidx // 3
            mp.result    = models.get_match_result(mp.team - 1, (m.score_team1, m.score_team2))
            mp.kills     =  20   + uidx
            mp.assists   =  10   - uidx
            mp.deaths    =  15   + uidx
            mp.score     =  30   - uidx
            mp.mvps      =   5   + uidx
            mp.headshots =  15   - uidx
            mp.adr       = 120.5 + uidx
            mp.save()
        return m

    def test_kd_challenge(self):
        badge = models.PlayerOfTheWeek.get_next_badge_data(self.squad, force_mode = 'k/d')
        self.assertEqual(badge['mode'], 'k/d')
        self.assertEqual(badge['week'], 1)
        self.assertEqual(badge['year'], 1970)
        for entry in badge['leaderboard']:
            player = entry['player']

            if entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team1)

            if not entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team2)

            if entry.get('place_candidate') is None:
                self.assertIn(player, self.team1)

            if entry.get('place_candidate') == 1:
                self.assertEqual(player.pk, self.team2[0].pk)

            if entry.get('place_candidate') == 2:
                self.assertEqual(player.pk, self.team2[1].pk)

            if entry.get('place_candidate') == 3:
                self.assertEqual(player.pk, self.team2[2].pk)

        return badge

    def test_streak_challenge(self):
        mp1 = self.pmatch.get_participation('12345678900000001')
        mp4 = self.pmatch.get_participation('12345678900000004')
        mp5 = self.pmatch.get_participation('12345678900000005')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            sum(
                [
                    [create_kill_event(mp5, mp1, round = 1)] * 3,
                    [create_kill_event(mp5, mp1, round = 2)] * 5,
                    [create_kill_event(mp4, mp1, round = 1)] * 5,
                ],
                list(),
            )
        )

        badge = models.PlayerOfTheWeek.get_next_badge_data(self.squad, force_mode = 'streaks')
        self.assertEqual(badge['mode'], 'streaks')
        self.assertEqual(badge['week'], 1)
        self.assertEqual(badge['year'], 1970)
        for entry in badge['leaderboard']:
            player = entry['player']

            if entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team1 + [self.team2[2]])

            if not entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team2[:2])

            if entry.get('place_candidate') is None:
                self.assertIn(player, self.team1 + [self.team2[2]])

            if entry.get('place_candidate') == 1:
                self.assertEqual(player.pk, self.team2[1].pk)

            if entry.get('place_candidate') == 2:
                self.assertEqual(player.pk, self.team2[0].pk)

            self.assertNotEqual(entry.get('place_candidate'), 3)

        return badge

    def test_adr_challenge(self):
        badge = models.PlayerOfTheWeek.get_next_badge_data(self.squad, force_mode = 'adr')
        self.assertEqual(badge['mode'], 'adr')
        self.assertEqual(badge['week'], 1)
        self.assertEqual(badge['year'], 1970)
        for entry in badge['leaderboard']:
            player = entry['player']

            if entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team1)

            if not entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team2)

            if entry.get('place_candidate') is None:
                self.assertIn(player, self.team1)

            if entry.get('place_candidate') == 1:
                self.assertEqual(player.pk, self.team2[-1].pk)

            if entry.get('place_candidate') == 2:
                self.assertEqual(player.pk, self.team2[-2].pk)

            if entry.get('place_candidate') == 3:
                self.assertEqual(player.pk, self.team2[-3].pk)

        return badge

    def test_accuracy_challenge(self):
        badge = models.PlayerOfTheWeek.get_next_badge_data(self.squad, force_mode = 'accuracy')
        self.assertEqual(badge['mode'], 'accuracy')
        self.assertEqual(badge['week'], 1)
        self.assertEqual(badge['year'], 1970)
        for entry in badge['leaderboard']:
            player = entry['player']

            if entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team1)

            if not entry.get('unfulfilled_requirement', ''):
                self.assertIn(player, self.team2)

            if entry.get('place_candidate') is None:
                self.assertIn(player, self.team1)

            if entry.get('place_candidate') == 1:
                self.assertEqual(player.pk, self.team2[0].pk)

            if entry.get('place_candidate') == 2:
                self.assertEqual(player.pk, self.team2[1].pk)

            if entry.get('place_candidate') == 3:
                self.assertEqual(player.pk, self.team2[2].pk)

        return badge

    def test_mode(self):
        data1 = models.PlayerOfTheWeek.get_next_badge_data(self.squad)
        badge1 = models.PlayerOfTheWeek.create_badge(data1)
        pmatch2 = self._create_match(badge1.timestamp)
        data2 = models.PlayerOfTheWeek.get_next_badge_data(self.squad)
        self.assertEqual(data2['mode'], potw.mode_cycle[1].id)
        self.assertEqual(data2['week'], 2)
        self.assertEqual(data2['year'], 1970)


class PlayerOfTheWeek__create_badge(TestCase):

    @testsuite.fake_api('accounts.models')
    def test(self):
        get_next_badge_data = PlayerOfTheWeek__get_next_badge_data()
        get_next_badge_data.setUp()
        data = get_next_badge_data.test_kd_challenge()
        get_next_badge_data.tearDown()
        badge = models.PlayerOfTheWeek.create_badge(data)
        self.assertEqual(badge.mode, 'k/d')
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        self.assertIn(potw.get_mode_by_id(badge.mode).name, ScheduledNotification.objects.get().text)


class squads(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.factory = RequestFactory()
        self.player = SteamProfile.objects.create(steamid='12345678900000001')
        self.squad = Squad.objects.create(name='Test Squad')
        self.squad.members.add(self.player)
        self.account = Account.objects.create(steam_profile=self.player)

    def test_squads_with_valid_squad(self):
        response = self.client.get(reverse('squads', kwargs={'squad': self.squad.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['squad'], self.squad.uuid)

    def test_squads_with_invalid_squad(self):
        invalid_uuid = str(uuid.uuid4())
        response = self.client.get(reverse('squads', kwargs={'squad': invalid_uuid}))
        self.assertIsInstance(response, HttpResponseNotFound)

    def test_squads_with_authenticated_user(self):
        self.client.force_login(self.account)
        response = self.client.get(reverse('squads'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['squads']), 1)
        self.assertEqual(response.context['squads'][0]['name'], self.squad.name)

    def test_squads_with_unauthenticated_user(self):
        response = self.client.get(reverse('squads'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

    @patch('stats.views.PlayerOfTheWeek.get_next_badge_data')
    def test_squads_with_upcoming_potw(self, mock_get_next_badge_data):
        mock_get_next_badge_data.return_value = {
            'timestamp': int(time.time()) + 1000,
            'squad': self.squad,
            'mode': 'k/d',
            'leaderboard': [
                {'player': self.player, 'place_candidate': 1, 'kills': 10, 'deaths': 20},
                {'player': self.player, 'place_candidate': 2, 'kills': 5, 'deaths': 15},
            ]
        }
        self.client.force_login(self.account)
        response = self.client.get(reverse('squads'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['squads'][0]['upcoming_player_of_the_week'])
        self.assertEqual(len(response.context['squads'][0]['upcoming_player_of_the_week']['leaderboard']), 2)
        self.assertEqual(response.context['squads'][0]['upcoming_player_of_the_week_mode'].id, 'k/d')


class split_into_chunks(TestCase):

    def test_split_into_chunks(self):
        # Test case 1: data length is divisible by n
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        n = 5
        expected_result = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]]
        result = views.split_into_chunks(data, n)
        self.assertEqual(result, expected_result)

        # Test case 2: data length is not divisible by n
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        n = 4
        expected_result = [[1, 2, 3, 4], [5, 6, 7, 8], [9]]
        result = views.split_into_chunks(data, n)
        self.assertEqual(result, expected_result)

        # Test case 3: data length is less than n
        data = [1, 2, 3]
        n = 5
        expected_result = [[1, 2, 3]]
        result = views.split_into_chunks(data, n)
        self.assertEqual(result, expected_result)

        # Test case 4: data length is equal to n
        data = [1, 2, 3, 4, 5]
        n = 5
        expected_result = [[1, 2, 3, 4, 5]]
        result = views.split_into_chunks(data, n)
        self.assertEqual(result, expected_result)


class matches(TestCase):
    
    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.factory = RequestFactory()
        self.player = SteamProfile.objects.create(steamid='12345678900000001')
        self.squad = Squad.objects.create(name='Test Squad')
        self.squad.members.add(self.player)
        self.account = Account.objects.create(steam_profile=self.player)
        self.session = models.GamingSession.objects.create(squad=self.squad)
        self.match = models.Match.objects.create(timestamp=int(time.time()), score_team1=12, score_team2=13, duration=1653, map_name='de_dust2')
        self.match.sessions.add(self.session)
        self.participation = models.MatchParticipation.objects.create(player=self.player, pmatch=self.match, position=0, team=1, result=0, kills=20, assists=10, deaths=15, score=30, mvps=5, headshots=15, adr=120.5)

    def test_matches_with_squad(self):
        response = self.client.get(reverse('matches', kwargs={'squad': self.squad.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/sessions.html')
        self.assertEqual(response.context['squad'], self.squad.uuid)
        self.assertEqual(response.context['sessions'].count(), 1)
        self.assertEqual(response.context['sessions'][0], self.session)

    def test_matches_without_squad(self):
        self.client.force_login(self.account)
        response = self.client.get(reverse('matches'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/sessions.html')
        self.assertEqual(response.context.get('squad'), None)
        self.assertEqual(response.context['sessions'].count(), 1)
        self.assertEqual(response.context['sessions'][0], self.session)

    def test_matches_with_last_timestamp(self):
        # There should be no session older than the match
        last_timestamp = self.match.timestamp
        self.client.force_login(self.account)
        response = self.client.get(reverse('matches', kwargs={'last_timestamp': last_timestamp}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/sessions-list.html')
        self.assertIsNone(response.context['last_timestamp'])
        self.assertEqual(response.context['sessions'].count(), 0)

        # But there should be a session with a timestamp newer than the match
        last_timestamp = self.match.timestamp + 60 * 60
        self.client.force_login(self.account)
        response = self.client.get(reverse('matches', kwargs={'last_timestamp': last_timestamp}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/sessions-list.html')
        self.assertEqual(response.context['last_timestamp'], self.match.timestamp)
        self.assertEqual(response.context['sessions'].count(), 1)

    def test_matches_without_authentication(self):
        response = self.client.get(reverse('matches'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))


class run_pending_tasks(TestCase):

    def test(self):
        from accounts.tests import Account__update_matches
        Account__update_matches__testcase = Account__update_matches()
        try:
            Account__update_matches__testcase.setUp()

            # Schedule 3 update tasks, 1st already completed, 2nd started (but interrupted)
            Account__update_matches__testcase.test()

            # Let each task fail
            with patch.object(models.UpdateTask, 'run', side_effect = ValueError) as mock_update_task_run:
                with self.assertLogs(updater.log, level='CRITICAL') as cm:
                    updater.run_pending_tasks()

            # Verify that updater repeats the interrupted task, and keeps running even after a failing task
            self.assertEqual(mock_update_task_run.call_count, 2)

            # Verify the logs
            self.assertEqual(len(cm.output), 2)
            self.assertIn('Failed to update stats.', cm.output[0])
            self.assertIn('Failed to update stats.', cm.output[1])

        finally:
            Account__update_matches__testcase.tearDown()


class UpdateTask__run(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.player = models.SteamProfile.objects.create(steamid = '12345678900000001')
        self.account = Account.objects.create(steam_profile = self.player, last_sharecode = 'xxx-sharecode-xxx')
        self.task = models.UpdateTask(account = self.account, scheduled_timestamp = datetime.datetime.timestamp(datetime.datetime(2024, 1, 1, 9, 00, 00)))
        self.assertFalse(self.task.completed)
        self.assertTrue(self.account.enabled)

    @patch('api.api.fetch_matches', side_effect = api.InvalidSharecodeError('12345678900000001', 'xxx-sharecode-xxx'))
    def test_invalid_sharecode_error(self, mock_api_fetch_matches):
        self.task.run()

        # Accounts with invalid `last_sharecode` should be disabled, because there is no point in retrying an update for an invalid sharecode
        self.assertFalse(self.account.enabled)

        # Verify that the task was completed (there is no point in repeating it)
        self.assertTrue(self.task.completed)

    @patch('api.api.fetch_matches', side_effect = ValueError)
    def test_fetch_matches_error(self, mock_api_fetch_matches):
        # Verify that the error is passed through (so it can be handled by `run_pending_tasks`, see the `run_pending_tasks` test)
        self.assertRaises(ValueError, self.task.run)

        # Verify that the task is not completed (can be repeated later, usually after a new task is scheduled)
        self.assertFalse(self.task.completed)

        # Verify that the account is still enabled
        self.assertTrue(self.account.enabled)

    @patch('api.api.fetch_matches', side_effect = ValueError)
    def test_disabled_account(self, mock_api_fetch_matches):
        self.account.enabled = False
        self.account.save()

        # Task should run without errors because account is disabled
        self.task.run()

        # Verify that the task was not actually processed
        self.assertEqual(mock_api_fetch_matches.call_count, 0)


class GamingSession__close(TestCase):
    
    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.player = SteamProfile.objects.create(steamid = '12345678900000001')
        self.squad = Squad.objects.create(name = 'Test Squad')
        self.squad.members.add(self.player)

        # Create a previously played session
        self.session1 = models.GamingSession.objects.create(squad = self.squad, is_closed = True)
        self.match1 = models.Match.objects.create(
            timestamp = int(time.time()) - 60 * 60 * 24 * 14,  # two weeks ago
            score_team1 = 12, score_team2 = 13,
            duration = 1653,
            map_name = 'de_dust2',
        )
        self.match1.sessions.add(self.session1)
        self.participation1 = models.MatchParticipation.objects.create(
            player = self.player,
            pmatch = self.match1,
            position = 0,
            team = 1,
            result = 0,
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120.5,
        )

        # Create a currently played session
        self.session2 = models.GamingSession.objects.create(squad = self.squad)
        self.match2 = models.Match.objects.create(
            timestamp = int(time.time()),
            score_team1 = 12, score_team2 = 13,
            duration = 1653,
            map_name = 'de_dust2',
        )
        self.match2.sessions.add(self.session2)
        self.participation2 = models.MatchParticipation.objects.create(
            player = self.player,
            pmatch = self.match2,
            position = 0,
            team = 1,
            result = 0,
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120.5,
        )

    def test_first_session(self):
        # Remove the previously played session
        self.session1.delete()
        self.match1.delete()
        self.participation1.delete()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Get the scheduled Discord notifcation
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.get()
        self.assertEqual(notification.squad.pk, self.squad.pk)

        # Verify the notification text
        text = notification.text
        pv = math.sqrt((20 / 15) * 120.5 / 100)
        self.assertIn(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> ±0.00% ({pv :.2f}), with respect to the *player value*.',
            text,
        )

    def test_constant_kpi(self):
        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Get the scheduled Discord notifcation
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.get()
        self.assertEqual(notification.squad.pk, self.squad.pk)

        # Verify the notification text
        text = notification.text
        pv = math.sqrt((20 / 15) * 120.5 / 100)
        self.assertIn(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> ±0.00% ({pv :.2f}), with respect to the *player value*.',
            text,
        )

    def test_increasing_kpi(self):
        # Increase the KPI
        self.participation2.adr = 140
        self.participation2.save()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Get the scheduled Discord notifcation
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.get()
        self.assertEqual(notification.squad.pk, self.squad.pk)

        # Verify the notification text
        text = notification.text
        pv_previous = math.sqrt((20 / 15) * 120.5 / 100)
        pv_today    = math.sqrt((20 / 15) * 140 / 100)
        pv_ref      = (pv_previous + pv_today) / 2
        self.assertIn(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> 📈 +{100 * (pv_today - pv_ref) / pv_ref :.1f}% ({pv_today :.2f}), with respect to the *player value*.',
            text,
        )