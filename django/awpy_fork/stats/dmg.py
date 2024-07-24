"""Calculates Average Damage Per Round.

This file is forked from: https://github.com/pnxenopoulos/awpy/blob/03f42504f5cb9ca29955db79764842bd0a9075f3/awpy/stats/adr.py
"""

import pandas as pd

from awpy import Demo


def dmg(
    demo: Demo,
    team_dmg: bool = False,  # noqa: FBT001, FBT002
    self_dmg: bool = True,  # noqa: FBT001, FBT002
) -> pd.DataFrame:
    """Calculates total damage. Does not include team damage.

    Args:
        demo (Demo): A parsed Awpy demo.
        team_dmg (bool, optional): Whether to use team damage. Defaults to False.
        self_dmg (bool, optional): Whether to use self damage. Defaults to True.

    Returns:
        pd.DataFrame: A dataframe of the player info + total damage.

    Raises:
        ValueError: If damages are missing in the parsed demo.
    """
    if demo.damages is None:
        missing_damages_error_msg = "Damages is missing in the parsed demo!"
        raise ValueError(missing_damages_error_msg)

    damages = demo.damages

    # Remove team damage
    if team_dmg:
        damages = damages[damages["attacker_team_name"] != damages["victim_team_name"]]

    # Remove self damage
    if self_dmg:
        damages = damages[~damages["attacker_name"].isna()]

    # Calculate all/ct/t total damage
    damages_all = (
        damages.groupby(["attacker_name", "attacker_steamid"])
        .dmg_health_real.sum()
        .reset_index(name="dmg")
    )
    damages_all["team_name"] = "all"
    damages_ct = (
        damages[damages["attacker_team_name"] == "CT"]
        .groupby(["attacker_name", "attacker_steamid"])
        .dmg_health_real.sum()
        .reset_index(name="dmg")
    )
    damages_ct["team_name"] = "CT"
    damages_t = (
        damages[damages["attacker_team_name"] == "TERRORIST"]
        .groupby(["attacker_name", "attacker_steamid"])
        .dmg_health_real.sum()
        .reset_index(name="dmg")
    )
    damages_t["team_name"] = "TERRORIST"
    damage_agg = pd.concat([damages_all, damages_ct, damages_t])
    damage_agg.columns = ["name", "steamid", "dmg", "team_name"]

    # Drop columns "name" and "team_name"
    damage_agg.drop(columns=['name', 'team_name'], inplace=True)

    # Group by "steamid", aggregate by maximum damage
    damage_agg = damage_agg.groupby('steamid').max()

    return damage_agg
