import urllib

from django.urls import reverse


def get_redirect_url_to(url):
    return reverse('redirect', kwargs = dict(
        encoded_url = urllib.parse.quote_plus(url)
    ))
