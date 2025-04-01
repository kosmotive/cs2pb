import datetime
import math
import pathlib
import time
import uuid
from unittest.mock import (
    MagicMock,
    patch,
)

import cs2_client
from accounts.models import (
    Account,
    Squad,
    SquadMembership,
    SteamProfile,
)
from discordbot.models import ScheduledNotification
from stats import (
    models,
    potw,
    updater,
    views,
)
from tests import testsuite
from url_forward import get_redirect_url_to

from django.http import HttpResponseNotFound
from django.test import (
    RequestFactory,
    TestCase,
)
from django.urls import reverse


def create_kill_event(
        mp_killer: models.MatchParticipation,
        mp_victim: models.MatchParticipation,
        round: int = 1,
        kill_type: int = 0,
        bomb_planted: bool = False,
        killer_x: int = 0,
        killer_y: int = 0,
        killer_z: int = 0,
        victim_x: int = 0,
        victim_y: int = 0,
        victim_z: int = 0,
    ):
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


class Match__from_summary(TestCase):

    def test(self):
        pmatch_data = {
            'sharecode': 'CSGO-a622L-DjJDC-5zwn4-Gx2tf-YYmQD',
            'timestamp': 1720469310,
            'summary': dict(
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
        pmatch = models.Match.from_summary(pmatch_data)

        self.assertEqual(pmatch.sharecode, pmatch_data['sharecode'])
        self.assertEqual(pmatch.timestamp, pmatch_data['timestamp'])
        self.assertEqual(pmatch.score_team1, pmatch_data['summary']['team_scores'][0])
        self.assertEqual(pmatch.score_team2, pmatch_data['summary']['team_scores'][1])
        self.assertEqual(pmatch.duration, pmatch_data['summary']['match_duration'])
        self.assertEqual(pmatch.map_name, 'de_vertigo')
        self.assertEqual(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').kills, 17)
        self.assertEqual(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').deaths, 15)
        self.assertEqual(round(pmatch.matchparticipation_set.get(player__steamid = '76561197967680028').adr, 1), 104.7)

        return pmatch


class Match__award_badges(TestCase):

    def test(self):
        pmatch = Match__from_summary().test()
        self.assertEqual(
            list(
                models.MatchBadge.objects.filter(
                    participation = pmatch.get_participation('76561199034015511'),
                )
            ),
            [
                models.MatchBadge(
                    badge_type = models.MatchBadgeType.objects.get(pk = 'quad-kill'),
                    participation = pmatch.get_participation('76561199034015511'),
                    frequency = 1,
                )
            ]
        )
        self.assertEqual(
            list(
                models.MatchBadge.objects.filter(
                    participation = pmatch.get_participation('76561198298259382'),
                )
            ),
            [
                models.MatchBadge(
                    badge_type = models.MatchBadgeType.objects.get(pk = 'quad-kill'),
                    participation = pmatch.get_participation('76561198298259382'),
                    frequency = 1,
                )
            ]
        )
        self.assertEqual(
            list(
                models.MatchBadge.objects.filter(
                    participation = pmatch.get_participation('76561197962477966'),
                )
            ),
            [
                models.MatchBadge(
                    badge_type = models.MatchBadgeType.objects.get(pk = 'peach'),
                    participation = pmatch.get_participation('76561197962477966'),
                    frequency = 1,
                )
            ]
        )


class MatchBadge__award(TestCase):

    def setUp(self):
        with patch('stats.models.Match.award_badges'):
            self.pmatch = Match__from_summary().test()
        self.mp5 = self.pmatch.get_participation('76561197962477966')
        self.teammates = list(
            self.mp5.pmatch.matchparticipation_set.filter(
                team = self.mp5.team,
            ).exclude(
                pk = self.mp5.pk,
            ).order_by('-adr')
        )

    def test_no_awards(self):
        participation = self.pmatch.get_participation('76561197967680028')
        models.MatchBadge.award(participation)
        self.assertEqual(len(models.MatchBadge.objects.filter(participation = participation)), 0)

    def test_quad_kill(self):
        mp1 = self.pmatch.get_participation('76561197967680028')
        mp2 = self.pmatch.get_participation('76561197961345487')
        models.KillEvent.objects.all().delete()
        models.KillEvent.objects.bulk_create(
            [
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
                create_kill_event(mp1, mp2, round = 1),
            ]
        )
        # Test twice. The badge should be awarded only once.
        for itr in range(2):
            with self.subTest(itr = itr):
                models.MatchBadge.award(mp1)
                self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'quad-kill')), 1)
                badge = models.MatchBadge.objects.filter(badge_type = 'quad-kill').get()
                self.assertEqual(badge.participation.pk, mp1.pk)
                self.assertEqual(badge.frequency, 1)

    def test_quad_kill_twice(self):
        mp1 = self.pmatch.get_participation('76561197967680028')
        mp2 = self.pmatch.get_participation('76561197961345487')
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
        models.MatchBadge.award(mp1)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'quad-kill')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'quad-kill').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)

    def test_ace(self):
        mp1 = self.pmatch.get_participation('76561197967680028')
        mp2 = self.pmatch.get_participation('76561197961345487')
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
        models.MatchBadge.award(mp1)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'ace')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_ace_twice(self):
        mp1 = self.pmatch.get_participation('76561197967680028')
        mp2 = self.pmatch.get_participation('76561197961345487')
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
        models.MatchBadge.award(mp1)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'ace')), 1)
        badge = models.MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)

    def test_carrier_badge(self):
        mp1 = self.pmatch.get_participation('76561197967680028')
        mp2 = self.pmatch.get_participation('76561197961345487')

        # Test with ADR right below the threshold
        mp1.adr = 1.79 * mp2.adr
        mp1.save()
        models.MatchBadge.award(mp1)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'carrier', participation = mp1)), 0)

        # Test with ADR right above the threshold
        mp1.adr = 1.81 * mp2.adr
        mp1.save()
        for itr in range(2):  # Test twice, the badge should be awarded only once
            with self.subTest(itr = itr):
                models.MatchBadge.award(mp1)
                self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'carrier', participation = mp1)), 1)

    def test_peach_price__within_bounds(self):
        """
        Test the 🍑 Peach Price when the constraints ✅ "ADR <50" and ✅ "K/D <0.5" are met.
        """
        for mp in self.teammates:
            mp.adr = 50
            mp.save()
        self.mp5.kills = 1
        self.mp5.deaths = 3

        # Test with ADR right above the threshold
        self.mp5.adr = 0.68 * self.teammates[-1].adr
        self.mp5.save()
        models.MatchBadge.award(self.mp5)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = self.mp5)), 0)

        # Test with ADR right below the threshold
        self.mp5.adr = 0.66 * self.teammates[-1].adr
        self.mp5.save()
        for itr in range(2):  # Test twice, the badge should be awarded only once
            with self.subTest(itr = itr):
                models.MatchBadge.award(self.mp5)
                self.assertEqual(
                    len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = self.mp5)), 1,
                )

    def test_peach_price__kd_too_high(self):
        """
        Test the 🍑 Peach Price when the constraint ✅ "ADR <50" is met but ❌ "K/D <0.5" is not.
        """
        for mp in self.teammates:
            mp.adr = 50
            mp.save()
        self.mp5.kills = 2
        self.mp5.deaths = 3

        # Test with ADR right below the threshold
        self.mp5.adr = 0.66 * self.teammates[-1].adr
        self.mp5.save()
        models.MatchBadge.award(self.mp5)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = self.mp5)), 1)

    def test_peach_price__adr_too_high(self):
        """
        Test the 🍑 Peach Price when the constraint ✅ "K/D <0.5" is met but ❌ "ADR <50" is not.
        """
        for mp in self.teammates:
            mp.adr = 100
            mp.save()
        self.mp5.kills = 1
        self.mp5.deaths = 3

        # Test with ADR right below the threshold
        self.mp5.adr = 0.66 * self.teammates[-1].adr
        self.mp5.save()
        models.MatchBadge.award(self.mp5)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = self.mp5)), 1)

    def test_peach_price__kd_and_adr_too_high(self):
        """
        Test the 🍑 Peach Price when the constraint ❌ "ADR <50" and ❌ "K/D <0.5" both are not met.
        """
        for mp in self.teammates:
            mp.adr = 100
            mp.save()
        self.mp5.kills = 2
        self.mp5.deaths = 3

        # Test with ADR right below the threshold
        self.mp5.adr = 0.66 * self.teammates[-1].adr
        self.mp5.save()
        models.MatchBadge.award(self.mp5)
        self.assertEqual(len(models.MatchBadge.objects.filter(badge_type = 'peach', participation = self.mp5)), 0)


