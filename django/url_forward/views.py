import urllib

from django.shortcuts import render


def do_redirect(request, encoded_url):
    url = urllib.parse.unquote_plus(encoded_url)
    context = dict(url = url)
    return render(request, 'url_forward/redirect.html', context)
