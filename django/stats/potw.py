class Mode:

    def __init__(self, id, description):
        self.id = id
        self.description = description

    def accumulate(self, stats, mp):
        raise NotImplementedError()

    def aggregate(self, stats):
        raise NotImplementedError()


class KDChallenge(Mode):

    def accumulate(self, stats, mp):
        stats.setdefault('kills', 0)
        stats.setdefault('deaths', 0)
        stats['kills'] += mp.kills
        stats['deaths'] += mp.deaths

    def aggregate(self, stats):
        return stats['kills'] / max((1, stats['deaths']))


class ADRChallenge(Mode):

    def accumulate(self, stats, mp):
        stats.setdefault('damage', 0)
        stats.setdefault('rounds', 0)
        stats['damage'] += mp.adr * mp.pmatch.rounds
        stats['reference'] += mp.pmatch.rounds

    def aggregate(self, stats):
        return stats['damage'] / max((1, stats['rounds']))


class StreakChallenge(Mode):

    def accumulate(self, stats, mp):
        stats.setdefault('score', 0)
        stats['score'] += sum(
            (
                 1 * mp.streak(2),
                 5 * mp.streak(3),
                20 * mp.streak(4),
                50 * mp.streak(5),
            )
        )

    def aggregate(self, stats):
        return stats['score']


mode_cycle = [
    KDChallenge(id = 'k/d', description = 'Max out your kill/death ratio!'),
    ADRChallenge(id = 'adr', description = 'Max out your average damage per round!'),
    StreakChallenge(id = 'streaks', description = 'Score two-kills, three-kills, quad-kills, and aces!'),
]


def get_next_mode(mode_id):
    idx = [m.id for m in mode_cycle].index(mode_id)
    return mode_cycle[(idx + 1) % len(mode_cycle)]
