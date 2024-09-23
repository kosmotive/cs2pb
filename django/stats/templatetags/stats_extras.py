import math

import stats.potw

from django import template
from django.db.models import Sum
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def map_name(slug):
    return slug[3:]


@register.filter
def divide(a, b):
    if a == 0 and b == 0:
        b = 1
    return a / b


@register.filter
def multiply(a, b):
    return a * b


@register.filter
def addf(a, b):
    return float(a) + float(b)


@register.filter
def subtractf(a, b):
    return float(a) - float(b)


@register.filter
def player_value(match_participation):
    if match_participation.deaths == 0:
        return match_participation.adr / 100
    else:
        return math.sqrt((match_participation.kills / match_participation.deaths) * match_participation.adr / 100)


@register.filter
def get_value(dictionary, key):
    return dictionary.get(key)


@register.filter
def potw_mode_name(mode):
    return stats.potw.get_mode_by_id(mode).name


@register.filter
def match_badge_count(qs):
    return qs.aggregate(Sum('frequency'))['frequency__sum']


@register.filter
def list_of_match_badges(qs):

    def format_badge(badge):
        yield '<li>'
        yield f'<span class="match-map">{ badge.participation.pmatch.map_name[3:] }</span>'
        yield f'<span class="match-weekday">{ badge.participation.pmatch.weekday }</span>'
        yield f'<span class="match-date">{ badge.participation.pmatch.date }</span>'
        yield f'<span class="match-time">{ badge.participation.pmatch.time }</span>'
        if badge.frequency > 1:
            yield f'<span class="match-badge-frequency">{ badge.frequency }&times;</span>'
        yield '</li>'

    if len(qs) > 0:
        return mark_safe(
            '<ul>' +
            ''.join(
                ''.join(format_badge(badge)) for badge in qs
            ) +
            '</ul>'
        )
    else:
        return ''


@register.filter(is_safe = True)
def list_of_gaming_sessions(qs):
    if len(qs) > 0:
        return mark_safe(
            '<ul>' +
            ''.join(
                '<li>'
                f'<span class="session-weekday">{ session.started_weekday }</span>'
                f'<span class="session-date">{ session.started_date }</span>'
                f'<span class="session-time">{ session.started_time } &ndash; { session.ended_time }</span>'
                '</li>'
                for session in qs
            ) +
            '</ul>'
        )
    else:
        return ''
