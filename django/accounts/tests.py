import datetime
from unittest.mock import patch
import threading

from django.test import TestCase

import accounts.forms, accounts.models
import stats.models
from tests import testsuite


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
    task.execution_timestamp = task.scheduled_timestamp
    task.save()


def _mark_task_as_completed(task, duration = datetime.timedelta(minutes = 2)):
    _mark_task_as_started(task)
    task.completed_timestamp = datetime.datetime.timestamp(task.scheduled + duration)
    task.save()


@patch('stats.updater.update_event.set', return_value=None) 
class Account__update_matches(TestCase):

    @testsuite.fake_api('accounts.models')
    def setUp(self):
        self.player = stats.models.SteamProfile.objects.create(steamid='12345678900000001')
        self.account = accounts.models.Account.objects.create(steam_profile=self.player)

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
        self.assertEqual(task1.scheduled, update1_datetime)

        # [9:02] Mark the task as completed (after two minutes)
        _mark_task_as_completed(task1)

        # [9:04] Try to schedule an update four minutes after the first one (should be prevented)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update1_datetime + datetime.timedelta(minutes = 4)
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 1)
        self.assertEqual(stats.models.UpdateTask.objects.get(account = self.account).scheduled, update1_datetime)

        # [9:06] Try to schedule an update six minutes after the first one (should be accepted)
        update2_datetime = update1_datetime + datetime.timedelta(minutes = 6)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update2_datetime
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 2)
        task2 = stats.models.UpdateTask.objects.filter(account = self.account).latest('scheduled_timestamp')
        self.assertEqual(task2.scheduled, update2_datetime)

        # [9:06] Mark the task as started
        _mark_task_as_started(task2)

        # [9:12] Try to schedule an update six minutes after the second one (should be accepted, even though previous is still running)
        update3_datetime = update2_datetime + datetime.timedelta(minutes = 6)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = update3_datetime
            mock_datetime.timestamp = timestamp
            self.account.update_matches()
        self.assertEqual(len(stats.models.UpdateTask.objects.filter(account = self.account)), 3)
        task3 = stats.models.UpdateTask.objects.filter(account = self.account).latest('scheduled_timestamp')
        self.assertEqual(task3.scheduled, update3_datetime)
