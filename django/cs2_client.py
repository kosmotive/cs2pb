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
from cs2pb_typing import (
    Any,
    Hashable,
)
from csgo.client import CSGOClient
from csgo.sharecode import decode as decode_sharecode
from stats.models import Match
from steam.client import SteamClient
from steam.core.connection import WebsocketConnection
from steam.steamid import SteamID

from django.conf import settings

STEAM_API_KEY = os.environ['CS2PB_STEAM_API_KEY']
assert len(STEAM_API_KEY) > 0

NAV_SUPPORTED_MAPS = frozenset(awpy.data.map_data.MAP_DATA.keys())

log = logging.getLogger(__name__)


def _zero_to_none(value: Any) -> Any:
    if value == 0:
        return None
    else:
        return value


def fetch_match_details(pmatch, max_retry_count = 4):
    for retry_idx in range(max_retry_count):
        time.sleep(retry_idx * 10)
        try:
            demo_url = pmatch['summary']['map']
            demo = parse_demo(demo_url)

            # No need to retry (fetch was successful)
            break

        except BaseException as error:
            log.warning(traceback.format_exc())
            log.warning(f'Failed to fetch match details (attempt: {retry_idx + 1} / {max_retry_count})')

            if retry_idx + 1 == max_retry_count:
                raise InvalidDemoError(
                    sharecode = pmatch['sharecode'],
                    demo_url = demo_url,
                ) from error

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
    num_rounds = sum(pmatch['summary']['team_scores'])
    pmatch['adr'] = {str(steam_id): get_damage(steam_id) / num_rounds for steam_id in pmatch['steam_ids']}

    # Read the ranks from the demo, `demo.events['rank_update']` is a pandas dataframe with following columns:
    #  - rank_type_id: 6 -> Competitive, 7 -> Wingman, 10 -> Danger Zone, 11 -> Premier
    #  - rank_old: Rank before the match (where 0 is unranked)
    #  - rank_new: Rank after the match (where 0 is unranked)
    #  - user_steamid: Steam ID of the player
    pmatch['type'] = {
        6:  Match.MTYPE_COMPETITIVE,
        7:  Match.MTYPE_WINGMAN,
        10: Match.MTYPE_DANGER_ZONE,
        11: Match.MTYPE_PREMIER,
    }.get(demo.events['rank_update'].rank_type_id.iloc[0], '')
    pmatch['ranks'] = {
        str(row['user_steamid']): dict(
            old = _zero_to_none(row['rank_old']),
            new = _zero_to_none(row['rank_new']),
        )
        for _, row in demo.events['rank_update'].iterrows()
    }


def _is_wingman_match(pmatch):
    """
    Deduce whether the match is a wingman match (2 on 2).

    In wingman matches, there are 5 players per team, but for 3 of them the steam ID is 0.
    We thus deduce whether the match is a wingman match by counting the occurances of 0 as the steam ID.
    """
    return (np.asarray(pmatch['steam_ids']) == 0).sum() == 6


class SteamAPIUser:

    def __init__(self, steamid, steamid_key):
        self.steamid = steamid
        self.steamid_key = steamid_key

    def __eq__(self, other):
        return isinstance(other, SteamAPIUser) and all(
            (
                self.steamid == other.steamid,
                self.steamid_key == other.steamid_key,
            )
        )

    def __hash__(self):
        return hash((self.steamid, self.steamid_key))


def fetch_matches(
        first_sharecode: str,
        steamuser: SteamAPIUser,
        recent_matches: list[Match],
        skip_first: bool,
    ) -> list[dict | Match]:
    """
    Fetch any new matches for a user, based on the given sharecode.

    The list of recent matches is used to avoid fetching matches that are already known and have been fetched recently.
    It is crucial that those matches can be identified by their sharecode solely, which is why only very recent matches
    can be used here.

    Returns a list of matches, which can be either a `Match` object (from the list of recent matches) or a match
    summary (dictionary of newly fetched data).
    """
    with tempfile.NamedTemporaryFile(delete=False) as ret_file:
        newpid = os.fork()

        # Execution inside the forked process
        if newpid == 0:

            # Fetch matches and handle errors
            success = False
            try:
                ret = Client(api).fetch_matches(first_sharecode, steamuser, recent_matches, skip_first)
                success = True
            except ClientError as error:
                log.error(f'An error occurred while fetching matches', exc_info=True)
                ret = dict(error=error, cause=None)
            except BaseException as error:
                log.critical(f'An error occurred while fetching matches', exc_info=True)
                ret = dict(error=ClientError(), cause=error)

            # Serialize the result and exit the subprocess
            dill.dump(ret, ret_file, byref=True)
            ret_file.flush()
            os._exit(0 if success else 1)

        # Execution inside the parent process
        else:
            exit_code = os.waitpid(newpid, 0)[1]
            log.info(f'fetch_matches subprocess finished with exit code {exit_code}')
            ret_file.seek(0)
            ret = dill.load(ret_file)
            if exit_code == 0:

                # Resolve any cache hits to the corresponding match objects,
                # and return the list of matches / match summaries
                match_by_pk = {pmatch.pk: pmatch for pmatch in recent_matches}
                return [
                    (
                        match_by_pk.get(summary, summary) if isinstance(summary, Hashable) else summary
                    )
                    for summary in ret
                ]

            else:

                # Report the error
                if ret['cause'] is None:
                    raise ret['error']
                else:
                    raise ret['error'] from ret['cause']


