import base64

from django.test import TestCase

import url_forward


class get_redirect_url_to(TestCase):

    def test(self):
        url = 'https://github.com/kodikit'
        actual = url_forward.get_redirect_url_to(url)
        code = base64.b64encode(url.encode('utf-8')).decode('utf-8')
        self.assertEqual(actual, f'/redirect/{code}/')


class do_redirect(TestCase):

    def test(self):
        url = 'https://github.com/kodikit'
        code = base64.b64encode(url.encode('utf-8')).decode('utf-8')
        resp = self.client.get(f'/redirect/{code}/', follow=False)
        self.assertContains(resp, 'https://github.com/kodikit', status_code=200)
        self.assertTemplateUsed(resp, 'url_forward/redirect.html')
