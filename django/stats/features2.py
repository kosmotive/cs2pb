from django.db.models import F, Avg, Value
from django.db.models.functions import Sqrt


def F_float(expr):
    return F(expr) * 1.


class FeatureContext:

    def __init__(self, match_participations, player):
        self.match_participations_universe = match_participations
        self.match_participations_with_player = match_participations.filter(player = player)


class Feature:

    def __init__(self, name, description, format = '{:.2f}'):
        self.name = name
        self.description = description
        self.format = format


class ExpressionFeature(Feature):

    def __init__(self, expression, *args, format='{:.2f}', **kwargs):
        super().__init__(*args, format, **kwargs)
        self.expression = expression

    def __call__(self, ctx: FeatureContext) -> float:
        avg_value_qs = ctx.player_participations.annotate(value = self.expression).aggregate(Avg('value'))
        avg_value = avg_value_qs['value__avg']
        return 0 if avg_value is not None and avg_value < 0 else avg_value


class Features:

    kill_per_death = ExpressionFeature(
        F_float('kills') / F_float('deaths'),
        'Kills per death',
        'The kills/death ratio, averaged over all matches.',
    )

    player_value = ExpressionFeature(
        Sqrt((F_float('kills') / F_float('deaths')) * (F_float('adr') / Value(100))),
        'Player value',
        'Geometric mean of kills per death ration and the average damage per round (divided by 100).',
    )
