class Mode:

    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description

    def accumulate(self, stats, mp):
        raise NotImplementedError()

    def aggregate(self, stats):
        raise NotImplementedError()

    def does_fail_requirements(self, stats):
        if stats['wins'] == 0:
            return 'Will not be awarded unless at least one match is won.'
        else:
            return None


class KDChallenge(Mode):

    fields = ['kills', 'deaths']
    labels = ['kills', 'deaths']

    def accumulate(self, stats, mp):
        stats.setdefault('kills', 0)
        stats.setdefault('deaths', 0)
        stats['kills'] += mp.kills
        stats['deaths'] += mp.deaths

    def aggregate(self, stats):
        return stats['kills'] / max((1, stats['deaths']))


class ADRChallenge(Mode):

    fields = ['damage', 'reference']
    labels = ['damage dealt', 'expected damage']

    def accumulate(self, stats, mp):
        stats.setdefault('damage', 0)
        stats.setdefault('reference', 0)
        stats['damage'] += mp.adr * mp.pmatch.rounds
        stats['reference'] += 100 * mp.pmatch.rounds

    def aggregate(self, stats):
        return 100 * stats['damage'] / max((100, stats['reference']))


class StreakChallenge(Mode):

    fields = ['score']
    labels = ['score']

    def accumulate(self, stats, mp):
        stats.setdefault('score', 0)
        stats['score'] += sum(
            (
                 1 * mp.streaks(2),
                 5 * mp.streaks(3),
                20 * mp.streaks(4),
                50 * mp.streaks(5),
            )
        )

    def aggregate(self, stats):
        return stats['score']

    def does_fail_requirements(self, stats):
        super_ret = super().does_fail_requirements(stats)
        if super_ret is not None:
            return super_ret
        elif stats['score'] == 0:
            return 'Will not be awarded unless at least a two-kill is performed.'
        else:
            return None


class AccuracyChallenge(Mode):

    fields = ['headshots', 'rounds']
    labels = ['headshots', 'rounds']

    def accumulate(self, stats, mp):
        stats.setdefault('headshots', 0)
        stats.setdefault('rounds', 0)
        stats['headshots'] += mp.headshots
        stats['rounds'] += mp.pmatch.rounds

    def aggregate(self, stats):
        return stats['headshots'] / max((1, stats['rounds']))


mode_cycle = [
    KDChallenge(
        id = 'k/d',
        name = 'K/D Challenge',
        description = 'Max out your kill/death ratio!',
    ),
    StreakChallenge(
        id = 'streaks',
        name = 'Streak Challenge',
        description = 'Score two-kills, three-kills, quad-kills, and aces!',
    ),
    ADRChallenge(
        id = 'adr',
        name = 'ADR Challenge',
        description = 'Max out your average damage per round!',
    ),
    AccuracyChallenge(
        id = 'accuracy',
        name = 'Accuracy Challenge',
        description = 'Aim for the head!',
    ),
]


def get_next_mode(mode_id):
    idx = [m.id for m in mode_cycle].index(mode_id)
    return mode_cycle[(idx + 1) % len(mode_cycle)]


def get_mode_by_id(mode_id):
    idx = [m.id for m in mode_cycle].index(mode_id)
    return mode_cycle[idx]
