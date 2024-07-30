from django.test import TestCase

import accounts.forms


class verify_discord_name(TestCase):

    def test_valid(self):
        self.assertTrue(accounts.forms.verify_discord_name('kostrykin'))
        self.assertTrue(accounts.forms.verify_discord_name('harle153'))
        self.assertTrue(accounts.forms.verify_discord_name('harle_153'))
        self.assertTrue(accounts.forms.verify_discord_name('_harle.153_'))
        self.assertTrue(accounts.forms.verify_discord_name('kk'))
        self.assertTrue(accounts.forms.verify_discord_name('k' * 32))

    def test_invalid_characters(self):
        self.assertFalse(accounts.forms.verify_discord_name('Kostrykin'))
        self.assertFalse(accounts.forms.verify_discord_name('kostrykin#8242'))

    def test_too_short(self):
        self.assertFalse(accounts.forms.verify_discord_name('k'))
        self.assertFalse(accounts.forms.verify_discord_name(''))

    def test_too_long(self):
        self.assertFalse(accounts.forms.verify_discord_name('k' * 33))
