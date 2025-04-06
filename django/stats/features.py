from cs2pb_typing import (
    List,
    Optional,
)

from django.db.models import (
    Avg,
    F,
    Value,
)
from django.db.models.functions import Sqrt


def F_float(expr):
    return F(expr) * 1.


class FeatureContext:

    def __init__(self, match_participations, player):
        self.match_participations_universe = match_participations
        self.match_participations_of_player = match_participations.filter(player = player)


class Feature:

    name: str
    """
    The human-readable name of the feature.
    """

    description: str
    """
    Brief description of the feature.
    """

    format: str
    """
    The format string to format the feature value with.
    """

    slug: Optional[str]
    """
    A unique identifier of the feature (determined automatically, may change over time).
    """

    extra: Optional[str]
    """
    An extra information about the feature, that is displayed next to the value.
    """

    def __init__(self, name: str, description, format = '{:.2f}', extra = None):
        self.name = name
        self.description = description
        self.format = format
        self.slug = None
        self.extra = extra

    def __call__(self, ctx: FeatureContext) -> Optional[float]:
        ...


class ExpressionFeature(Feature):

    def __init__(self, expression, *args, format='{:.2f}', **kwargs):
        super().__init__(*args, format, **kwargs)
        self.expression = expression

    def __call__(self, ctx: FeatureContext) -> Optional[float]:
        avg_value_qs = self.get_queryset(ctx).aggregate(Avg('value'))
        avg_value = avg_value_qs['value__avg']
        return 0 if avg_value is not None and avg_value < 0 else avg_value
    
    def get_queryset(self, ctx: FeatureContext):
        return ctx.match_participations_of_player.annotate(value = self.expression)


class ParticipationEffect(Feature):

    def __init__(self, min_datapoints = 2):
        super().__init__(
            'Participation effect',
            'The expected causal effect of participating in a squad match towards winning that match (aka treatment '
            'effect) based on Judea Pearl\'s causality calculus, which he received the Turing award for in 2011.',
        )
        self.min_datapoints = min_datapoints

    def __call__(self, ctx: FeatureContext) -> Optional[float]:
        victories_with_participation = ctx.match_participations_of_player.filter(result = 'w').count()
        matches_with_participation   = ctx.match_participations_of_player.exclude(result = 't').count()
        matches_without_participation_qs = ctx.match_participations_universe.values('pmatch', 'result').exclude(
            pmatch__in = ctx.match_participations_of_player.values_list('pmatch', flat = True)
        ).exclude(result = 't').order_by('pmatch').distinct()
        matches_without_participation    = matches_without_participation_qs.count()
        if matches_with_participation < self.min_datapoints or matches_without_participation < self.min_datapoints:
            return None
        else:
            victories_without_participation = matches_without_participation_qs.filter(result = 'w').count()
            victory_chance_with_participation    = victories_with_participation    / matches_with_participation
            victory_chance_without_participation = victories_without_participation / matches_without_participation
            expected_causal_effect = victory_chance_with_participation - victory_chance_without_participation
            return (1 + expected_causal_effect) / 2


class Rank(Feature):

    def __init__(self, mtype):
        from .models import Match
        assert mtype in (Match.MTYPE_COMPETITIVE, Match.MTYPE_DANGER_ZONE, Match.MTYPE_WINGMAN, Match.MTYPE_PREMIER)
        super().__init__(
            f'{mtype} Rank',
            f'The latest {mtype} rank of the player.',
            format = '{:.1f}',
            extra = 'x1000',
        )
        self.mtype = mtype

    def __call__(self, ctx: FeatureContext) -> Optional[float]:
        from .models import MatchParticipation
        try:
            return ctx.match_participations_of_player.filter(
                pmatch__mtype = self.mtype,
            ).latest('pmatch__timestamp').new_rank / 1000
        except MatchParticipation.DoesNotExist:
            return None


class PeachRate(Feature):

    def __init__(self):
        super().__init__(
            'Peach rate',
            'The empirical probability of qualifying for the Peach Price.',
        )

    def __call__(self, ctx: FeatureContext) -> Optional[float]:
        from .models import MatchBadge
        if ctx.match_participations_of_player.count() > 0:
            match_participations_with_peach = MatchBadge.objects.filter(
                badge_type = 'peach',
                participation__in = ctx.match_participations_of_player.values_list('pk', flat = True),
            )
            return match_participations_with_peach.count() / ctx.match_participations_of_player.count()
        else:
            return None


class Features:

    damage_per_round = ExpressionFeature(
        F_float('adr'),
        'Damage per round',
        'The damage per round, averaged over all matches.',
        format = '{:.1f}',
    )

    assists_per_death = ExpressionFeature(
        F_float('assists') / F_float('deaths'),
        'Assists per death',
        'The assists/death ratio, averaged over all matches.',
    )

    headshot_rate = ExpressionFeature(
        F_float('headshots') / F_float('kills'),
        'Headshot rate',
        'Headshots per kill.',
    )

    kills_per_death = ExpressionFeature(
        F_float('kills') / F_float('deaths'),
        'Kills per death',
        'The kills/death ratio, averaged over all matches.',
    )

    participation_effect = ParticipationEffect()

    player_value = ExpressionFeature(
        Sqrt((F_float('kills') / F_float('deaths')) * (F_float('adr') / Value(100))),
        'Player value',
        'Geometric mean of kills per death ration and the average damage per round (divided by 100).',
    )

    peach_rate = PeachRate()

    premier_rank = Rank(mtype = 'Premier')

    all: List[Feature] = []  # Filled automatically


for attr_name in dir(Features):
    attr_value = getattr(Features, attr_name)
    if isinstance(attr_value, Feature):
        attr_value.slug = attr_name
        Features.all.append(attr_value)
