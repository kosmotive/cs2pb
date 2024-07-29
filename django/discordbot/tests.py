from asgiref.sync import sync_to_async, async_to_sync
import os
from types import SimpleNamespace

from django.test import TestCase

from accounts.models import Account, Squad, SteamProfile
from discordbot import bot as botimpl
from discordbot.models import ScheduledNotification
from tests import testsuite


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
            SimpleNamespace(name = 'discordname', discriminator = '', mention = '<@discordname>')
        ]

    def get_channel(self, channel_id):
        self.channels.setdefault(channel_id, Channel())
        return self.channels[channel_id]


assert not botimpl.enabled
botimpl.bot = FakeBot()


class bot(TestCase):

    @classmethod
    def setUpClass(cls):
        testsuite.fake_api.inject('accounts.models')

    @classmethod
    def tearDownClass(cls):
        testsuite.fake_api.restore('accounts.models')

    def setUp(self):
        self.user = SteamProfile.objects.create(steamid = '1234567890')
        self.account = Account.objects.create(steam_profile = self.user, discord_name = 'discordname')
        self.squad = Squad.objects.create(name='squad', discord_channel_id='1234')
        self.squad.members.add(self.user)

    def test_tick(self):
        ScheduledNotification.objects.create(squad = self.squad, text = f'Hello <1234567890>!')
        #_await(botimpl.tick)
        async_to_sync(botimpl.tick)()

        self.assertEqual(len(ScheduledNotification.objects.all()), 0)
        self.assertEqual(botimpl.bot.channels[1234].sent, [
            dict(
                content = f'Hello steamname!',
            )
        ])
#
#
#def _await(func, *args, **kwargs):
#    coro = asyncio.coroutine(func)
#    future = coro(*args, **kwargs)
#    loop = asyncio.get_event_loop()
#    loop.run_until_complete(future)
