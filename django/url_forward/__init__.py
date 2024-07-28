import base64

from django.urls import reverse


def get_redirect_url_to(url):
    return reverse('redirect', kwargs = dict(
        encoded_url = base64.b64encode(url_bytes.encode('utf-8')).decode('utf-8')
    ))
