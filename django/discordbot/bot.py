import discord, discord.utils
import json
import asyncio
import logging
import re
import os

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async

from discord.ext import commands
from datetime import datetime

from accounts.models import Squad, SteamProfile
from discordbot.models import ScheduledNotification, InvitationDraft
from stats.models import MatchParticipation
from stats import plots
from stats.features import Features, FeatureContext


log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)


@sync_to_async
def get_squad(channel_id = None, squad_id = None):
    assert channel_id or squad_id
    if squad_id is None:
        squads = Squad.objects.filter(discord_channel_id = channel_id)
        if len(squads) == 0: return None
        squad = squads.get()
    else:
        squad = Squad.objects.get(uuid = squad_id)
    squad.members_list = list(squad.members.all())
    return squad


@sync_to_async
def pop_scheduled_notifications(user_lookup):
    notifications_qs = ScheduledNotification.objects.order_by('-scheduled_timestamp')
    notifications = list(notifications_qs)
    result = []
    for n in notifications:
        data = dict(
            channel_id = n.squad.discord_channel_id,
            text       = n.resolve_text(user_lookup),
            attachment = ScheduledNotification.get_attachment(n))
        result.append(data)
        n.delete()
    return result


@sync_to_async
def create_invitation(squad, discord_name):
    try:
        draft = InvitationDraft.objects.get(discord_name = discord_name)
        return draft.steam_profile.invite(squad, discord_name = discord_name)
    except ObjectDoesNotExist:
        log.info(f'No invitation draft for {discord_name}')
        return None


def get_or_none(qs, *args, **kwargs):
    try:
        return qs.get(*args, **kwargs)
    except ObjectDoesNotExist:
        return None


class BotError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class UnrecognizedNameError(BotError):

    def __init__(self, name):
        super().__init__(f'Failed to recognize name: {name}')
        self.name = name


class UnrecognizedFeatureError(BotError):

    def __init__(self, name):
        super().__init__(f'Failed to recognize feature: {name}')
        self.name = name


def get_features(features_add, features_remove):
    for feature in features_remove:
        if not hasattr(Features, feature):
            raise UnrecognizedFeatureError(feature)
    stats = [stat for stat in Features.MANY if stat.slug not in features_remove]
    for feature in features_add:
        if hasattr(Features, feature):
            stats.append(getattr(Features, feature))
        else:
            raise UnrecognizedFeatureError(feature)
    return stats


def recognize_name(squad, name): # name must be either full Discord name or Steam name
    qs = SteamProfile.objects.filter(squads = squad)
    player = get_or_none(qs, account__discord_name = name) or get_or_none(qs, name = name)
    if not player: raise UnrecognizedNameError(name)
    return player


@sync_to_async
def plot_stats(squad, name1, name2=None, features_add=[], features_remove=[], days=None, **filters): # names must be either full Discord names or Steam names
    log.info(f'Fetching stats for {name1}' + (f' and {name2}' if name2 is not None else ''))
    player1 = recognize_name(squad, name1)
    if name2 is not None:
        player2 = recognize_name(squad, name2)
        if player1.pk == player2.pk: player2 = None
    else:
        player2 = None
    features = get_features(features_add, features_remove)
    contexts = [FeatureContext.create_default(player1, squad, days, **filters)]
    labels   = [player1.clean_name]
    if player2 is not None:
        contexts.append(FeatureContext.create_default(player2, squad, days, **filters))
        labels  .append(player2.clean_name)
    return plots.radar(*contexts, features = features, labels = labels)


@sync_to_async
def plot_squad_stats(squad, features, days = None, **filters):
    features = get_features(features, [f.slug for f in Features.MANY])
    contexts, labels = [], []
    for m in squad.members.all():
        contexts.append(FeatureContext.create_default(m, squad, days, **filters))
        labels  .append(m.clean_name)
    return plots.bars(*contexts, features = features, labels = labels)


