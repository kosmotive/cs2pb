import base64

from django.shortcuts import render


def do_redirect(request, encoded_url):
    url = base64.b64encode(encoded_url.encode(encoding='utf-8'))
    context = dict(url = url)
    return render(request, 'url_forward/redirect.html', context)
