import datetime
from unittest.mock import patch

import accounts.forms
import accounts.models
import stats.features
import stats.models
from discordbot.models import ScheduledNotification
from tests import testsuite

from django.test import TestCase


class verify_discord_name(TestCase):

    def test_valid(self):
        self.assertTrue(accounts.forms.verify_discord_name('kostrykin'))
        self.assertTrue(accounts.forms.verify_discord_name('harle153'))
        self.assertTrue(accounts.forms.verify_discord_name('harle_153'))
        self.assertTrue(accounts.forms.verify_discord_name('_harle.153_'))
        self.assertTrue(accounts.forms.verify_discord_name('kk'))
        self.assertTrue(accounts.forms.verify_discord_name('k' * 32))

    def test_invalid_characters(self):
        self.assertFalse(accounts.forms.verify_discord_name('Kostrykin'))
        self.assertFalse(accounts.forms.verify_discord_name('kostrykin#8242'))

    def test_too_short(self):
        self.assertFalse(accounts.forms.verify_discord_name('k'))
        self.assertFalse(accounts.forms.verify_discord_name(''))

    def test_too_long(self):
        self.assertFalse(accounts.forms.verify_discord_name('k' * 33))


def _mark_task_as_started(task):
    task.execution_timestamp = task.scheduling_timestamp
    task.save()


def _mark_task_as_completed(task, duration = datetime.timedelta(minutes = 2)):
    _mark_task_as_started(task)
    task.completion_timestamp = datetime.datetime.timestamp(task.scheduling_datetime + duration)
    task.save()


@patch('stats.updater.update_event.set', return_value = None)
class Account__update_matches(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.player  = accounts.models.SteamProfile.objects.create(steamid = '12345678900000001')
        self.account = accounts.models.Account.objects.create(steam_profile = self.player)

    def test(self, mock_update_event_set):
        # [9:00] Schedule an update on 1.1.2024 at 9am
        timestamp = datetime.datetime.timestamp
        update1_datetime = datetime.datetime(2024, 1, 1, 9, 00, 00)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update1_datetime
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 1)
        task1 = stats.models.UpdateTask.objects.get(account = self.account)
        self.assertEqual(task1.scheduling_datetime, update1_datetime)

        # [9:02] Mark the task as completed (after two minutes)
        _mark_task_as_completed(task1)

        # [9:04] Try to schedule an update four minutes after the first one (should be prevented)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update1_datetime + datetime.timedelta(minutes = 4)
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 1)
        self.assertEqual(
            stats.models.UpdateTask.objects.get(account = self.account).scheduling_datetime, update1_datetime,
        )

        # [9:06] Try to schedule an update six minutes after the first one (should be accepted)
        update2_datetime = update1_datetime + datetime.timedelta(minutes = 6)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update2_datetime
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 2)
        task2 = stats.models.UpdateTask.objects.filter(account = self.account).latest('scheduling_timestamp')
        self.assertEqual(task2.scheduling_datetime, update2_datetime)

        # [9:06] Mark the task as started
        _mark_task_as_started(task2)

        # [9:12] Try to schedule an update six minutes after the second one
        # (should be accepted, even though previous is still running)
        update3_datetime = update2_datetime + datetime.timedelta(minutes = 6)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update3_datetime
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 3)
        task3 = stats.models.UpdateTask.objects.filter(account = self.account).latest('scheduling_timestamp')
        self.assertEqual(task3.scheduling_datetime, update3_datetime)


