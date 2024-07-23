import logging
import matplotlib as mpl
mpl.use('Agg')

import matplotlib.pyplot as plt
import numpy as np

from django.db.models.query import QuerySet

from .features import Features, FeatureContext, escape_none

from datetime import datetime
from io import BytesIO


log = logging.getLogger(__name__)

DEFAULT_COLORS = plt.rcParams['axes.prop_cycle'].by_key()['color']


class Renderer:

    def __init__(self, fmt='png'):
        self.fmt = fmt

    def __enter__(self):
        self.fig = plt.figure()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            buf = BytesIO()
            self.fig.savefig(buf, format=self.fmt)
            buf.seek(0)
            self.data = buf


def format_date(dt):
    return dt.strftime('%-d %b %Y')


def parse_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp)


def unroll_datachunks(features, *datachunks):
    from .models import MatchParticipation
    values       = list()
    oldest_match = None
    stats_lut    = dict()
    for dr_idx, datachunk in enumerate(datachunks):
        if isinstance(datachunk, FeatureContext):
            if not datachunk.player_participations.exists() and datachunk.squad_participations.exists(): return None
            stats = [feature(datachunk) for feature in features]
            stats_lut[dr_idx] = stats
            loads  = [stat['load_raw'] if stat['load_raw'] is not None else None for stat in stats]
            scales = [stat['max_value'] if stat['max_value'] is not None else None for stat in stats]
            period = MatchParticipation.Period().without_old(datachunk.days)
            datachunk_filtered = datachunk.filtered(period)
            for qs in (datachunk_filtered.player_participations, datachunk_filtered.squad_participations):
                if qs is None or len(qs) == 0: continue
                _oldest_match = qs.earliest('pmatch__timestamp').pmatch
                if oldest_match is None or _oldest_match.timestamp < oldest_match.timestamp:
                    oldest_match = _oldest_match
        elif isinstance(datachunk, tuple) and len(datachunk) == 2 and datachunk[0] == 'trend' and isinstance(datachunk[1], int):
            stats = stats_lut[datachunk[1]]
            loads = [(1 + escape_none(stat['trend_rel'], 0)) * stat['load'] / 100 if stat['load'] is not None else None for stat in stats]
        else:
            raise ValueError(f'Unknown datachunk at position {dr_idx}: {str(datachunk)}')
        values.append(loads)
    feature_names = [stat['name'] for stat in stats]
    return values, feature_names, oldest_match, scales


def add_default_hints(r, oldest_match):
    text_period = f'{format_date(parse_timestamp(oldest_match.timestamp))}—{format_date(datetime.now())}'
    text_percentages = '% values are with respect to the 84th percentile of the normal distribution (except for team contribution).'
    plt.text(0.02, 0.95, text_period, transform=r.fig.transFigure)
    plt.text(0.98, 0.02, text_percentages, transform=r.fig.transFigure, ha='right', color='#bbb', fontsize=8)
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.15)


def radar(*datachunks, labels = [], features = Features.MANY, feature_substitutions = {}, plot_kwargs = [], fill_kwargs = []):
    from .radarplot import radar as _radar
    assert len(datachunks) > 0 and len(datachunks) == len(labels), f'datachunks: {datachunks}, labels: {labels}'
    feature_substitutions.setdefault('Flashbang score', 'Flashbang\nscore')
    feature_substitutions.setdefault('Assists per death', 'Assists per\ndeath')
    feature_substitutions.setdefault('Utility damage per round', 'Utility damage\nper round')
    feature_substitutions.setdefault('Headshot ratio', 'Headshot\nratio')
    feature_substitutions.setdefault('Team impact', 'Team\nimpact')
    feature_substitutions.setdefault('Participation effect', 'Participation\neffect')
    feature_substitutions.setdefault('Damage per round', 'Damage\nper round')
    feature_substitutions.setdefault('Kills per death', 'Kills per\ndeath')
    values, feature_names, oldest_match = unroll_datachunks(features, *datachunks)[:3]
    feature_names = [feature_substitutions.get(name, name) for name in feature_names]
    with Renderer() as r:
        values = [np.asarray(line).astype(float) for line in values]
        _radar(r.fig, feature_names, *values, labels = labels, plot_kwargs = plot_kwargs, fill_kwargs = fill_kwargs)
        add_default_hints(r, oldest_match)
    return r.data


def trends(squad, player, features, days = None, trend_shift = None, **filters):
    context    = FeatureContext.create_default(player, squad, days, trend_shift, **filters)
    datachunks = [context, ('trend', 0)]
    labels     = [player.clean_name, f'Trend ({-context.trend_shift / (60 * 60 * 24):g} days)']
    return radar(*datachunks, features = features, labels = labels,
        plot_kwargs = [
            {'c': DEFAULT_COLORS[0]},
            {'c': DEFAULT_COLORS[0], 'ls': '--'},
        ],
        fill_kwargs = [
            {},
            {'alpha': 0},
        ])


def bars(*datachunks, labels = [], features = Features.MANY):
    assert len(datachunks) > 0 and len(datachunks) == len(labels), f'datachunks: {datachunks}, labels: {labels}'
    values, feature_names, oldest_match, scales = unroll_datachunks(features, *datachunks, *[('trend', idx) for idx, _ in enumerate(datachunks)])
    X_values = np.array(values[:len(labels) ]).T.astype(float)
    X_trends = np.array(values[ len(labels):]).T.astype(float)
    ymax = 0
    with Renderer() as r:
        label_locations = np.arange(len(labels))
        bar_width = 1 / (1 + len(features))
        group_width = bar_width * len(features)
        for idx, (x_values, name, scale, x_trends) in enumerate(zip(X_values, feature_names, scales, X_trends)):
            bar_locations = label_locations - group_width / 2 + bar_width * idx + bar_width / 2
            if scale is not None and scale != 1: name = f'{name} (×{scale:.1f})'
            plt.bar(bar_locations, x_values, bar_width, label=name, lw=1, ec='white')
            dt = x_trends - x_values
            for location, dti, xi in zip(bar_locations, dt, x_values):
                plt.annotate('', xy=(location, xi + dti), xytext=(location, xi - dti), arrowprops=dict(arrowstyle = '-|>', mutation_scale=20, color='k'))
                ymax = max((ymax, xi + dti, xi - dti))
        plt.legend(prop=dict(size=7), ncol=2)
        plt.xticks(label_locations, labels)
        plt.ylim(0, ymax + 0.05)
        plt.grid(axis='y')
        add_default_hints(r, oldest_match)
    return r.data

