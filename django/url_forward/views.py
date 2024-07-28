import urllib

from django.shortcuts import redirect


def do_redirect(request, encoded_url):
    url = urllib.parse.unquote_plus(encoded_url)
    assert url.lower().startswith('http://') or url.lower().startswith('https://'), url
    return redirect(url)
