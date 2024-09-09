import matplotlib.pyplot as plt
import numpy as np
from cs2pb_typing import List
from stats.plots import DEFAULT_COLORS


def radar(
        fig: plt.Figure,
        features: List[str],
        *values: List[float],
        labels: List[str] = [],
        colors: List[str] = DEFAULT_COLORS,
        plot_kwargs: List[dict] = [],
        fill_kwargs: List[dict] = [],
    ) -> None:
    """
    Create a radar plot with the given features and values.

    Arguments:
        fig: The figure to plot on.
        features: The names of the features.
        values: The values for each line.
        labels: The labels for each line.
        colors: The color cycle to use for the lines.
        plot_kwargs: The plot kwargs for each line.
        fill_kwargs: The fill kwargs for each line.
    """
    N = len(features)

    # What will be the angle of each axis in the plot? (we divide the plot / number of variable)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    # Initialise the spider plot
    ax = fig.add_subplot(111, polar=True)

    # If you want the first axis to be on top:
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    # Draw one axe per variable + add labels
    plt.xticks(angles[:-1], features, weight='bold', fontsize=12)

    # Draw ylabels
    ax.set_rlabel_position(0)
    yticks = np.arange(0, np.ceil(np.nanmax(values) / 0.25)) * 0.25
    plt.yticks(yticks, [f'{yt * 100:.0f}%' for yt in yticks], color="grey", size=7)
    plt.ylim(0, yticks.max() + 0.25)

    for line_idx, line in enumerate(values):
        c = colors[line_idx % len(colors)]
        line = list(line) + list(line[:1])
        _plot_kwargs = plot_kwargs[line_idx] if len(plot_kwargs) > line_idx else dict()
        _fill_kwargs = fill_kwargs[line_idx] if len(fill_kwargs) > line_idx else dict()
        _plot_kwargs.setdefault('c', c)
        _plot_kwargs.setdefault('lw', 1)
        _plot_kwargs.setdefault('ls', 'solid')
        _plot_kwargs['label'] = labels[line_idx]
        _fill_kwargs.setdefault('c', c)
        _fill_kwargs.setdefault('alpha', 0.1)
        ax.plot(angles, line, **_plot_kwargs)
        ax.fill(angles, line, **_fill_kwargs)

    plt.legend(loc='lower left', bbox_to_anchor=(-0.3, -0.1))
