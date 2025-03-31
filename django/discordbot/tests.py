import unittest.mock
from types import SimpleNamespace

from accounts.models import (
    Account,
    Squad,
    SquadMembership,
    SteamProfile,
)
from asgiref.sync import (
    async_to_sync,
    sync_to_async,
)
from discordbot import bot as botimpl
from discordbot.models import ScheduledNotification
from tests import testsuite

from django.test import TestCase


class Channel:

    def __init__(self):
        self.sent = list()

    @sync_to_async
    def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeBot:

    def __init__(self):
        self.channels = dict()
        self.users = [
            SimpleNamespace(id = 9216784356, name = 'discordname1', discriminator = '', mention = '<@discordname1>')
        ]

    def get_channel(self, channel_id):
        self.channels.setdefault(channel_id, Channel())
        return self.channels[channel_id]

    def get_all_members(self):
        return self.users


assert not botimpl.enabled
botimpl.bot = FakeBot()


class bot(TestCase):

    @testsuite.fake_api()
    def setUp(self):
        """
        Sets up multiple users:
        - 12345678900000001 has a discord name
        - 12345678900000002 has no discord name
        - 12345678900000003 has as invalid discord name
        """
        self.users = [
            SteamProfile.objects.create(steamid = '12345678900000001'),
            SteamProfile.objects.create(steamid = '12345678900000002'),
            SteamProfile.objects.create(steamid = '12345678900000003'),
        ]
        self.accounts = [
            Account.objects.create(
                steam_profile = self.users[0],
                email_address = 'user1@test.com',
                discord_name  = 'discordname1',
            ),
            None,
            Account.objects.create(
                steam_profile = self.users[2],
                email_address = 'user3@test.com',
                discord_name  = 'invalid_discordname',
            ),
        ]
        self.squad = Squad.objects.create(name = 'squad', discord_channel_id = '1234')
        for user in self.users:
            SquadMembership.objects.create(squad = self.squad, player = user)

    @unittest.mock.patch('discordbot.bot.settings', dict(base_url = 'https://example.com'))
    def test_tick(self):
        ScheduledNotification.objects.create(
            squad = self.squad,
            text = (
                f'Correct mention: <12345678900000001> '
                f'No discord name: <12345678900000002> '
                f'Invalid discord name: <12345678900000003> '
                f'Test URL: </stats/bc29cf56-9415-4864-abc4-d8d7b7e11e53/12345678900000001>'
            ),
        )
        async_to_sync(botimpl.tick)()

        self.assertEqual(len(ScheduledNotification.objects.all()), 0)
        self.assertEqual(
            botimpl.bot.channels[1234].sent,
            [
                dict(
                    content = (
                        'Correct mention: <@discordname1> '
                        'No discord name: name-of-12345678900000002 '
                        'Invalid discord name: name-of-12345678900000003 '
                        'Test URL: https://example.com/stats/bc29cf56-9415-4864-abc4-d8d7b7e11e53/12345678900000001'
                    ),
                )
            ],
        )
