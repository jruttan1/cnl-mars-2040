"""Synthetic SAPPHIRE cumulative dose; requires verified transport inputs."""
from sapphire_common import plot_dose

SCENARIO_ROLES = ('main', 'worst_case')  # 100-year main, 1,000-year worst-case.
# The highlighted interval is configured in radiation_config.json, not optimized.

if __name__ == '__main__':
    plot_dose(cumulative=True, roles=SCENARIO_ROLES)
