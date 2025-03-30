import bz2
import logging
import os
import tempfile
import time
import traceback

import awpy
import awpy.data.map_data
import awpy_fork.stats
import dill
import gevent.exceptions
import numpy as np
import ratelimit
import requests
from csgo.client import CSGOClient
from csgo.sharecode import decode as decode_sharecode
from steam.client import SteamClient
from steam.core.connection import WebsocketConnection
from steam.steamid import SteamID

from django.conf import settings

STEAM_API_KEY = os.environ['CS2PB_STEAM_API_KEY']
assert len(STEAM_API_KEY) > 0

NAV_SUPPORTED_MAPS = frozenset(awpy.data.map_data.MAP_DATA.keys())

log = logging.getLogger(__name__)


def fetch_match_details(pmatch, max_retry_count = 4):
    for retry_idx in range(max_retry_count):
        time.sleep(retry_idx * 10)
        try:
            demo_url = pmatch['summary'].map
            demo = parse_demo(demo_url)

            # No need to retry (fetch was successful)
            break

        except:  # noqa: E722
            log.warning(traceback.format_exc())
            log.warning(f'Failed to fetch match details (attempt: {retry_idx + 1} / {max_retry_count})')

            if retry_idx + 1 == max_retry_count:
                raise InvalidDemoError(
                    sharecode = pmatch['sharecode'],
                    demo_url = demo_url,
                )

    # Fetch info from parsed demo
    pmatch['map'] = demo.header['map_name']
    pmatch['kills'] = demo.kills

    def get_damage(steam_id):
        try:
            return int(dmg_df.at[str(steam_id), 'dmg'])
        except KeyError:
            return 0

    dmg_df = awpy_fork.stats.dmg(demo)
    pmatch['dmg'] = {str(steam_id): get_damage(steam_id) for steam_id in pmatch['steam_ids']}

    # We avoid using `awpy.stats.adr` because this requires `ticks=True` for Demo parsing
    num_rounds = sum(pmatch['summary'].team_scores)
    pmatch['adr'] = {str(steam_id): get_damage(steam_id) / num_rounds for steam_id in pmatch['steam_ids']}


def _is_wingman_match(pmatch):
    """
    Deduce whether the match is a wingman match (2 on 2).

    In wingman matches, there are 5 players per team, but for 3 of them the steam ID is 0.
    We thus deduce whether the match is a wingman match by counting the occurances of 0 as the steam ID.
    """
    return (np.asarray(pmatch['steam_ids']) == 0).sum() == 6


def fetch_matches(first_sharecode, steamuser):
    with tempfile.NamedTemporaryFile() as ret_file:
        newpid = os.fork()
        if newpid == 0:
            # Execution inside the forked process
            matches = Client(api).fetch_matches(first_sharecode, steamuser)
            try:
                dill.dump(matches, ret_file)
                ret_file.flush()
                os._exit(0)
            except Exception as error:
                dill.dump(error, ret_file)
                ret_file.flush()
                os._exit(1)
        else:
            # Execution inside the parent process
            exit_code = os.waitpid(newpid, 0)[1]
            ret_file.seek(0)
            ret = dill.load(ret_file)
            if exit_code != 0:
                log.error(f'An error occurred while fetching matches')
                raise ClientError() from ret
            else:
                return ret


class Client:

    def __init__(self, api):
        self.api = api
        self.csgo = CSGOWrapper()

    def fetch_matches(self, first_sharecode, steamuser):
        log.debug(f'Fetching sharecodes (for Steam ID: {steamuser.steamid})')
        sharecodes = list(self.api.fetch_sharecodes(first_sharecode, steamuser))
        log.debug(f'Fetched: {first_sharecode} -> {sharecodes}')
        log.debug('Resolving sharecodes (fetching match data)')
        matches = self._resolve_sharecodes(sharecodes)
        log.debug('Resolving Steam IDs')
        matches = [
                dict(
                    sharecode = sharecode,
                    timestamp = pmatch.matchtime,
                    summary   = pmatch.roundstatsall[-1],
                    steam_ids = self._resolve_account_ids(pmatch.roundstatsall[-1].reservation.account_ids)
                )
                for sharecode, pmatch in zip(sharecodes, matches)
            ]
        log.debug(f'Fetched {len(matches)} match(es)')
        matches = [pmatch for pmatch in matches if not _is_wingman_match(pmatch)]
        log.debug(f'All matches fetched ({len(matches)})')
        return matches

    def _resolve_sharecodes(self, sharecodes):
        results = list()
        for sharecode in sharecodes:
            d = decode_sharecode(sharecode)
            log.debug('Requesting match info')
            while True:
                self.csgo.get().request_full_match_info(d['matchid'], d['outcomeid'], d['token'])
                log.debug('Waiting for match data')
                response = self.csgo.get().wait_event('full_match_info', 10)
                if response is not None:
                    break
                log.debug('Waiting for match data timed out, retrying')
            log.debug('Match data completed')
            results.append(response[0].matches[0])
        return results

    def _resolve_account_ids(self, account_ids):
        return [SteamID(int(account_id)).as_64 for account_id in account_ids]


class SteamAPIUser:

    def __init__(self, steamid, steamid_key):
        self.steamid = steamid
        self.steamid_key = steamid_key


class InvalidSharecodeError(Exception):
    """
    Raised when a sharecode is wrongly associated with a user.
    """

    def __init__(self, steamuser, sharecode):
        self.steamuser = steamuser
        self.sharecode = sharecode


