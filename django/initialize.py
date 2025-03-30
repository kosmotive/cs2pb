#!/usr/bin/env python

import argparse
import subprocess
import sys
from getpass import getpass

parser = argparse.ArgumentParser()

parser.add_argument(
    '--steamid', action = 'store', type = str, help = 'Steam ID of the superuser account (used for log in).',
)
parser.add_argument(
    '--email', action = 'store', type = str, help = 'Mail address of the superuser (can be used for log in).',
)
parser.add_argument(
    '--discord', action = 'store', type = str, help = 'Initial Discord ID of the superuser account.',
)
parser.add_argument(
    '--sharecode', action = 'store', type = str, help = 'Initial sharecode of the superuser account.',
)
parser.add_argument(
    '--auth', action = 'store', type = str, help = 'Initial Steam Auth of the superuser account.',
)
parser.add_argument(
    '--squadname', action = 'store', type = str, help = 'Name of the squad of the superuser.',
)
parser.add_argument(
    '--discord-channel', action = 'store', type = str, help = 'Initial Discord channel ID of the squad.',
)
parser.add_argument(
    '--extra-steamids', nargs = '*', type = str, help = 'Steam IDs of users to be added as squad members.',
)

args = parser.parse_args()

steamid = args.steamid
if steamid is None:
    steamid = input('Steam ID of the superuser account (used for log in): ')

email = args.email
if email is None:
    email = input('Mail address of the superuser (can be used for log in): ')

discord = args.discord
if discord is None:
    discord = input('Initial Discord ID of the superuser account: ')

discord_channel = args.discord_channel
if discord_channel is None:
    discord_channel = input('Initial Discord channel ID of the squad: ')

sharecode = args.sharecode
if sharecode is None:
    sharecode = input('Initial sharecode of the superuser account: ')

auth = args.auth
if auth is None:
    auth = input('Initial Steam Auth of the superuser account: ')

squadname = args.squadname
if squadname is None:
    squadname = input('Name of the initial squad of the superuser: ')

extra_steamid_list = '[' + ', '.join((f"'{steamid}'" for steamid in args.extra_steamids)) + ']'

password = getpass('Superuser password: ')

subprocess.run(['python', 'manage.py', 'shell', '-c', f'''

from stats.models import Squad
from accounts.models import SteamProfile, SquadMembership

from django.contrib.auth import get_user_model
Account = get_user_model()
kwargs = dict(email_address='{email}', discord_name='{discord}')
if len('{sharecode}') > 0: kwargs['last_sharecode'] = '{sharecode}'
if len('{auth}') > 0: kwargs['steam_auth'] = '{auth}'

users = [Account.objects.create_superuser('{steamid}', '{password}', **kwargs).steam_profile]
for steamid in {extra_steamid_list}:
    users.append(SteamProfile.objects.create(steamid=steamid))

squad = Squad.objects.create(name='{squadname}', discord_channel_id='{discord_channel}')
for member in users:
    SquadMembership.objects.create(squad=squad, player=member)
squad.save()

'''], stdout = sys.stdout, stderr = sys.stderr)
