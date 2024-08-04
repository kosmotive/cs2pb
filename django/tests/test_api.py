from types import SimpleNamespace
import unittest
from unittest.mock import patch

from memory_profiler import memory_usage

import api
from tests import testsuite


class fetch_match_details(unittest.TestCase):

    def test(self):
        pmatch = {
            'sharecode': 'CSGO-a622L-DjJDC-5zwn4-Gx2tf-YYmQD',
            'timestamp': 1720469310,
            'summary': SimpleNamespace(
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

        fetch_match_details = lambda: api.fetch_match_details(pmatch)
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


class api_csgo(unittest.TestCase):

    @patch('django.conf.settings.CSGO_API_ENABLED', True)
    def test(self):
        api.api.csgo.get().request_full_match_info(0, 0, 0)
        response = api.api.csgo.get().wait_event('full_match_info', 10)
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 1)
        self.assertEqual(type(response[0]).__name__, 'CMsgGCCStrike15_v2_MatchList')