class MatchBadge__award_with_history(TestCase):

    def test_no_awards(self):
        pmatch = Match__from_summary().test()
        participation = pmatch.get_participation('76561197967680028')
        models.MatchBadge.award_with_history(participation, list())
        self.assertEqual(len(models.MatchBadge.objects.filter(participation = participation)), 0)


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
            'message': 'Minor layout improvements',
            'url': get_redirect_url_to(
                'https://github.com/kodikit/cs2pb/commits/9074a7a848a6ac74ba729757e1b2a4a971586190',
            ),
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
        squad = Squad.objects.create(
            name = 'squad',
            last_changelog_announcement = Squad__do_changelog_announcements.changelog[-1]['sha'],
        )
        squad.do_changelog_announcements(changelog = Squad__do_changelog_announcements.changelog)
        self.assertEqual(len(ScheduledNotification.objects.all()), 0)

    def test(self):
        squad = Squad.objects.create(
            name = 'squad',
            discord_channel_id = 'xxx',
            last_changelog_announcement = Squad__do_changelog_announcements.changelog[-1]['sha'],
        )
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

    @testsuite.fake_api.patch
    def setUp(self):
        self.squad = Squad.objects.create(name = 'squad', discord_channel_id = '1234')
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
            SquadMembership.objects.create(squad = self.squad, player = player)

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
        models.PlayerOfTheWeek.create_badge(data1)
        data2 = models.PlayerOfTheWeek.get_next_badge_data(self.squad)
        self.assertEqual(data2['mode'], potw.mode_cycle[1].id)
        self.assertEqual(data2['week'], 2)
        self.assertEqual(data2['year'], 1970)


