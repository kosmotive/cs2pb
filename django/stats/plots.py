import logging
from datetime import datetime
from io import BytesIO
from numbers import Real

import matplotlib as mpl
import numpy as np
from accounts.models import SquadMembership
from cs2pb_typing import (
    Dict,
    List,
    Union,
)

from .features import (
    Feature,
    FeatureContext,
    Features,
)

mpl.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402

log = logging.getLogger(__name__)

DEFAULT_COLORS: List[str] = plt.rcParams['axes.prop_cycle'].by_key()['color']
"""
Default color cycle.
"""

DataChunkType = Union[SquadMembership, FeatureContext]


class Renderer:
    """
    Provides a figure for off-screen plotting.
    """

    data: BytesIO
    """
    The compressed data of the figure.
    """

    format: str
    """
    The compression format to store the figure in.
    """

    def __init__(self, format = 'png'):
        self.format = format

    def __enter__(self):
        self.fig = plt.figure()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            buf = BytesIO()
            self.fig.savefig(buf, format = self.format)
            buf.seek(0)
            self.data = buf


def format_date(dt):
    return dt.strftime('%-d %b %Y')


def parse_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp)


def unwrap_datachunks(features: List[Feature], *datachunks: DataChunkType) -> List[List[Real]]:
    values: List[List[Real]] = list()
    for dc_idx, datachunk in enumerate(datachunks):

        if isinstance(datachunk, FeatureContext):
            values.append([feature(datachunk) for feature in features])

        if isinstance(datachunk, SquadMembership):
            values.append([datachunk.stats[feature.name] for feature in features])

        else:
            raise ValueError(f'Unknown datachunk at position {dc_idx}: {str(datachunk)}')

    return values


def add_default_hints(r):
    text_percentages = (
        'Damage per round is normalized by a factor of 0.01.'
    )
    plt.text(0.98, 0.02, text_percentages, transform = r.fig.transFigure, ha = 'right', color = '#bbb', fontsize = 8)
    plt.subplots_adjust(left = 0.1, right = 0.9, top = 0.9, bottom = 0.15)


def radar(
        *datachunks: DataChunkType,
        labels: List[str] = [],
        features: List[Feature] = Features.all,
        feature_substitutions: Dict[str, str] = {
            'Assists per death': 'Assists per\ndeath',
            'Headshot rate': 'Headshot\nrate',
            'Participation effect': 'Participation\neffect',
            'Damage per round': 'Damage\nper round',
            'Kills per death': 'Kills per\ndeath',
        },
        plot_kwargs: List[dict] = [],
        fill_kwargs: List[dict] = [],
        normalization: Dict[Feature, float] = {
            Features.damage_per_round: 0.01,
        },
    ) -> BytesIO:
    """
    """
    from .radarplot import radar as _radar
    assert len(datachunks) > 0 and len(datachunks) == len(labels), f'datachunks: {datachunks}, labels: {labels}'

    # Unwrap the datachunks into a list of lines
    line_list = unwrap_datachunks(features, *datachunks)

    # Apply feature-wise normalization
    for line in line_list:
        for feature, factor in normalization.items():
            fidx = features.index(feature)
            line[fidx] *= factor

    # Determine the feature names with respect to `feature_substitutions`
    feature_names = [feature_substitutions.get(feature.name, feature.name) for feature in features]

    # Render the radar plot
    with Renderer() as r:
        values = [np.asarray(line).astype(float) for line in line_list]
        _radar(r.fig, feature_names, *values, labels = labels, plot_kwargs = plot_kwargs, fill_kwargs = fill_kwargs)
        add_default_hints(r)

    # Return the compressed data
    return r.data


def trends(
        squad_membership: SquadMembership,
        context: FeatureContext,
        features: List[Feature],
    ) -> BytesIO:
    datachunks = [squad_membership, context]
    labels = [
        f'{squad_membership.player.clean_name} 30 days average',
        f'{squad_membership.player.clean_name} trend',
    ]
    return radar(
        *datachunks,
        features = features,
        labels = labels,
        plot_kwargs = [
            {'c': DEFAULT_COLORS[0]},
            {'c': DEFAULT_COLORS[0], 'ls': '--'},
        ],
        fill_kwargs = [
            {},
            {'alpha': 0},
        ],
    )
