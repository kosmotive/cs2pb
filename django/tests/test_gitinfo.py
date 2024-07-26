import unittest

import gitinfo


class get_changelog(unittest.TestCase):

    def test(self):
        changelog = gitinfo.get_changelog()
        print(changelog)


if __name__ == '__main__':
    unittest.main()
