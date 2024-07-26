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
        print(changelog)


if __name__ == '__main__':
    unittest.main()