class Client:

    def __init__(self, api):
        self.api = api
        self.csgo = LazyCSGOWrapper()  # Steam connection is established only when the wrapper is used

    def fetch_matches(
            self,
            first_sharecode: str,
            steamuser: SteamAPIUser,
            recent_matches: list[Match],
            skip_first: bool,
        ) -> list[dict | int]:

        # Build a cache of recent matches that can be checked quickly
        recent_matches_cache = {pmatch.sharecode: pmatch for pmatch in recent_matches}
        log.info(f'Cached sharecodes: {", ".join(recent_matches_cache.keys()) or "None"}')

        # Fetch the newest sharecodes
        log.info(f'Fetching sharecodes (for Steam ID: {steamuser.steamid})')
        sharecodes = list(self.api.fetch_sharecodes(first_sharecode, steamuser))
        log.info(f'Fetched: {first_sharecode} -> {sharecodes}')

        # Skip the first sharecode (if requested, i.e. if the corresponding match was already processed before)
        if skip_first:
            log.info(f'Skipping first sharecode: {sharecodes[0]}')
            sharecodes = sharecodes[1:]

        # Resolve the fetched sharecodes
        matches: list[dict] = list()
        for sidx, sharecode in enumerate(sharecodes):
            log.info(f'Processing sharecode: {sharecode} ({sidx + 1} / {len(sharecodes)})')

            # Check if the sharecode is already among the recent matches (cache hit)
            cache_hit = recent_matches_cache.get(sharecode)
            if cache_hit is not None:
                log.info(f'Cache hit for sharecode: {sharecode}')
                matches.append(cache_hit.pk)

            # Otherwise, resolve the sharecode
            else:
                protobuf = self._resolve_sharecode(sharecode)
                summary = self._resolve_protobuf(sharecode, protobuf)

                # Skip the match if it is a wingman match
                if _is_wingman_match(summary):
                    log.info(f'Skipping wingman match: {sharecode}')
                else:
                    matches.append(summary)

        # Return only matches that are not wingman matches
        log.info(f'Fetched {len(matches)} match(es)')
        return matches

    def _unfold_summary(self, summary):
        """
        Unfold the protobuf object into a simple dictionary, that can easily be pickled.
        """
        return {
            key: getattr(summary, key) for key in [
                'map',
                'match_duration',
            ]
        } | {
            key: list(getattr(summary, key)) for key in [
                'team_scores',
                'enemy_kills',
                'enemy_headshots',
                'assists',
                'deaths',
                'scores',
                'mvps',
            ]
        }

    def _resolve_sharecode(self, sharecode: str) -> Any:
        """
        Resolves a sharecode to a protobuf object.
        """
        log.info(f'Resolving sharecode: {sharecode}')
        d = decode_sharecode(sharecode)
        log.info('Requesting match info')
        while True:
            self.csgo.get().request_full_match_info(d['matchid'], d['outcomeid'], d['token'])
            log.info('Waiting for match data')
            response = self.csgo.get().wait_event('full_match_info', 10)
            if response is not None:
                break
            log.info('Waiting for match data timed out, retrying')
        log.info('Match data completed')
        return response[0].matches[0]

    def _resolve_protobuf(self, sharecode: str, protobuf: Any) -> dict:
        """
        Resolves a protobuf object to a summary of a match.
        """
        return dict(
            sharecode = sharecode,
            timestamp = protobuf.matchtime,
            summary   = self._unfold_summary(protobuf.roundstatsall[-1]),
            steam_ids = self._resolve_account_ids(protobuf.roundstatsall[-1].reservation.account_ids),
        )

    def _resolve_account_ids(self, account_ids):
        log.info('Resolving Steam IDs')
        return [SteamID(int(account_id)).as_64 for account_id in account_ids]


class ClientError(Exception):
    """
    Raised when a client operation fails.
    """
    pass


class InvalidSharecodeError(ClientError):
    """
    Raised when a sharecode is wrongly associated with a user.
    """

    def __init__(self, steamuser, sharecode):
        self.steamuser = steamuser
        self.sharecode = sharecode


class InvalidDemoError(ClientError):
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
                else:
                    raise

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


class LazyCSGOWrapper:

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
