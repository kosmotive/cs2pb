import asyncio
import json
import logging
import os

import discord
import discord.utils
from accounts.models import Squad
from asgiref.sync import sync_to_async
from discord.ext import commands
from discordbot.models import (
    InvitationDraft,
    ScheduledNotification,
)

log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix = '/', intents = intents)


@sync_to_async
def get_squad(channel_id = None, squad_id = None):
    assert channel_id or squad_id
    if squad_id is None:
        squads = Squad.objects.filter(discord_channel_id = channel_id)
        if len(squads) == 0:
            return None
        squad = squads.get()
    else:
        squad = Squad.objects.get(uuid = squad_id)
    squad.memberships_list = list(squad.memberships.all())
    return squad


@sync_to_async
def pop_scheduled_notifications(user_lookup):
    notifications_qs = ScheduledNotification.objects.order_by('-scheduling_timestamp')
    notifications = list(notifications_qs)
    result = []
    for n in notifications:
        data = dict(
            channel_id = n.squad.discord_channel_id,
            text       = n.resolve_text(user_lookup, settings),
            attachment = ScheduledNotification.get_attachment(n))
        result.append(data)
        n.delete()
    return result


@sync_to_async
def create_invitation(squad, discord_name):
    try:
        draft = InvitationDraft.objects.get(discord_name = discord_name)
        return draft.steam_profile.invite(squad, discord_name = discord_name)
    except InvitationDraft.ObjectDoesNotExist:
        log.info(f'No invitation draft for {discord_name}')
        return None


@sync_to_async
def calculate_preview_player_value(squad):
    current_session = squad.sessions.filter(is_closed = False).order_by('-id').first()
    if current_session:
        return current_session.calculate_preview_player_value()
    return None


class BotError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


async def tick():
    user_lookup = {user.name: user.mention for user in bot.users}.get
    new_notifications = await pop_scheduled_notifications(user_lookup)
    for n in new_notifications:
        if n['channel_id'] is None:
            continue
        channel = bot.get_channel(int(n['channel_id']))
        kwargs = dict(content = n['text'])
        if n['attachment'] is not None:
            kwargs['file'] = discord.File(n['attachment'], filename='stats.png')
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
            await ctx.response.send_message(
                f'Sorry bro, you are not on the list ¯\\_(ツ)_/¯' '\n'
                f'Type `/who_is_your_creator` and I\'ll tell you whom to ask.'
            )
        else:
            url = f'{settings["base_url"]}{invitation.url}'
            await ctx.response.send_message(f'This invitation is only for you ma friend:\n{url}', ephemeral = True)


@bot.tree.command(description='Credits')
async def who_is_your_creator(ctx):
    await ctx.response.send_message('The only and almighty, *TEH VOID OF THE AETHER!!1*'.upper())


@bot.tree.command(description='Preview your updated 30-days average player value based on current session.')
async def preview(ctx):
    squad = await get_squad(channel_id = ctx.channel_id)
    if squad is None:
        await ctx.response.send_message(f'No squad registered for this Discord channel')
    else:
        preview_value = await calculate_preview_player_value(squad)
        if preview_value is None:
            await ctx.response.send_message(f'No active session found or unable to calculate preview value.')
        else:
            await ctx.response.send_message(f'The preview of the updated 30-days average player value is: {preview_value:.2f}')


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
    settings = dict()
