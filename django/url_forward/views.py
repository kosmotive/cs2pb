import base64

from django.shortcuts import render


def do_redirect(request, encoded_url):
    url = base64.b64decode(encoded_url.encode('utf-8')).decode('utf-8')
    context = dict(url = url)
    return render(request, 'url_forward/redirect.html', context)
