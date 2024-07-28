from django.test import TestCase

import url_forward


class get_redirect_url_to(TestCase):

    def test(self):
        actual = url_forward.get_redirect_url_to('https://github.com/kodikit')
        self.assertEqual(actual, '/redirect/https%253A%252F%252Fgithub.com%252Fkodikit/')


class do_redirect(TestCase):

    def test(self):
        resp = self.client.get('/redirect/https%253A%252F%252Fgithub.com%252Fkodikit/', follow=False)
        self.assertEqual(resp.url, 'https://github.com/kodikit')
