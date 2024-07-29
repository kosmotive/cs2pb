from types import SimpleNamespace

from django.test import TestCase

from accounts.models import Squad
from stats.models import Match, MatchBadge, KillEvent, get_next_potw_mode as get_next_potw_mode_, potw_mode_cycle, PlayerOfTheWeek
from stats import views
from discordbot.models import ScheduledNotification
from tests import testsuite
from url_forward import get_redirect_url_to


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
        pmatch = Match.create_from_data(pmatch_data)

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
        MatchBadge.award(participation, list())
        self.assertEqual(len(MatchBadge.objects.all()), 0)

    def test_quad_kill(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        KillEvent.objects.all().delete()
        KillEvent.objects.bulk_create(
            [
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
            ]
        )
        MatchBadge.award(mp1, list())
        self.assertEqual(len(MatchBadge.objects.all()), 1)
        badge = MatchBadge.objects.filter(badge_type = 'quad-kill').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_quad_kill_twice(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        KillEvent.objects.all().delete()
        KillEvent.objects.bulk_create(
            [
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
            ]
        )
        MatchBadge.award(mp1, list())
        self.assertEqual(len(MatchBadge.objects.all()), 1)
        badge = MatchBadge.objects.filter(badge_type = 'quad-kill').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)

    def test_ace(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        KillEvent.objects.all().delete()
        KillEvent.objects.bulk_create(
            [
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
            ]
        )
        MatchBadge.award(mp1, list())
        self.assertEqual(len(MatchBadge.objects.all()), 1)
        badge = MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_ace(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        KillEvent.objects.all().delete()
        KillEvent.objects.bulk_create(
            [
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
            ]
        )
        MatchBadge.award(mp1, list())
        self.assertEqual(len(MatchBadge.objects.all()), 1)
        badge = MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 1)

    def test_ace_twice(self):
        pmatch = Match__create_from_data().test()
        mp1 = pmatch.get_participation('76561197967680028')
        mp2 = pmatch.get_participation('76561197961345487')
        KillEvent.objects.all().delete()
        KillEvent.objects.bulk_create(
            [
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 1, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
                KillEvent(killer = mp1, victim = mp2, round = 2, kill_type = 0, bomb_planted = False, killer_x = 0, killer_y = 0, killer_z = 0, victim_x = 0, victim_y = 0, victim_z = 0),
            ]
        )
        MatchBadge.award(mp1, list())
        self.assertEqual(len(MatchBadge.objects.all()), 1)
        badge = MatchBadge.objects.filter(badge_type = 'ace').get()
        self.assertEqual(badge.participation.pk, mp1.pk)
        self.assertEqual(badge.frequency, 2)


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
        self.assertEqual(len(ScheduledNotification.objects.all()), 0)
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
        self.assertEqual(len(ScheduledNotification.objects.all()), 0)
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
        self.assertEqual(get_next_potw_mode_(potw_mode_cycle[ 0].id), potw_mode_cycle[1])
        self.assertEqual(get_next_potw_mode_(potw_mode_cycle[-1].id), potw_mode_cycle[0])


if __name__ == '__main__':
    unittest.main()
