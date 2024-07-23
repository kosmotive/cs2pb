from django import template
from django.template.defaultfilters import stringfilter


register = template.Library()


@register.filter
@stringfilter
def map_name(slug):
    return slug[3:]


@register.filter
def divide(a, b):
    if a == 0 and b == 0: b = 1
    return a / b


@register.filter
def multiply(a, b):
    return a * b


@register.filter
def get_value(dictionary, key):
    return dictionary.get(key)

