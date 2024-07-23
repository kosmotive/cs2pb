from django.utils.functional import cached_property
from django.db.models import F, ExpressionWrapper, Avg, StdDev, Case, When, Count, Value, Max
from django.db.models.functions import Sqrt

import numpy as np
import logging


log = logging.getLogger(__name__)

F_float = lambda expr: F(expr) * 1.
escape_none = lambda f, f_none = 1: f_none if f is None else f


def stat(name, value, fmt, max_value = 1, trend = None, trend_rel = None):
    assert max_value > 0, f'max_value = 0 giveon for {name} (value: {value})'
    return {
        'name':  name,
        'value': value,
        'load':  None if value is None else 100 * min((1, value / max_value)),
        'load_raw':  None if value is None else value / max_value,
        'max_value': max_value,
        'label': '' if value is None else fmt.format(value),
        'trend': trend,
        'trend_rel': trend_rel,
    }


class Feature:

    def __init__(self, name, description, max_value = 1, format = '{:.2f}'):
        self.name = name
        self.description = description
        self.max_value = max_value
        self.format = format

    def value(self, ctx):
        return NotImplemented

    def get_max_value(self, ctx):
        return self.max_value

    def __call__(self, ctx):
        from .models import MatchParticipation
        period = MatchParticipation.Period().without_old(ctx.days)
        value_base = self.value(ctx.filtered(period))
        value_ref  = self.value(ctx.filtered(period.shift(ctx.trend_shift))) if ctx.trend_shift != 0 else value_base
        if value_base is not None and value_ref is not None:
            trend = value_base - value_ref
            if trend == 0:
                trend_rel = 0
            else:
                trend_rel = trend / value_ref if value_ref > 0 else np.infty
        else:
            trend, trend_rel = None, None
        return stat(self.name, value_base, self.format, max_value = self.get_max_value(ctx), trend = trend, trend_rel = trend_rel)


class FeatureContext:

    def __init__(self, player_participations, squad_participations = None, days = None, trend_shift = None):
        from .models import MatchParticipation
        self.player_participations = player_participations
        self.squad_participations  =  squad_participations
        self.days = days if days is not None else MatchParticipation.Period.DEFAULT_DAYS
        self.trend_shift = trend_shift if trend_shift is not None else MatchParticipation.Period.LONG_TERM_TREND_SHIFT

    @staticmethod
    def create_default(player, squad = None, days = None, trend_shift = None, **filters):
        return FeatureContext(player.match_participations(**filters), squad.match_participations(**filters) if squad is not None else None, days, trend_shift)

    def filtered(self, period):
        from .models import MatchParticipation
        player_participations = MatchParticipation.filter(self.player_participations, period)
        squad_participations  = MatchParticipation.filter(self.squad_participations , period) if self.squad_participations is not None else None
        return FeatureContext(player_participations, squad_participations)


class ExpressionFeature(Feature):

    def __init__(self, expression, *args, max_value=None, format='{:.2f}', **kwargs):
        super().__init__(*args, max_value, format, **kwargs)
        self.expression = expression

    def get_max_value(self, ctx):
        from .models import MatchParticipation
        if self.max_value is None:
            qs = MatchParticipation.objects.annotate(value = self.expression).exclude(value = None).aggregate(Avg('value'), StdDev('value'))
            return escape_none(qs['value__avg']) + escape_none(qs['value__stddev'])
        else:
            return self.max_value

    def value(self, ctx):
        from .models import MatchParticipation
        avg_value_qs = ctx.player_participations.annotate(value = self.expression).aggregate(Avg('value'))
        avg_value = avg_value_qs['value__avg']
        return 0 if avg_value is not None and avg_value < 0 else avg_value


class TeamImpact(Feature):

    def __init__(self):
        super().__init__('Team impact', 'Zero-normalized cross correlation of the individual and the team performance.')

    def value(self, ctx):
        qs_tr_kd = ctx.player_participations.annotate(
            tr = Case(When(result='w', then=1.), When(result='l', then=-1.), default=0.),
            kd = F_float('kills') / F_float('deaths')
        )
        data = qs_tr_kd.aggregate(Avg('tr'), StdDev('tr'), Avg('kd'), StdDev('kd'))
        zncc = None if data['kd__stddev'] is None or data['tr__stddev'] is None else qs_tr_kd.annotate(
                coeff = 
                    ((F('kd') - data['kd__avg']) * (F('tr') - data['tr__avg']))
                    / (data['kd__stddev'] * data['tr__stddev'])
                ).aggregate(Avg('coeff'))['coeff__avg']
        return None if zncc is None else max((0, zncc))


class ParticipationEffect(Feature):

    def __init__(self, min_datapoints = 2): ## this should be made higher later
        super().__init__('Participation effect', 'The expected causal effect of particpating in a squad match towards winning that match (aka treatment effect) based on Judea Pearl\'s causality calculus, which he received the Turing award for in 2011.')
        self.min_datapoints = min_datapoints

    def value(self, ctx):
        from .models import MatchParticipation
        victories_with_participation = ctx.player_participations.filter(result = 'w').count()
        matches_with_participation   = ctx.player_participations.exclude(result = 't').count()
        matches_without_participation_qs = ctx.squad_participations.values('pmatch', 'result').exclude(pmatch__in = ctx.player_participations.values_list('pmatch', flat=True)).exclude(result = 't').order_by('pmatch').distinct()
        matches_without_participation    = matches_without_participation_qs.count()
        if matches_with_participation < self.min_datapoints or matches_without_participation < self.min_datapoints:
            return None
        else:
            victories_without_participation = matches_without_participation_qs.filter(result = 'w').count()
            victory_chance_with_participation    = victories_with_participation    / matches_with_participation
            victory_chance_without_participation = victories_without_participation / matches_without_participation
            expected_causal_effect = victory_chance_with_participation - victory_chance_without_participation
            return (1 + expected_causal_effect) / 2


class Features:

    kd   = ExpressionFeature(F_float('kills') / F_float('deaths'), 'Kills per death', 'The kills/death ratio, averaged over all matches.')
    ad   = ExpressionFeature(F_float('assists') / F_float('deaths'), 'Assists per death', 'The assists/death ratio, averaged over all matches.')
    ti   = TeamImpact()
    pe   = ParticipationEffect()
    adr  = ExpressionFeature(F_float('adr'), 'Damage per round', 'The damage per round, averaged over all matches.', format='{:.1f}')
    kast = ExpressionFeature(F_float('kast'), 'KAST performance', 'Rounds in which the player either had a kill, assist, survived, or was traded.', format='{:.1f}')
    hltv = ExpressionFeature(F_float('hltv'), 'HLTV rating', 'Performance in relation to the statistical means.', format='{:.1f}')
    pv   = ExpressionFeature(Sqrt((F_float('kills') / F_float('deaths')) * (F_float('adr') / Value(100))), 'Player value', 'Geometric mean of kills per death ration and the average damage per round (divided by 100).')

    ALL  = [] # will be filled automatically
    MANY = [pv, pe, adr, kd]


for attr_name in dir(Features):
    attr_value = getattr(Features, attr_name)
    if isinstance(attr_value, Feature):
        attr_value.slug = attr_name
        Features.ALL.append(attr_value)