@sync_to_async
def plot_trends(squad, name, days, features_add=[], features_remove=[], **filters):
    log.info(f'Fetching trends for {name}')
    player    = recognize_name(squad, name)
    features  = get_features(features_add, features_remove)
    return plots.trends(squad, player, features, days, **filters)


async def tick():
    user_lookup = {user.name: user.mention for user in bot.users}.get
    new_notifications = await pop_scheduled_notifications(user_lookup)
    for n in new_notifications:
        if n['channel_id'] is None: continue
        channel = bot.get_channel(int(n['channel_id']))
        kwargs = dict(content = n['text'])
        if n['attachment'] is not None: kwargs['file'] = discord.File(n['attachment'], filename='stats.png')
        await channel.send(**kwargs)


@bot.event
async def on_ready():
    await bot.tree.sync()
    while True:
        await asyncio.gather(
            asyncio.sleep(tick_pause),
            tick(),
        )


@bot.tree.command(description='Requests the link to the web page.')
async def link(ctx):
    squad = await get_squad(channel_id = ctx.channel_id)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        url = f'{settings["base_url"]}{squad.url}'
        await ctx.response.send_message(f'Here is the link to the squad overview: {url}')


async def get_full_discord_name(user):
    # FIXME: some users might not have a `discord_name` set up in their profile,
    #        so it would be better to resolve to an abstract User object?
    return None if user is None else user.name


@bot.tree.command(description='Permits the bot to track your performance without gaps.')
async def join(ctx):
    squad = await get_squad(channel_id = ctx.channel_id)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        discord_name = await get_full_discord_name(ctx.user)
        invitation = await create_invitation(squad, discord_name)
        if invitation is None:
            await ctx.response.send_message(f'Sorry bro, you are not on the list ¯\\_(ツ)_/¯\nType `/who_is_your_creator` and I\'ll tell you whom to ask.')
        else:
            url = f'{settings["base_url"]}{invitation.url}'
            await ctx.response.send_message(f'This invitation is only for you ma friend:\n{url}', ephemeral=True)


mention_pattern = re.compile(r'^ *<@([0-9]+)> *$')


async def resolve_mention(token):
    """Resolves a token if it is a mention to the corresponding full Discord name.
    """
    if token is None: return None
    m = mention_pattern.match(token)
    if m is not None:
        user = discord.utils.get(bot.get_all_members(), id=int(m.group(1)))
        log.debug(f'Resolved "{token}" to {user.name}')
        return await get_full_discord_name(user)
    else:
        return token


add_feature_pattern    = re.compile(r'(?:^|[ ,])\+?([a-z]+)')
remove_feature_pattern = re.compile(r'(?:^|[ ,])-([a-z]+)')


@bot.tree.command(description='Show your stats or of any other player of the squad.')
@discord.app_commands.describe(squad   = 'The ID of the squad used to look up Steam profile names')
@discord.app_commands.describe(player1 = 'Mention, Discord name, or Steam profile name')
@discord.app_commands.describe(player2 = 'Mention, Discord name, or Steam profile name')
@discord.app_commands.describe(days    = 'The period of time to consider for the stats')
@discord.app_commands.describe(features = 'List of features to include or exclude (e.g, afbs -fbsr -kd)')
async def stats(ctx, squad:str=None, player1:str=None, player2:str=None, days:int=None, features:str=''):
    squad = await get_squad(channel_id = ctx.channel_id, squad_id = squad)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        name0  = await get_full_discord_name(ctx.user)
        name1  = await resolve_mention(player1)
        name2  = await resolve_mention(player2)
        kwargs = dict(
            features_add    = add_feature_pattern.findall(features),
            features_remove = remove_feature_pattern.findall(features),
            days = days,
        )
        try:
            if name1 and name2:
                result = await plot_stats(squad, name1, name2, **kwargs)
            elif name1:
                result = await plot_stats(squad, name1, name0, **kwargs)
            else:
                result = await plot_stats(squad, name0, **kwargs)
        except UnrecognizedNameError as ex:
            members = ', '.join([m.name for m in squad.members_list])
            await ctx.response.send_message(f'I didn\'t recognize the player `{ex.name}`. Either use mentions, Discord names including the discriminators, or Steam profile names, for example: {members}')
            return
        except UnrecognizedFeatureError as ex:
            features = '\n'.join([f'\n`{s.slug}`: **{s.name}**\n{s.description}' for s in Features.ALL])
            await ctx.response.send_message(f'I didn\'t recognize the feature `{ex.name}`. The following are available:\n{features}')
            return
        if result is None:
            await ctx.response.send_message(f'Insufficient data')
        else:
            await ctx.response.send_message(file=discord.File(result, filename='stats.png'))