@patch('accounts.models.SquadMembership.update_stats')
class Squad__update_stats(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.players = [
            accounts.models.SteamProfile.objects.create(steamid = f'1234567890000000{pidx + 1}') for pidx in range(4)
        ]
        self.squad = accounts.models.Squad.objects.create(name = 'squad', discord_channel_id = '1234')
        for player in self.players:
            accounts.models.SquadMembership.objects.create(squad = self.squad, player = player)

    def update_position(self, player, position):
        m = self.squad.memberships.get(player = player)
        m.position = position
        m.save()

    def update_player_value(self, player, value):
        m = self.squad.memberships.get(player = player)
        m.stats['player_value'] = value
        m.save()

    def test_all_newcomers(self, mock__SquadMembership__update_stats):
        self.update_player_value(self.players[0], 0.9)
        self.update_player_value(self.players[1], 1.1)
        self.update_player_value(self.players[2], 0.8)
        self.update_player_value(self.players[3], 0.7)

        self.squad.update_stats()

        self.assertEqual(len(ScheduledNotification.objects.all()), 0)

        memberships = self.squad.memberships.all()
        self.assertEqual(memberships.get(player = self.players[0]).position, 1)
        self.assertEqual(memberships.get(player = self.players[1]).position, 0)
        self.assertEqual(memberships.get(player = self.players[2]).position, 2)
        self.assertEqual(memberships.get(player = self.players[3]).position, 3)

    def test_one_newcomer(self, mock__SquadMembership__update_stats):
        self.update_position(self.players[0], 1)
        self.update_position(self.players[1], 0)
        self.update_position(self.players[3], 2)

        self.update_player_value(self.players[0], 0.9)
        self.update_player_value(self.players[1], 1.1)
        self.update_player_value(self.players[2], 0.8)
        self.update_player_value(self.players[3], 0.7)

        self.squad.update_stats()

        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification_text = ScheduledNotification.objects.get().text
        self.assertEqual(
            notification_text,
            'We have changes in the 30-days leaderboard! 🎆' '\n'
            '\n'
            '1. <12345678900000002>' '\n'
            '2. <12345678900000001>' '\n'
            '3. <12345678900000003> 🆕' '\n'
            '4. <12345678900000004> ⬇️'
        )

        memberships = self.squad.memberships.all()
        self.assertEqual(memberships.get(player = self.players[0]).position, 1)
        self.assertEqual(memberships.get(player = self.players[1]).position, 0)
        self.assertEqual(memberships.get(player = self.players[2]).position, 2)
        self.assertEqual(memberships.get(player = self.players[3]).position, 3)

    def test_swap(self, mock__SquadMembership__update_stats):
        self.update_position(self.players[0], 0)
        self.update_position(self.players[1], 1)
        self.update_position(self.players[2], 2)
        self.update_position(self.players[3], 3)

        self.update_player_value(self.players[0], 0.9)
        self.update_player_value(self.players[1], 1.1)
        self.update_player_value(self.players[2], 0.8)
        self.update_player_value(self.players[3], 0.7)

        self.squad.update_stats()

        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification_text = ScheduledNotification.objects.get().text
        self.assertEqual(
            notification_text,
            'We have changes in the 30-days leaderboard! 🎆' '\n'
            '\n'
            '1. <12345678900000002> ⬆️' '\n'
            '2. <12345678900000001> ⬇️' '\n'
            '3. <12345678900000003>' '\n'
            '4. <12345678900000004>'
        )

        memberships = self.squad.memberships.all()
        self.assertEqual(memberships.get(player = self.players[0]).position, 1)
        self.assertEqual(memberships.get(player = self.players[1]).position, 0)
        self.assertEqual(memberships.get(player = self.players[2]).position, 2)
        self.assertEqual(memberships.get(player = self.players[3]).position, 3)

    def test_one_missing(self, mock__SquadMembership__update_stats):
        self.update_position(self.players[0], 0)
        self.update_position(self.players[1], 1)
        self.update_position(self.players[2], 2)

        self.update_player_value(self.players[0], 1.1)
        self.update_player_value(self.players[1], None)
        self.update_player_value(self.players[2], 0.8)
        self.update_player_value(self.players[3], None)

        self.squad.update_stats()

        self.assertEqual(len(ScheduledNotification.objects.all()), 1)
        notification_text = ScheduledNotification.objects.get().text
        self.assertEqual(
            notification_text,
            'We have changes in the 30-days leaderboard! 🎆' '\n'
            '\n'
            '1. <12345678900000001>' '\n'
            '2. <12345678900000003> ⬆️' '\n'
            '\n'
            '<12345678900000002> is no longer present 👋'
        )

        memberships = self.squad.memberships.all()
        self.assertEqual (memberships.get(player = self.players[0]).position, 0)
        self.assertIsNone(memberships.get(player = self.players[1]).position)
        self.assertEqual (memberships.get(player = self.players[2]).position, 1)
        self.assertIsNone(memberships.get(player = self.players[3]).position)