class PlayerOfTheWeek__create_badge(TestCase):

    @testsuite.fake_api.patch
    def test(self):
        get_next_badge_data = PlayerOfTheWeek__get_next_badge_data()
        get_next_badge_data.setUp()
        data = get_next_badge_data.test_kd_challenge()
        get_next_badge_data.tearDown()
        badge = models.PlayerOfTheWeek.create_badge(data)
        self.assertEqual(badge.mode, 'k/d')
        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        self.assertIn(potw.get_mode_by_id(badge.mode).name, ScheduledNotification.objects.get().text)


@patch('accounts.models.SteamProfile.update_cached_avatar')
class squads(TestCase):

    @testsuite.fake_api.patch
    def setUp(self):
        self.factory = RequestFactory()
        self.player = SteamProfile.objects.create(steamid='12345678900000001')
        self.squad = Squad.objects.create(name='Test Squad')
        SquadMembership.objects.create(squad = self.squad, player = self.player)
        self.account = Account.objects.create(steam_profile=self.player)

    def test_squads_with_valid_squad(self, mock__SteamProfile__update_cached_avatar):
        response = self.client.get(reverse('squads', kwargs={'squad': self.squad.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['squad'], self.squad)
        mock__SteamProfile__update_cached_avatar.assert_called_once()

    def test_squads_with_invalid_squad(self, mock__SteamProfile__update_cached_avatar):
        invalid_uuid = str(uuid.uuid4())
        response = self.client.get(reverse('squads', kwargs={'squad': invalid_uuid}))
        self.assertIsInstance(response, HttpResponseNotFound)
        mock__SteamProfile__update_cached_avatar.assert_not_called()

    def test_squads_with_authenticated_user(self, mock__SteamProfile__update_cached_avatar):
        self.client.force_login(self.account)
        response = self.client.get(reverse('squads'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['squads']), 1)
        self.assertEqual(response.context['squads'][0]['name'], self.squad.name)
        mock__SteamProfile__update_cached_avatar.assert_called_once()

    def test_squads_with_unauthenticated_user(self, mock__SteamProfile__update_cached_avatar):
        response = self.client.get(reverse('squads'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        mock__SteamProfile__update_cached_avatar.assert_not_called()

    @patch('stats.views.PlayerOfTheWeek.get_next_badge_data')
    def test_squads_with_upcoming_potw(self, mock_get_next_badge_data, mock__SteamProfile__update_cached_avatar):
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
        mock__SteamProfile__update_cached_avatar.assert_called_once()


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

    @testsuite.fake_api.patch
    def setUp(self):
        self.factory = RequestFactory()
        self.player = SteamProfile.objects.create(steamid = '12345678900000001')
        self.squad = Squad.objects.create(name = 'Test Squad')
        SquadMembership.objects.create(squad = self.squad, player = self.player)
        self.account = Account.objects.create(steam_profile = self.player)
        self.session = models.GamingSession.objects.create(squad = self.squad)
        self.match = models.Match.objects.create(
            timestamp = int(time.time()),
            score_team1 = 12,
            score_team2 = 13,
            duration = 1653,
            map_name = 'de_dust2',
        )
        self.match.sessions.add(self.session)
        self.participation = models.MatchParticipation.objects.create(
            player = self.player,
            pmatch = self.match,
            team = 1,
            result = 'l',
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120.5,
        )

    def test_matches_with_squad(self):
        response = self.client.get(reverse('matches', kwargs={'squad': self.squad.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stats/sessions.html')
        self.assertEqual(response.context['squad'], self.squad)
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
            with patch.object(models.UpdateTask, 'run', side_effect = cs2_client.ClientError) as mock_update_task_run:
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

    @testsuite.fake_api.patch
    def setUp(self):
        self.player = models.SteamProfile.objects.create(steamid = '12345678900000001')
        self.account = Account.objects.create(steam_profile = self.player, last_sharecode = 'xxx-sharecode-xxx')
        self.task = models.UpdateTask(
            account = self.account,
            scheduling_timestamp = datetime.datetime.timestamp(datetime.datetime(2024, 1, 1, 9, 00, 00)),
        )
        self.assertFalse(self.task.completion_datetime)
        self.assertTrue(self.account.enabled)

    @patch.object(models.settings, 'CSGO_API_ENABLED', True)
    @patch(
        'cs2_client.fetch_matches',
        side_effect = cs2_client.InvalidSharecodeError('12345678900000001', 'xxx-sharecode-xxx'),
    )
    def test_invalid_sharecode_error(self, mock_cs2_client_fetch_matches):
        self.task.run(recent_matches = list())

        # Accounts with invalid `last_sharecode` should be disabled, because there is no point in retrying an update
        # for an invalid sharecode
        self.assertFalse(self.account.enabled)

        # Verify that the task was completed (there is no point in repeating it)
        self.assertTrue(self.task.completion_datetime)

    @patch.object(models.settings, 'CSGO_API_ENABLED', True)
    @patch('cs2_client.fetch_matches', side_effect = cs2_client.ClientError)
    def test_fetch_matches_error(self, mock_cs2_client_fetch_matches):
        # Verify that the error is passed through (so it can be handled by `run_pending_tasks`, see the
        # `run_pending_tasks` test)
        with self.assertRaises(cs2_client.ClientError):
            self.task.run(recent_matches = list())

        # Verify that the task is not completed (can be repeated later, usually after a new task is scheduled)
        self.assertFalse(self.task.completion_datetime)

        # Verify that the account is still enabled
        self.assertTrue(self.account.enabled)

    @patch('cs2_client.fetch_matches')
    def test_disabled_account(self, mock_cs2_client_fetch_matches):
        self.account.enabled = False
        self.account.save()

        # Task should run without errors because account is disabled
        self.task.run(recent_matches = list())

        # Verify that the task was not actually processed
        self.assertEqual(mock_cs2_client_fetch_matches.call_count, 0)

    @patch.object(models.settings, 'CSGO_API_ENABLED', True)
    @patch('cs2_client.fetch_matches')
    @patch('stats.models.Match.from_summary')
    @patch('stats.models.MatchBadge.award_with_history')
    @patch('accounts.models.SteamProfile.find_oldest_sharecode', return_value = 'xxx-sharecode-xxx')
    def test_initial_update(
        self,
        mock_SteamProfile_find_oldest_sharecode,
        mock_MatchBadge_award_with_history,
        mock_Match_from_summary,
        mock_cs2_client_fetch_matches,
    ):
        """
        Test the initial update for an account (no prior matches) that yields a new match.
        """
        # Establish preconditions
        self.account.last_sharecode = ''
        self.account.save()
        mock_Match_from_summary_ret = MagicMock()
        mock_Match_from_summary_ret.sharecode = 'xxx-sharecode-xxx'
        mock_Match_from_summary_ret.timestamp = 3000
        mock_Match_from_summary.return_value = mock_Match_from_summary_ret
        mock_cs2_client_fetch_matches.return_value = [
            dict(sharecode = mock_Match_from_summary_ret.sharecode),
        ]

        # Task should run without errors
        with patch.object(self.account, 'handle_finished_update') as mock_account_handle_finished_update:
            self.task.run(recent_matches = list())

        # Verify that `cs2_client.fetch_matches` was called correctly
        mock_cs2_client_fetch_matches.assert_called_once_with(
            self.account.sharecode,
            cs2_client.SteamAPIUser(self.account.steamid, self.account.steam_auth),
            list(),
            skip_first = False,
        )

        # Verify that `Match.from_summary` was called correctly
        mock_Match_from_summary.assert_called_once_with(
            mock_cs2_client_fetch_matches.return_value[0],
        )

        # Verify that `MatchBadge.award_with_history` was called correctly
        mock_MatchBadge_award_with_history.assert_called_once_with(
            mock_Match_from_summary.return_value.get_participation(self.account.steam_profile),
            list(),
        )

        # Verify that `account.handle_finished_update` was called correctly
        mock_account_handle_finished_update.assert_called_once_with()

        # Verify that the state of the account was updated correctly
        self.assertEqual(self.account.last_sharecode, mock_cs2_client_fetch_matches.return_value[0]['sharecode'])

    @patch.object(models.settings, 'CSGO_API_ENABLED', True)
    @patch('cs2_client.fetch_matches')
    @patch('stats.models.Match.from_summary')
    @patch('stats.models.MatchBadge.award_with_history')
    def test_regular_update(
        self,
        mock_MatchBadge_award_with_history,
        mock_Match_from_summary,
        mock_cs2_client_fetch_matches,
    ):
        """
        Test a regular update (i.e. for an account with prior matches) that yields no new matches.
        """
        # Establish preconditions
        pmatch = models.Match.objects.create(
            sharecode = 'xxx-sharecode-xxx',
            timestamp = 0,
            score_team1 = 12,
            score_team2 = 12,
            duration = 3000,
            map_name = 'de_dust2',
        )
        models.MatchParticipation.objects.create(
            player = self.account.steam_profile,
            pmatch = pmatch,
            team = 1,
            result = 'l',
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120.5,
        )
        mock_cs2_client_fetch_matches.return_value = list()

        # Task should run without errors
        with patch.object(self.account, 'handle_finished_update') as mock_account_handle_finished_update:
            self.task.run(recent_matches = list())

        # Verify that `cs2_client.fetch_matches` was called correctly
        mock_cs2_client_fetch_matches.assert_called_once_with(
            pmatch.sharecode,
            cs2_client.SteamAPIUser(self.account.steamid, self.account.steam_auth),
            list(),
            skip_first = True,
        )

        # Verify that `Match.from_summary` and `MatchBadge.award_with_history` were not called
        mock_Match_from_summary.assert_not_called()
        mock_MatchBadge_award_with_history.assert_not_called()

        # Verify that `account.handle_finished_update` was called correctly
        mock_account_handle_finished_update.assert_called_once_with()

        # Verify that the state of the account remains correct
        self.assertEqual(self.account.last_sharecode, pmatch.sharecode)

    @patch.object(models.settings, 'CSGO_API_ENABLED', True)
    @patch('cs2_client.fetch_matches')
    @patch('stats.models.Match.from_summary')
    @patch('stats.models.MatchBadge.award_with_history')
    def test_regular_update_with_recent_matches(
        self,
        mock_MatchBadge_award_with_history,
        mock_Match_from_summary,
        mock_cs2_client_fetch_matches,
    ):
        """
        Test a regular update (i.e. for an account with prior matches) that yields a recent match.
        """
        # Establish preconditions
        pmatch_previous = models.Match.objects.create(
            sharecode = 'xxx-sharecode-xxx',
            timestamp = 0,
            score_team1 = 12,
            score_team2 = 12,
            duration = 3000,
            map_name = 'de_dust2',
        )
        pmatch_recent = models.Match.objects.create(
            sharecode = 'xxx-sharecode-recent',
            timestamp = 5000,
            score_team1 = 12,
            score_team2 = 12,
            duration = 3000,
            map_name = 'de_inferno',
        )
        for pmatch in (pmatch_previous, pmatch_recent):
            models.MatchParticipation.objects.create(
                player = self.account.steam_profile,
                pmatch = pmatch,
                team = 1,
                result = 'l',
                kills = 20,
                assists = 10,
                deaths = 15,
                score = 30,
                mvps = 5,
                headshots = 15,
                adr = 120.5,
            )
        mock_cs2_client_fetch_matches.return_value = [
            pmatch_recent,
        ]

        # Task should run without errors
        with patch.object(self.account, 'handle_finished_update') as mock_account_handle_finished_update:
            self.task.run(recent_matches = [pmatch_recent])

        # Verify that `cs2_client.fetch_matches` was called correctly
        mock_cs2_client_fetch_matches.assert_called_once_with(
            pmatch_previous.sharecode,
            cs2_client.SteamAPIUser(self.account.steamid, self.account.steam_auth),
            [pmatch_recent],
            skip_first = True,
        )

        # Verify that `Match.from_summary` was not called
        mock_Match_from_summary.assert_not_called()

        # Verify that `MatchBadge.award_with_history` was called correctly
        mock_MatchBadge_award_with_history.assert_called_once_with(
            pmatch_recent.get_participation(self.account.steam_profile),
            [pmatch_previous.get_participation(self.account.steam_profile)],
        )

        # Verify that `account.handle_finished_update` was called correctly
        mock_account_handle_finished_update.assert_called_once_with()

        # Verify that the state of the account was updated correctly
        self.assertEqual(self.account.last_sharecode, pmatch_recent.sharecode)


class GamingSession(TestCase):

    def setUp(self):
        self.squad = Squad.objects.create(name = 'Test Squad', discord_channel_id = '1234')
        self.session = models.GamingSession.objects.create(squad = self.squad)
        self.matches = [
            models.Match.objects.create(
                sharecode = f'xxx-{midx}',
                timestamp = timestamp,
                score_team1 = 12,
                score_team2 = 12,
                duration = 3000,
                map_name = 'de_dust2',
            )
            for midx, timestamp in enumerate([10, 3600])
        ]
        for m in self.matches:
            m.sessions.add(self.session)

    def test__first_match(self):
        self.assertEqual(self.session.first_match, self.matches[0])

    def test__last_match(self):
        self.assertEqual(self.session.last_match, self.matches[-1])

    def test__started(self):
        self.assertEqual(self.session.started, 10)

    def test__ended(self):
        self.assertEqual(self.session.ended, 6600)

    def test__started_datetime(self):
        self.assertEqual(self.session.started_date_and_time, 'Jan 1, 1970, 01:00')

    def test__ended_datetime(self):
        self.assertEqual(self.session.ended_date_and_time, 'Jan 1, 1970, 02:50')

    def test__started_time(self):
        self.assertEqual(self.session.started_time, '01:00')

    def test__ended_time(self):
        self.assertEqual(self.session.ended_time, '02:50')

    def test__started_weekday(self):
        self.assertEqual(self.session.started_weekday, 'Thursday')

    def test__started_weekday_short(self):
        self.assertEqual(self.session.started_weekday_short, 'Thu')


class GamingSession__close(TestCase):

    @testsuite.fake_api.patch
    def setUp(self):
        self.player1 = SteamProfile.objects.create(steamid = '12345678900000001')
        self.player2 = SteamProfile.objects.create(steamid = '12345678900000002')
        self.squad = Squad.objects.create(name = 'Test Squad', discord_channel_id = '1234')
        SquadMembership.objects.create(squad = self.squad, player = self.player1)
        SquadMembership.objects.create(squad = self.squad, player = self.player2)

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
            player = self.player1,
            pmatch = self.match1,
            team = 1,
            result = 'l',
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
            player = self.player1,
            pmatch = self.match2,
            team = 1,
            result = 'l',
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
        self.squad.update_stats()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertIsNone(self.session2.rising_star)

        # Verify the scheduled Discord notifcation for player performance
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.all()[0]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        self.assertEqual(
            f'Looks like your session has ended!',
            notification.text,
        )

    def test_constant_kpi(self):
        self.squad.update_stats()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertIsNone(self.session2.rising_star)

        # Verify the scheduled Discord notifcation for player performance
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.all()[0]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        pv = math.sqrt((20 / 15) * 120.5 / 100)
        self.assertEqual(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> ±0.00% ({pv :.2f}), with respect to the *player value*.',
            notification.text,
        )

    def test_increasing_kpi(self):
        self.squad.update_stats()

        # Increase the KPI
        self.participation2.adr = 140
        self.participation2.save()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertIsNone(self.session2.rising_star)

        # Verify the scheduled Discord notifcation for player performance
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.all()[0]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        pv_previous  = math.sqrt((20 / 15) * 120.5 / 100)
        pv_today     = math.sqrt((20 / 15) * 140 / 100)
        pv_trend_rel = (pv_today - pv_previous) / pv_previous
        self.assertEqual(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> 📈 +{100 * pv_trend_rel :.1f}% ({pv_today :.2f}), with respect to the *player value*.',
            notification.text,
        )

    def test_decreasing_kpi(self):
        self.squad.update_stats()

        # Decrease the KPI
        self.participation2.adr = 100
        self.participation2.save()

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertIsNone(self.session2.rising_star)

        # Verify the scheduled Discord notifcation for player performance
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 1)
        notification = ScheduledNotification.objects.all()[0]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        pv_previous = math.sqrt((20 / 15) * 120.5 / 100)
        pv_today    = math.sqrt((20 / 15) * 100 / 100)
        pv_trend_rel = (pv_today - pv_previous) / pv_previous
        self.assertEqual(
            f'Looks like your session has ended! Here is your current performance compared to your 30-days average:  '
            f'<12345678900000001> 📉 {100 * pv_trend_rel :.1f}% ({pv_today :.2f}), with respect to the *player value*.',
            notification.text,
        )

    def test_multiple_matches(self):
        self.squad.update_stats()

        # Add a second participant to the current session (teammate)
        self.participation3 = models.MatchParticipation.objects.create(
            player = self.player2,
            pmatch = self.match2,
            team = self.participation2.team,
            result = self.participation2.result,
            kills = 10,
            assists = 5,
            deaths = 10,
            score = 15,
            mvps = 3,
            headshots = 10,
            adr = 90,
        )

        # Create a second match in current session (won)
        match3 = models.Match.objects.create(
            timestamp = int(time.time()) - 2000,
            score_team1 = 13, score_team2 = 12,
            duration = 1653,
            map_name = 'de_inferno',
        )
        match3.sessions.add(self.session2)
        models.MatchParticipation.objects.create(
            player = self.player1,
            pmatch = match3,
            team = 1,
            result = 'w',
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120,
        )

        # Create a third match in current session (tie)
        match4 = models.Match.objects.create(
            timestamp = int(time.time()) - 4000,
            score_team1 = 12, score_team2 = 12,
            duration = 1653,
            map_name = 'de_anubis',
        )
        match4.sessions.add(self.session2)
        models.MatchParticipation.objects.create(
            player = self.player1,
            pmatch = match4,
            team = 1,
            result = 't',
            kills = 20,
            assists = 10,
            deaths = 15,
            score = 30,
            mvps = 5,
            headshots = 15,
            adr = 120,
        )

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertIsNone(self.session2.rising_star)

        # Verify the scheduled Discord notification for summary of played matches
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 2)
        notification = ScheduledNotification.objects.all()[1]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        self.assertEqual(
            notification.text,
            'Matches played in this session:\n'
            '- *de_anubis*, **12:12**\n'
            '- *de_inferno*, **13:12** won 🤘\n'
            '- *de_dust2*, **12:13** lost 💩',
        )

    def test_rising_star_without_avatar(self):
        self.squad.update_stats()

        # Increase the KPI
        self.participation2.adr = 140
        self.participation2.save()

        # Add a second participant to the current session (teammate)
        self.participation3 = models.MatchParticipation.objects.create(
            player = self.player2,
            pmatch = self.match2,
            team = self.participation2.team,
            result = self.participation2.result,
            kills = 10,
            assists = 5,
            deaths = 10,
            score = 15,
            mvps = 3,
            headshots = 10,
            adr = 90,
        )

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertEqual(self.session2.rising_star.pk, self.player1.pk)

        # Verify the scheduled Discord notification for the rising star
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 3)
        notification = ScheduledNotification.objects.all()[2]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        self.assertEqual(
            notification.text,
            f'And today\'s **rising star** was: 🌟 <12345678900000001>! '
            f'</stats/{self.squad.uuid}/12345678900000001>',
        )

        # Verify the radar plot
        attachment = notification.get_attachment()
        testsuite.assert_image_almost_equal(
            self,
            test_id = 'radarplot_without_avatar',
            actual = attachment,
            expected = 'tests/data/radarplot_without_avatar.png',
        )

    @patch('accounts.models.avatar_cache_filepath', pathlib.Path('tests/data/avatars'))
    def test_rising_star_with_avatar(self):
        self.squad.update_stats()

        # Increase the KPI
        self.participation2.adr = 140
        self.participation2.save()

        # Add a second participant to the current session (teammate)
        self.participation3 = models.MatchParticipation.objects.create(
            player = self.player2,
            pmatch = self.match2,
            team = self.participation2.team,
            result = self.participation2.result,
            kills = 10,
            assists = 5,
            deaths = 10,
            score = 15,
            mvps = 3,
            headshots = 10,
            adr = 90,
        )

        # Close the currently played session
        self.session2.close()
        self.assertTrue(self.session2.is_closed)

        # Verify the rising star
        self.assertEqual(self.session2.rising_star.pk, self.player1.pk)

        # Verify the scheduled Discord notification for the rising star
        self.assertGreaterEqual(len(ScheduledNotification.objects.all()), 3)
        notification = ScheduledNotification.objects.all()[2]
        self.assertEqual(notification.squad.pk, self.squad.pk)
        self.assertEqual(
            notification.text,
            f'And today\'s **rising star** was: 🌟 <12345678900000001>! '
            f'</stats/{self.squad.uuid}/12345678900000001>',
        )

        # Verify the radar plot
        attachment = notification.get_attachment()
        testsuite.assert_image_almost_equal(
            self,
            test_id = 'radarplot_with_avatar',
            actual = attachment,
            expected = 'tests/data/radarplot_with_avatar.png',
        )