@bot.tree.command(description='Show your trends or of any other player of the squad.')
@discord.app_commands.describe(squad   = 'The ID of the squad used to look up Steam profile names')
@discord.app_commands.describe(player  = 'Mention, Discord name, or Steam profile name')
@discord.app_commands.describe(days    = 'The period of time to consider for the stats')
@discord.app_commands.describe(features = 'List of features to include or exclude (e.g, afbs -fbsr -kd)')
async def trends(ctx, squad:str=None, player:str=None, days:int=None, features:str=''):
    squad = await get_squad(channel_id = ctx.channel_id, squad_id = squad)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        name   = await resolve_mention(player) if player else await get_full_discord_name(ctx.user)
        kwargs = dict(
            features_add    = add_feature_pattern.findall(features),
            features_remove = remove_feature_pattern.findall(features),
        )
        try:
            result = await plot_trends(squad, name, days, **kwargs)
        except UnrecognizedNameError as ex:
            members = ', '.join([m.name for m in squad.members_list])
            await ctx.response.send_message(f'I didn\'t recognize the player `{ex.name}`. Either use mentions, Discord names including the discriminators, or Steam profile names, for example: {members}')
            return
        except UnrecognizedFeatureError as ex:
            features = '\n'.join([f'\n`{s.slug}`: **{s.name}**\n{s.description}' for s in Features.ALL])
            await ctx.response.send_message(f'I didn\'t recognize the feature `{ex.name}`. The following are available:\n{features}')
            return
        if result is None:
            await ctx.response.send_message(f'Insufficient data')
        else:
            await ctx.response.send_message(file=discord.File(result, filename='stats.png'))


@bot.tree.command(description='Show the stats of the whole squad.')
@discord.app_commands.describe(features = 'List of features to include (e.g, kd, tc)')
@discord.app_commands.describe(squad   = 'The ID of the squad')
@discord.app_commands.describe(days    = 'The period of time to consider for the stats')
async def squadstats(ctx, features:str, squad:str=None, days:int=None):
    squad = await get_squad(channel_id = ctx.channel_id, squad_id = squad)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        features = add_feature_pattern.findall(features)
        try:
            result = await plot_squad_stats(squad, features, days)
        except UnrecognizedFeatureError as ex:
            features = '\n'.join([f'\n`{s.slug}`: **{s.name}**\n{s.description}' for s in Features.ALL])
            await ctx.response.send_message(f'I didn\'t recognize the feature `{ex.name}`. The following are available:\n{features}')
            return
        if result is None:
            await ctx.response.send_message(f'Insufficient data')
        else:
            await ctx.response.send_message(file=discord.File(result, filename='stats.png'))


@bot.tree.command(description='Credits')
async def who_is_your_creator(ctx):
    await ctx.response.send_message('The only and almighty, *the void of the Aether!!1*'.upper())


if os.environ.get('CS2PB_DISCORD_ENABLED', False):
    log.info(f'Discord integration enabled')
    enabled = True

    with open('discordbot/settings.json') as fin:
        settings = json.load(fin)

    for squad in Squad.objects.all():
        squad.do_changelog_announcements(base_url = settings['base_url'])

    tick_pause = 60 / int(settings['ticks_per_minute'])
    bot.run(settings['token'])

else:
    log.warning(f'Discord integration disabled')
    enabled = False
