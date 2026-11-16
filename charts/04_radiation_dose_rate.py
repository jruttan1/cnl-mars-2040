"""Synthetic SAPPHIRE absorbed-dose rate; requires verified transport inputs."""
from sapphire_common import plot_dose

SCENARIO_ROLES = ('main', 'worst_case')  # 100-year main, 1,000-year worst-case.
# Event timing and shielding selections live in radiation_config.json.

if __name__ == '__main__':
    plot_dose(cumulative=False, roles=SCENARIO_ROLES)
