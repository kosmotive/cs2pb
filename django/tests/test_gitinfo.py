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

    def test(self):
        changelog = gitinfo.get_changelog()
        self.assertIn(dict(
            message = 'Fix player cards HTML/CSS',
            url = 'https://github.com/kodikit/cs2pb/pull/6',
            sha = '4a7136f55f7db3cd7c12191103eeb36ece7feafd',
            date = '2024-07-26',
        ), changelog)

        previous_date = None
        for entry in changelog:
            if previous_date is not None:
                self.assertLessEqual(entry['date'], previous_date)
            previous_date = entry['date']


if __name__ == '__main__':
    unittest.main()
