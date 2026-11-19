"""Generate the retained figures and a readable gallery; never rebuild radiation inputs."""
import html
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'results/final-case'
FIGURES = (
    ('results/analysis/anatomical_eva/eva_bfo_comparison.png', '01_astronaut_eva_exposure.png',
     'Astronaut EVA exposure',
     'SAPPHIRE 100-year and 1,000-year anatomical BFO dose with 1972 and 2003 timing. '
     'Includes seven-hour exposure and accumulation; hatched periods are interpolated. '
     'The peak-window examples are retrospective comparisons, not Strategy A schedules.'),
    ('results/mission-runs/final_case_strategy_a/mission_timeline.png', '02_strategy_a_mission_timeline.png',
     'Strategy A mission timeline',
     'Current NTP / 100-year / 1972 example, with qualitative constraints enabled. '
     'Shows who performs each repair and when. Completion does not establish survival or medical safety.'),
    ('results/charts/03_sapphire_spectra.png', '03_storm_severity.png',
     'Storm severity: 100-year versus 1,000-year',
     'Event-integrated SAPPHIRE proton fluence at selected energy thresholds. This is not absorbed dose.'),
    ('results/charts/01_spe_proton_flux.png', '04_historical_storm_timing.png',
     'Historical storm timing',
     'Measured 1972 proton-flux channels supply the timing profile, not measured astronaut dose.'),
    ('results/charts/06_shielding_sensitivity.png', '05_shielding_reference.png',
     'Independent shielding reference',
     'SHIELDOSE-2 tissue-target dose versus aluminium shielding. '
     'This reference is separate from the simulator’s OLTARIS anatomical BFO dose.'),
    ('results/validation/oltaris_anatomical/spectrum_overlay.png', '06_spectrum_fit_validation.png',
     'Spectrum-fit validation',
     'Corrected Band fit against the original SAPPHIRE spectra; the earlier Weibull fit is historical. '
     'Agreement of spectra does not by itself establish dose accuracy.'),
)


def main():
    environment = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONDONTWRITEBYTECODE': '1'}
    for name in ('01_spe_proton_flux.py', '03_sapphire_spectra.py',
                 '06_shielding_sensitivity.py', '09_anatomical_eva_exposure.py'):
        subprocess.run([sys.executable, '-B', str(ROOT / 'charts' / name)],
                       cwd=ROOT, env=environment, check=True)
    subprocess.run([sys.executable, '-B', '-m', 'sim.run_strategy_a', '--recovery',
                    '--engine', 'NTP', '--scenario', 'SAPPHIRE-1-in-100', '--template', 'august_1972',
                    '--output-dir', str(ROOT / 'results/mission-runs/final_case_strategy_a')],
                   cwd=ROOT, env=environment, check=True)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    cards = []
    for source, filename, title, description in FIGURES:
        shutil.copy2(ROOT / source, DESTINATION / filename)
        cards.append(f'<section><h2>{html.escape(title)}</h2><p>{html.escape(description)}</p>'
                     f'<a href="{filename}"><img src="{filename}" alt="{html.escape(title)}"></a></section>')
    gallery = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CNL final-case figures</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#17202a}
h1,h2{line-height:1.2}section{margin:40px 0;border-top:1px solid #dce2e8;padding-top:20px}
img{display:block;width:100%;height:auto}p{max-width:85ch}code{background:#eef2f6;padding:2px 5px}</style>
</head><body><h1>CNL final-case figures</h1>
<p>Start with astronaut exposure and the mission timeline. Click any image for the full-resolution PNG.
The remaining figures support the source, severity and shielding explanation.</p>
<p>Reference solar-proton spectra applied near 1.25 AU without distance rescaling.
Exposure estimates are not predictions of symptoms or individual health outcomes.</p>'''
    gallery += ''.join(cards)
    gallery += '<p>Recreate this gallery: <code>.venv/bin/python -B charts/build_final_case.py</code></p></body></html>'
    (DESTINATION / 'index.html').write_text(gallery, encoding='utf-8')
    print(f'Open {DESTINATION / "index.html"}')


if __name__ == '__main__':
    main()
