import re
import unittest

import gitinfo


class get_head_info(unittest.TestCase):

    def test(self):
        info = gitinfo.get_head_info()
        self.assertIsInstance(info['sha'], str)
        self.assertIsInstance(info['date'], str)
        self.assertIsNotNone(re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', info['date']))


class get_changelog(unittest.TestCase):

    def test_merged_pr(self):
        changelog = gitinfo.get_changelog()
        self.assertIn(dict(
            message = 'Fix player cards HTML/CSS',
            url = 'https://github.com/kodikit/cs2pb/pull/6',
            sha = '4a7136f55f7db3cd7c12191103eeb36ece7feafd',
            date = '2024-07-26',
        ), changelog)

    def test_squashed_pr(self):
        changelog = gitinfo.get_changelog(skip_nochangelog=False)
        self.assertIn(dict(
            message = '[no-changelog] Extract changelog from Git history',
            url = 'https://github.com/kodikit/cs2pb/pull/8',
            sha = 'a6f3167e1313abb002cc759142eec01c235da977',
            date = '2024-07-28',
        ), changelog)

    def test_substitute(self):
        changelog = gitinfo.get_changelog()
        self.assertIn(dict(
            message = 'Fix Discord name field in settings/signup',
            url = 'https://github.com/kodikit/cs2pb/pull/5',
            sha = 'f229070697d182f1aa55b2594bf3e7f0cf69bd34',
            date = '2024-07-25',
        ), changelog)

    def test_exclude(self):
        changelog = gitinfo.get_changelog()
        sha_list = [entry['sha'] for entry in changelog]
        self.assertNotIn('ef37efb000f082b1a18e9fd4c1e49344eb6d4f78', changelog)

    def test_order(self):
        changelog = gitinfo.get_changelog()
        previous_date = None
        for entry in changelog:
            if previous_date is not None:
                self.assertLessEqual(entry['date'], previous_date)
            previous_date = entry['date']


if __name__ == '__main__':
    unittest.main()
