import os
import unittest
from unittest.mock import patch

import cs2_client
from memory_profiler import memory_usage
from stats.models import Match
from tests import testsuite

from django.test import TestCase


class fetch_match_details(unittest.TestCase):

    def setUp(self):
        self.pmatch_data = [
            {
                'sharecode': 'CSGO-a622L-DjJDC-5zwn4-Gx2tf-YYmQD',
                'timestamp': 1720469310,
                'summary': dict(
                    map = testsuite.get_demo_path('003694683536926703955_1352610665'),
                    team_scores = (4, 13),
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
        ]

    def test(self):
        pmatch = self.pmatch_data[0]
        fetch_match_details = lambda: cs2_client.fetch_match_details(pmatch)  # noqa: E731
        peak_mem_mb = max(memory_usage(proc = fetch_match_details))

        # Peak memory usage was ~900 MiB when tested, shouldn't rise too much in the future to avoid memory issues
        self.assertLess(peak_mem_mb, 1300)

        self.assertEqual(pmatch['map'], 'de_vertigo')
        self.assertEqual(round(pmatch['adr']['76561197967680028'], 1), 104.7)
        self.assertEqual(round(pmatch['adr']['76561197961345487'], 1), 96.9)
        self.assertEqual(round(pmatch['adr']['76561197961748270'], 1), 71.9)
        self.assertEqual(round(pmatch['adr']['76561198067716219'], 1), 47.6)
        self.assertEqual(round(pmatch['adr']['76561197962477966'], 1), 19.2)
        self.assertEqual(round(pmatch['adr']['76561198298259382'], 1), 106.9)
        self.assertEqual(round(pmatch['adr']['76561199034015511'], 1), 107.7)
        self.assertEqual(round(pmatch['adr']['76561198309743637'], 1), 84.5)
        self.assertEqual(round(pmatch['adr']['76561198140806020'], 1), 98.9)
        self.assertEqual(round(pmatch['adr']['76561198064174518'], 1), 63.6)

        self.assertEqual(pmatch['type'], Match.MTYPE_PREMIER)
        self.assertEqual(
            pmatch['ranks'],
            {
                '76561197961345487': {'new': 11483, 'old': 11590},
                '76561197961748270': {'new': 11963, 'old': 12073},
                '76561197962477966': {'new':  9893, 'old':  9999},
                '76561197967680028': {'new': 15107, 'old': 15231},
                '76561198064174518': {'new': 12856, 'old': 12498},
                '76561198067716219': {'new': 11645, 'old': 11754},
                '76561198140806020': {'new': 11186, 'old': 10829},
                '76561198298259382': {'new': 12812, 'old': 12662},
                '76561198309743637': {'new': 13958, 'old': 13634},
                '76561199034015511': {'new': 13080, 'old': 12966},
            },
        )

    def test_awpy_003698946311295336822_1609103086(self):
        # This test fails with awpy older than 2.0.0.b4 and should pass with newer versions
        pmatch = {
            'sharecode': 'CSGO-aKe8R-YPeR3-vjBdp-oBGxh-Z5O3A',
            'timestamp': 1722455585,
            'summary': dict(
                map = testsuite.get_demo_path('003698946311295336822_1609103086'),
                team_scores = (9, 0),
            ),
            'steam_ids': [
                76561198192222793,
                76561198195506142,
                0, 0, 0,
                76561197963929445,
                76561197962477966,
                0, 0, 0,
            ],
        }

        # Parse the demo file
        try:
            cs2_client.fetch_match_details(pmatch)

        except cs2_client.InvalidDemoError as err:
            self.fail(
                f'Parsing demo file has failed with error {str(err)}. '
                'This indicates that an old version of awpy is being used, '
                'the minimum required version is 2.0.0.b4.'
            )

        # If parsing succeeds, perform some checks to make sure that the data is correct
        self.assertEqual(pmatch['map'], 'de_vertigo')
        self.assertEqual(pmatch['type'], Match.MTYPE_WINGMAN)
        self.assertEqual(
            pmatch['ranks'],
            {
                '76561197962477966': {'new':  0, 'old':  0},
                '76561197963929445': {'new':  0, 'old':  0},
                '76561198192222793': {'new': 10, 'old': 10},
                '76561198195506142': {'new':  9, 'old':  9},
            },
        )

    @patch('cs2_client.parse_demo', wraps=cs2_client.parse_demo)
    def test_corrupted_demo_file(self, mock_parse_demo):
        fetch_match_details = lambda: cs2_client.fetch_match_details(self.pmatch_data[0])  # noqa: E731

        # Inject the error described in https://github.com/kosmotive/cs2pb/issues/23
        def raise_error_on_first_n_calls(n):
            def raise_error(*args):

                # Remove the sideeffect if this is the last call
                if mock_parse_demo.call_count == n:
                    mock_parse_demo.side_effect = None

                # Raise the error
                if mock_parse_demo.call_count <= n:
                    raise OSError()

            return raise_error

        # Test ultimate failure (after 4 attempts)
        mock_parse_demo.side_effect = raise_error_on_first_n_calls(4)
        self.assertRaises(cs2_client.InvalidDemoError, fetch_match_details)
        # ... 4 invocations raising the error:
        self.assertEqual(mock_parse_demo.call_count, 4)

        # Test success after two failures
        mock_parse_demo.call_count = 0
        mock_parse_demo.side_effect = raise_error_on_first_n_calls(2)
        fetch_match_details()
        # ... 2 invocations raising the error + 1 invocation with remote URL + 1 invocation with downloaded file:
        self.assertEqual(mock_parse_demo.call_count, 4)

        # Test success after one failure
        mock_parse_demo.call_count = 0
        mock_parse_demo.side_effect = raise_error_on_first_n_calls(1)
        fetch_match_details()
        # ... 1 invocations raising the error + 1 invocation with remote URL + 1 invocation with downloaded file:
        self.assertEqual(mock_parse_demo.call_count, 3)


class Client(TestCase):

    def setUp(self):
        self.client = cs2_client.Client(cs2_client.api)

    @patch('django.conf.settings.CSGO_API_ENABLED', True)
    def test_csgo(self):
        self.client.csgo.get().request_full_match_info(0, 0, 0)
        response = self.client.csgo.get().wait_event('full_match_info', 10)
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 1)
        self.assertEqual(type(response[0]).__name__, 'CMsgGCCStrike15_v2_MatchList')

    def _mock_client_internals(self, fetch_sharecodes_return_value):
        def decorator(func):
            @patch.object(self.client.api, 'fetch_sharecodes', return_value = fetch_sharecodes_return_value)
            @patch.object(
                self.client,
                '_resolve_sharecode',
                side_effect = lambda sharecode: dict(sharecode = sharecode),
            )
            @patch.object(self.client, '_resolve_protobuf', side_effect = lambda sharecode, protobuf: protobuf)
            @patch('cs2_client._is_wingman_match', return_value = False)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def test_fetch_matches_with_recent_matches(self):
        recent_matches = [
            Match.objects.create(
                sharecode = 'xxx-1',
                timestamp = 0,
                score_team1 = 12,
                score_team2 = 13,
                duration = 1653,
                map_name = 'de_dust2',
            )
        ]
        steamuser = cs2_client.SteamAPIUser('1234567890', 'steam_auth')

        @self._mock_client_internals(fetch_sharecodes_return_value = ['xxx-1', 'xxx-2'])
        def __test(mock_is_wingman_match, mock_resolve_protobuf, mock_resolve_sharecode, mock_fetch_sharecodes):
            ret = self.client.fetch_matches(
                first_sharecode = 'xxx-1',
                steamuser = steamuser,
                recent_matches = recent_matches,
                skip_first = False,
            )
            self.assertEqual(ret, [recent_matches[0].pk, dict(sharecode = 'xxx-2')])
            mock_fetch_sharecodes.assert_called_once_with('xxx-1', steamuser)
            mock_resolve_sharecode.assert_called_once()
            mock_resolve_protobuf.assert_called_once()

        __test()

    def test_fetch_matches_with_skip_first(self):
        steamuser = cs2_client.SteamAPIUser('1234567890', 'steam_auth')

        @self._mock_client_internals(fetch_sharecodes_return_value = ['xxx-1'])
        def __test_0_new(mock_is_wingman_match, mock_resolve_protobuf, mock_resolve_sharecode, mock_fetch_sharecodes):
            ret = self.client.fetch_matches(
                first_sharecode = 'xxx-1',
                steamuser = steamuser,
                recent_matches = list(),
                skip_first = True,
            )
            self.assertEqual(ret, list())
            mock_fetch_sharecodes.assert_called_once_with('xxx-1', steamuser)
            mock_resolve_sharecode.assert_not_called()
            mock_resolve_protobuf.assert_not_called()

        @self._mock_client_internals(fetch_sharecodes_return_value = ['xxx-1', 'xxx-2'])
        def __test_1_new(mock_is_wingman_match, mock_resolve_protobuf, mock_resolve_sharecode, mock_fetch_sharecodes):
            ret = self.client.fetch_matches(
                first_sharecode = 'xxx-1',
                steamuser = steamuser,
                recent_matches = list(),
                skip_first = True,
            )
            self.assertEqual(ret, [dict(sharecode = 'xxx-2')])
            mock_fetch_sharecodes.assert_called_once_with('xxx-1', steamuser)
            mock_resolve_sharecode.assert_called_once()
            mock_resolve_protobuf.assert_called_once()

        for subtest in (__test_0_new, __test_1_new):
            with self.subTest(subtest = subtest.__name__):
                subtest()


def create_mocked_client_class(fetch_matches):
    """
    Helper function that creates a class that mocks the Client class.

    This is necessary because dill does not support MagicMock objects.
    """

    class MockedClient:

        def __init__(self, *_):
            self.fetch_matches = fetch_matches

    return MockedClient


class fetch_matches(TestCase):

    def raise_error(error):
        raise error

    @patch('cs2_client.Client', create_mocked_client_class(fetch_matches = lambda *args: [str(args)]))
    def test(self):
        """
        Tests the arguments passed to `Client.fetch_matches` and the return value.
        """
        for skip_first in (False, True):
            with self.subTest(skip_first = skip_first):
                ret = cs2_client.fetch_matches(
                    first_sharecode = 'xxx-1',
                    steamuser = None,
                    recent_matches = list(),
                    skip_first = skip_first,
                )
                self.assertEqual(ret, [str(('xxx-1', None, list(), skip_first))])

    @patch('cs2_client.Client', create_mocked_client_class(fetch_matches = lambda *_: [os.getpid()]))
    def test_subprocessing(self):
        pid = cs2_client.fetch_matches(
            first_sharecode = '',
            steamuser = None,
            recent_matches = list(),
            skip_first = False,
        )
        self.assertNotEqual(pid, [os.getpid()])

    def test_error_handling(self):
        with patch(
            'cs2_client.Client',
            create_mocked_client_class(
                fetch_matches = lambda *_: fetch_matches.raise_error(ValueError('error')),
            ),
        ):
            with self.assertRaises(cs2_client.ClientError) as error:
                cs2_client.fetch_matches(
                    first_sharecode = '',
                    steamuser = None,
                    recent_matches = list(),
                    skip_first = False,
                )
            self.assertIsInstance(error.exception.__cause__, ValueError)
            self.assertEqual(str(error.exception.__cause__), 'error')
        with patch(
            'cs2_client.Client',
            create_mocked_client_class(
                fetch_matches = lambda *_: fetch_matches.raise_error(cs2_client.InvalidSharecodeError(None, 'xxx')),
            ),
        ):
            with self.assertRaises(cs2_client.InvalidSharecodeError) as error:
                cs2_client.fetch_matches(
                    first_sharecode = '',
                    steamuser = None,
                    recent_matches = list(),
                    skip_first = False,
                )
            self.assertIsNone(error.exception.steamuser)
            self.assertEqual(error.exception.sharecode, 'xxx')

    def test_recent_matches(self):
        recent_matches = [
            Match.objects.create(
                sharecode = 'xxx-1',
                timestamp = 0,
                score_team1 = 12,
                score_team2 = 13,
                duration = 1653,
                map_name = 'de_dust2',
            )
        ]
        with patch(
            'cs2_client.Client',
            create_mocked_client_class(
                fetch_matches = lambda *_: [
                    recent_matches[0].pk,
                    dict(sharecode = 'xxx-2'),
                ],
            ),
        ):
            matches = cs2_client.fetch_matches(
                first_sharecode = '',
                steamuser = None,
                recent_matches = recent_matches,
                skip_first = False,
            )
            self.assertEqual(len(matches), 2)
            self.assertEqual(matches[0].pk, recent_matches[0].pk)
            self.assertEqual(matches[1], dict(sharecode = 'xxx-2'))