class ClientError(Exception):
    """
    Raised when a Steam client operation fails.
    """
    pass


class InvalidDemoError(Exception):
    """
    Raised when a corrupted demo is faced.
    """

    def __init__(self, sharecode, demo_url):
        self.sharecode = sharecode
        self.demo_url  = demo_url


class SteamAPI:

    def __init__(self):
        self.http = ratelimit.Ratelimiter('Steam API')

    def fetch_sharecodes(self, first_sharecode, steamuser):
        sharecode = first_sharecode
        while sharecode is not None:
            yield sharecode
            url = (
                f'https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1?key={STEAM_API_KEY}'
                f'&steamid={steamuser.steamid}&steamidkey={steamuser.steamid_key}&knowncode={sharecode}'
            )
            log.debug(f'-> {url}')
            try:

                # HTTP response code will be 202 if the last sharecodes is reached:
                # https://developer.valvesoftware.com/wiki/Counter-Strike:_Global_Offensive_Access_Match_History
                response = self.http.request(url, accept=(200, 202))
                log.debug(f'-> {response.status_code}')
                if response.status_code == 200:
                    log.debug(f'Response: {response.json()}')
                    sharecode = response.json()['result']['nextcode']
                else:
                    sharecode = None

            except ratelimit.RequestError as ex:
                # https://developer.valvesoftware.com/wiki/Counter-Strike:_Global_Offensive_Access_Match_History#Error_Handling
                if ex.status_code == 412 and sharecode == first_sharecode:
                    raise InvalidSharecodeError(steamuser, sharecode)

    def test_steam_auth(self, sharecode, steamuser):
        tmp_http = ratelimit.Ratelimiter('Steam Auth Test', max_trycount=2)
        try:
            tmp_http.request(
                (
                    f'https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1?key={STEAM_API_KEY}'
                    f'&steamid={steamuser.steamid}&steamidkey={steamuser.steamid_key}&knowncode={sharecode}'
                ),
                accept=(200, 202),
            )
            return True
        except ratelimit.RequestError:
            return False

    def fetch_profile(self, steamid):
        response = self.http.request(
            f'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steamid}'
        )
        try:
            return response.json()['response']['players'][0]
        except IndexError:
            log.critical(f'Failed to fetch steam profile: {steamid}')
            raise


def parse_demo(demofile):
    if demofile.startswith('http://'):
        log.info(f'Downloading demo: {demofile}')
        response = requests.get(demofile)
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(bz2.decompress(response.content))
            temp.flush()
            return parse_demo(temp.name)
    elif demofile.lower().endswith('.bz2'):
        with tempfile.NamedTemporaryFile() as temp:
            zipfile = bz2.BZ2File(demofile)
            temp.write(zipfile.read())
            temp.flush()
            return parse_demo(temp.name)
    log.info(f'Parsing demo: {demofile}')
    try:
        assert os.path.isfile(demofile)
        return awpy.Demo(path=demofile, ticks = False)  # `ticks = False` is required to reduce memory consumption
    except:  # noqa: E722
        log.critical(f'Failed to parse demo: {demofile}')
        raise


# see:
# - https://csgo.readthedocs.io/en/stable/
# - https://github.com/ValvePython/steam/blob/master/recipes/1.Login/persistent_login.py

class CSGO:

    def __init__(self):
        self.steam_started = False

        self.steam = SteamClient()
        self.steam.connection = WebsocketConnection()
        self.csgo  = CSGOClient(self.steam)

        self.steam.on('error', self._error)
        self.steam.on('channel_secured', self._send_login)
        self.steam.on('reconnect', self._handle_reconnect)
        self.steam.on('disconnected', self._handle_disconnect)
        self.steam.on('logged_on', self._start_csgo)

        self.csgo.on('ready', self._csgo_ready)

    def _error(self, result):
        log.error('Steam logon error:', repr(result))

    def _send_login(self):
        if self.steam.relogin_available:
            self.steam.relogin()

    def _handle_reconnect(self, delay):
        log.info(f'Reconnect Steam in {delay}')

    def _handle_disconnect(self):
        log.warning('Steam disconnected')
        if self.steam.relogin_available:
            log.info('Reconnecting Steam')
            self.steam.reconnect(maxdelay = 30)

    def _start_csgo(self):
        log.info('Steam logon successful')
        self.csgo.launch()

    def _csgo_ready(self):
        log.info('CSGO game coordinator is ready')

    def wait(self):
        if not self.steam_started:
            log.info('Connecting to Steam')
            self.steam.login(
                username = os.environ['CS2PB_STEAM_USERNAME'],
                password = os.environ['CS2PB_STEAM_PASSWORD'],
            )
            self.steam_started = True
        if not self.csgo.ready:
            log.warning(f'CSGO game coordinator is down, will wait for it')
            self.csgo.wait_event('ready')
            log.info(f'Finished waiting for CSGO game coordinator')


class CSGOWrapper:

    def __init__(self):
        self.csgo = None

    def get(self):
        if not settings.CSGO_API_ENABLED:
            log.warning(f'CSGO API is disabled')
        else:
            if self.csgo is None:
                self.csgo = CSGO()
            try:
                self.csgo.wait()
            except gevent.exceptions.LoopExit as ex:
                log.exception(ex)
                log.warning('Restarting Steam client')
                self.csgo = None
                return self.get()
            return self.csgo.csgo


api = SteamAPI()
