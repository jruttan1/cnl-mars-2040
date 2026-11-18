"""Standalone archival/validation workflow; never imports or runs the mission model."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data/raw/oltaris/sapphire_corrected_band_2026-11-16'
OLD = ROOT / 'data/raw/oltaris/sapphire_superseded_weibull_2026-11-16'
PROCESSED = ROOT / 'data/processed/oltaris'
OUT = ROOT / 'outputs/validation/oltaris_anatomical'
SUMMARY_NAME = 'oltaris_sapphire_anatomical_summary.csv'
ORGANS_NAME = 'oltaris_sapphire_organ_doses.csv'
PARAMETER_COLUMNS = ['band_j0_particles_cm2', 'band_r0_MV', 'band_gamma1', 'band_gamma2']


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive(source, destination):
    """Copy bytes without deleting downloads or silently replacing different data."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and digest(source) != digest(destination):
        raise ValueError(f'Archive collision: {destination}')
    if not destination.exists():
        shutil.copy2(source, destination)
    assert digest(source) == digest(destination)
    return dict(original_path=str(source.resolve()), path=str(destination.relative_to(ROOT)),
                sha256=digest(destination), size_bytes=destination.stat().st_size,
                action='copied_byte_for_byte_original_retained')


def band_integral(energy, parameters):
    """Protons/cm²; E in MeV, R0 in MV, dimensionless powers of R/(1 GV)."""
    energy = np.asarray(energy, dtype=float)
    j0, r0, gamma1, gamma2 = parameters
    if np.any(~np.isfinite(energy)) or np.any(energy <= 0):
        raise ValueError('Positive finite proton energies required')
    if not (j0 > 0 and r0 > 0 and 0 < gamma1 < gamma2):
        raise ValueError('Invalid Band parameters')
    rigidity = np.sqrt(energy * (energy + 2 * 938.2720813)) / 1000
    scale = r0 / 1000
    boundary = (gamma2 - gamma1) * scale
    low = np.log(j0) - gamma1 * np.log(rigidity) - rigidity / scale
    high = (np.log(j0) + (gamma2 - gamma1) * np.log(boundary)
            + gamma1 - gamma2 - gamma2 * np.log(rigidity))
    return np.exp(np.where(rigidity <= boundary, low, high))


def source_spectrum(years):
    source = ROOT / f'data/raw/spenvis/sapphire_{years}yr/sapphire_{years}yr_source_report.html'
    soup = BeautifulSoup(source.read_text(), 'html.parser')
    if not re.search(rf'Event frequency:\s*1 in\s*{years} years', soup.get_text()):
        raise ValueError('Wrong source return period')
    tables = [table for table in soup.find_all('table') if 'Fluence at spacecraft' in table.get_text()]
    if len(tables) != 1 or not re.search(r'Model fluence at\s*1.2 AU', tables[0].get_text()):
        raise ValueError('Ambiguous source spectrum/distance')
    rows = []
    for row in tables[0].find_all('tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) == 5:
            rows.append([float(cell.get_text()) for cell in cells])
    values = np.asarray(rows)
    if values.shape != (81, 5) or not np.all(np.diff(values[:, 0]) > 0):
        raise ValueError('Unexpected source grid')
    np.testing.assert_array_equal(values[:, 1], values[:, 3])
    processed = pd.read_csv(ROOT / 'data/processed/spe_scenarios.csv')
    selected = processed[processed.scenario_id.eq(f'SAPPHIRE-1-in-{years}')].sort_values('energy_MeV')
    np.testing.assert_array_equal(values[:, :2], selected[
        ['energy_MeV', 'spacecraft_integral_protons_cm2']].to_numpy())
    return values[:, :2], source


def validate_doses(summary, organs):
    if len(summary) != 4 or summary.scenario_id.duplicated().any():
        raise ValueError('Expected four unique runs')
    if len(organs) != 112 or organs.duplicated(['scenario_id', 'organ']).any():
        raise ValueError('Expected 28 unique organs per run')
    if set(summary.scenario_id) != set(organs.scenario_id):
        raise ValueError('Run identities disagree')
    for frame in (summary, organs):
        columns = [column for column in frame if column.endswith(('_mGy', '_mSv', '_mGy_eq'))]
        values = frame[columns].to_numpy(dtype=float)
        if np.isinf(values).any() or (values < 0).any():
            raise ValueError('Invalid dose values')
    checks = []
    for _, run in summary.iterrows():
        group = organs[organs.scenario_id.eq(run.scenario_id)].set_index('organ')
        if len(group) != 28:
            raise ValueError('Missing organs')
        for column in ('grid_engine_id', 'sapphire_return_period_years', 'aluminum_areal_density_g_cm2'):
            if not group[column].eq(run[column]).all():
                raise ValueError(f'Run metadata mismatch: {column}')
        for organ, prefix, quantities in [
            ('BFO', 'bfo', ('absorbed_dose_mGy', 'dose_equivalent_mSv', 'gray_equivalent_mGy_eq')),
            ('Skin', 'skin', ('absorbed_dose_mGy', 'gray_equivalent_mGy_eq')),
            ('Lens', 'lens', ('absorbed_dose_mGy', 'gray_equivalent_mGy_eq')),
            ('Heart', 'heart', ('gray_equivalent_mGy_eq',)),
            ('CNS', 'cns', ('absorbed_dose_mGy',)),
        ]:
            for quantity in quantities:
                if run[f'{prefix}_{quantity}'] != group.loc[organ, quantity]:
                    raise ValueError(f'Summary/organ mismatch: {run.scenario_id}/{organ}/{quantity}')
                checks.append(f'{run.scenario_id}/{organ}/{quantity}')
    return checks


def save_csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format='%.15g', na_rep='')


def process_current():
    summary = pd.read_csv(RAW / SUMMARY_NAME)
    organs = pd.read_csv(RAW / ORGANS_NAME)
    checks = validate_doses(summary, organs)
    for frame, name in ((summary, SUMMARY_NAME), (organs, ORGANS_NAME)):
        frame['source_path'] = str((RAW / name).relative_to(ROOT))
        frame['source_sha256'] = digest(RAW / name)
        frame['provenance_status'] = 'user_supplied_corrected_run_summary_not_independently_verified_export'
        frame['temporal_basis'] = 'event_total'
        save_csv(frame, PROCESSED / name)
    return summary, checks


def process_previous():
    source = OLD / 'effective_dose_equivalent-3.txt'
    rows = []
    with source.open(newline='') as stream:
        reader = csv.reader(stream, delimiter=';')
        if next(reader)[1] != 'total value ( days) in mSv':
            raise ValueError('Unexpected original effective-dose units')
        for line, fields in enumerate(reader, 2):
            name, value = fields
            rows.append(dict(target=name, quantity='effective_dose_equivalent' if name == 'Effective Dose Equivalent'
                             else 'organ_dose_equivalent', value=float(value), unit='mSv',
                             provenance='original_effective_dose_export', source_path=str(source.relative_to(ROOT)),
                             source_line=line, status='superseded_weibull_run', temporal_basis='event_total'))
    for target, quantity, value, unit in [
        ('BFO', 'absorbed_dose', 474.4, 'mGy'),
        ('BFO', 'gray_equivalent', 713.1, 'mGy-Eq'),
        ('Whole body', 'effective_dose_equivalent', 603.2, 'mSv'),
    ]:
        rows.append(dict(target=target, quantity=quantity, value=value, unit=unit,
                         provenance='user_supplied_project_summary_2026-11-16',
                         source_path=str((OLD / 'provenance.json').relative_to(ROOT)), source_line='',
                         status='superseded_weibull_run', temporal_basis='event_total'))
    save_csv(pd.DataFrame(rows), PROCESSED / 'superseded_weibull_anatomical_doses.csv')


def validate_spectra(summary):
    comparisons, metrics, sources = [], [], []
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex='col', height_ratios=[2, 1])
    for column, years in enumerate((100, 1000)):
        params = summary.loc[summary.sapphire_return_period_years.eq(years), PARAMETER_COLUMNS].drop_duplicates()
        if len(params) != 1:
            raise ValueError('Shielding runs use different source parameters')
        spectrum, source = source_spectrum(years)
        energy, reference = spectrum.T
        estimate = band_integral(energy, params.iloc[0].to_numpy())
        error = 100 * (estimate / reference - 1)
        frame = pd.DataFrame(dict(return_period_years=years, energy_MeV=energy,
                                 sapphire_integral_protons_cm2=reference,
                                 corrected_band_integral_protons_cm2=estimate,
                                 signed_error_percent=error, absolute_error_percent=np.abs(error)))
        if years == 100:
            previous = 1.110e12 * np.exp(-2.25498 * energy ** .27765)
            frame['superseded_weibull_integral_protons_cm2'] = previous
            frame['superseded_weibull_signed_error_percent'] = 100 * (previous / reference - 1)
            axes[0, column].loglog(energy, previous, '--', color='#9b6363', label='Superseded Weibull')
        comparisons.append(frame)
        sources.append(dict(path=str(source.relative_to(ROOT)), sha256=digest(source),
                            return_period_years=years, reported_distance_AU=1.2))
        for lower, upper in ((.1, 1000), (1, 1000), (10, 100), (10, 1000), (100, 1000)):
            selected = frame[frame.energy_MeV.between(lower, upper)]
            worst = selected.loc[selected.absolute_error_percent.idxmax()]
            metrics.append(dict(return_period_years=years, min_energy_MeV=lower, max_energy_MeV=upper,
                                count=len(selected), mean_absolute_error_percent=selected.absolute_error_percent.mean(),
                                max_absolute_error_percent=worst.absolute_error_percent,
                                worst_energy_MeV=worst.energy_MeV))
        axes[0, column].loglog(energy, reference, 'o', ms=3, color='#222222', label='SAPPHIRE source nodes')
        axes[0, column].loglog(energy, estimate, color='#167586', label='Corrected Band')
        axes[0, column].set_title(f'{years:,}-year spectrum')
        axes[0, column].set_ylabel('Integral fluence (protons/cm²)')
        axes[0, column].legend(fontsize=9)
        axes[1, column].semilogx(energy, error, color='#167586')
        axes[1, column].axhline(0, color='0.4', lw=.8)
        axes[1, column].set_ylim(-4, 4)
        axes[1, column].set_ylabel('Band error (%)')
        axes[1, column].set_xlabel('Proton kinetic energy threshold (MeV)')
        for axis in axes[:, column]:
            axis.grid(alpha=.2)
    fig.suptitle('Corrected OLTARIS input spectra vs original SAPPHIRE', fontsize=15)
    fig.text(.5, .01, 'Exact source energies · no interpolation or distance rescaling · source report: 1.2 AU; run label: 1 AU',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, .96))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / 'spectrum_overlay.png', dpi=180)
    plt.close(fig)
    comparison = pd.concat(comparisons, ignore_index=True)
    save_csv(comparison, OUT / 'spectrum_percentage_errors.csv')
    save_csv(pd.DataFrame(metrics), OUT / 'spectrum_metrics.csv')
    return comparison, metrics, sources


def write_report(summary, comparison, metrics):
    lines = ['# Corrected OLTARIS anatomical results and spectrum validation', '',
             '## Recommendation', '',
             'The new files specify **Band**, not Weibull. Keep the old Weibull run as superseded history.',
             'The corrected Band inputs are adequate as a close numerical approximation over the supplied',
             '0.1–1000 MeV grid: maximum absolute integral-fluence error is below 3.2% for both events.',
             'This is a descriptive fit assessment, not a NASA acceptance criterion or validation of organ doses.',
             'The prior Weibull was substantially less accurate and should not be used as the current fit.', '',
             'Before quantitative mission use, resolve the source report’s **1.2 AU** versus run label **1 AU**',
             '(the supplied notes also mention no correction to 1.25 AU). No distance scaling is applied here.',
             'Obtain original corrected OLTARIS exports/input records to independently verify the four reruns.', '',
             '## Dose semantics and provenance', '',
             '- Raw attachments are copied byte-for-byte; SHA-256 hashes and original paths are in provenance.json.',
             '- Four runs and 112 organ records are retained. Corrected data are user-supplied summaries, not raw solver exports.',
             '- Absorbed dose (mGy), dose equivalent (mSv), and Gray Equivalent (mGy-Eq) stay separate.',
             '- Effective dose equivalent is a whole-body weighted quantity, not an organ absorbed dose.',
             '- Missing Gray Equivalent entries remain empty, not zero. Reported Bone zeros are retained, not reinterpreted.',
             '- CNS absorbed dose is retained in mGy as supplied; its cGy-to-mGy conversion is claimed by the supplied source field, not repeated.',
             '- Point absorbed dose is not BFO or whole-body dose. Results are event totals, not daily/yearly rates.',
             '- Spherical aluminium is a surrogate, not verified suit/cabin geometry. Settings and job IDs come from the attachments.',
             '- The old effective-dose export is entirely mSv; its BFO value is 588.90587 mSv.',
             '  Old BFO 474.4 mGy and 713.1 mGy-Eq come only from the earlier user project summary.',
             '  Old summary 603.2 mSv agrees with the exported 603.1618 mSv at displayed precision.',
             '- The old .dat files are depth lookup databases, not organ tables; they are archived without relabeling or conversion.', '',
             '## Corrected anatomical summary', '',
             '| Return period (yr) | Al (g/cm²) | BFO absorbed (mGy) | BFO equivalent (mSv) | BFO Gray Equivalent (mGy-Eq) | Effective equivalent (mSv) |',
             '|---:|---:|---:|---:|---:|---:|']
    for _, row in summary.iterrows():
        lines.append('| ' + ' | '.join(f'{row[column]:g}' for column in [
            'sapphire_return_period_years', 'aluminum_areal_density_g_cm2', 'bfo_absorbed_dose_mGy',
            'bfo_dose_equivalent_mSv', 'bfo_gray_equivalent_mGy_eq', 'effective_dose_equivalent_mSv']) + ' |')
    lines += ['', '## Validation method', '',
              'The two original HTML source reports are parsed directly; all 81 native energies per event',
              'are cross-checked against data/processed/spe_scenarios.csv. Spacecraft and model integral',
              'columns are identical. No interpolation, refitting, transport or dose scaling is performed.',
              'Signed error = 100 × (analytic integral / original integral − 1). Metrics weight each native node equally;',
              'they are not dose-response weighted. Fluence agreement does not bound dose error.', '',
              'Band convention: E in MeV, m = 938.2720813 MeV, r = sqrt(E(E+2m))/1000 (GV),',
              'r0 = supplied R0_MV/1000, rb = (gamma2−gamma1)r0.',
              'Below rb: F = J0 r^(−gamma1) exp(−r/r0). Above rb:',
              'F = J0 rb^(gamma2−gamma1) exp(gamma1−gamma2) r^(−gamma2).',
              'Parameters are read from the corrected summary, without another normalization correction.',
              'The existing outputs/model/band_validation audit documents the earlier MV/GV mismatch and export checks.',
              'That audit’s transport exports are not evidence that these corrected reruns were independently checked.',
              'Previous Weibull comparison uses F = 1.110e12 exp(−2.25498 E^0.27765), never the swapped exponent convention.', '',
              '## Integral-fluence errors at exact source energies', '',
              '| Energy (MeV) | Corrected 100-year (%) | Corrected 1,000-year (%) | Old 100-year Weibull (%) |',
              '|---:|---:|---:|---:|']
    for energy in (.1, 1, 5, 10, 20, 32, 50, 63, 100, 200, 500, 1000):
        selected = comparison[comparison.energy_MeV.eq(energy)].set_index('return_period_years')
        lines.append(f'| {energy:g} | {selected.loc[100, "signed_error_percent"]:+.3f} | '
                     f'{selected.loc[1000, "signed_error_percent"]:+.3f} | '
                     f'{selected.loc[100, "superseded_weibull_signed_error_percent"]:+.3f} |')
    lines += ['', 'Full native-grid errors: spectrum_percentage_errors.csv; band-specific metrics: spectrum_metrics.csv.',
              'Overlay: spectrum_overlay.png. No conclusions are drawn outside 0.1–1000 MeV.', '',
              '## Reproduction and isolation', '',
              'Run `.venv/bin/python organize_oltaris_anatomical.py` after initial archival.',
              'Run `.venv/bin/python -m unittest discover -s tests -p test_oltaris_anatomical.py` for checks.',
              'Only standalone anatomical datasets and validation outputs are written. The frozen baseline,',
              'mission configuration and strategy code are neither imported nor modified. No simulation is run.', '']
    (OUT / 'README.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path)
    parser.add_argument('--organs', type=Path)
    parser.add_argument('--old-downloads', type=Path)
    args = parser.parse_args()
    if bool(args.summary) != bool(args.organs):
        parser.error('Provide both corrected input files, or neither to reuse the archive')
    if args.summary:
        validate_doses(pd.read_csv(args.summary), pd.read_csv(args.organs))
        files = [archive(args.summary, RAW / SUMMARY_NAME), archive(args.organs, RAW / ORGANS_NAME)]
        manifest = dict(archive_date='2026-11-16', source_kind='user_supplied_corrected_run_summaries',
                        supersedes='earlier Weibull anatomical results; not a baseline replacement', files=files,
                        setting_provenance='Attached CSV rows; input decks and corrected raw solver exports not supplied',
                        quantity_units=dict(absorbed_dose='mGy', dose_equivalent='mSv', gray_equivalent='mGy-Eq'),
                        missing_values='Unreported; not zero', temporal_basis='event_total')
        manifest_path = RAW / 'provenance.json'
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    if args.old_downloads:
        files = [archive(args.old_downloads / name, OLD / name) for name in (
            'effective_dose_equivalent-3.txt', 'li_dose_database_mGy-3.dat', 'li_flux_database-3.dat')]
        manifest = dict(status='superseded_weibull_run', archive_date='2026-11-16', files=files,
                        user_supplied_settings=dict(J0=1.110e12, alpha=.27765, k=2.25498,
                            aluminium_sphere_g_cm2=.4, anatomical_model='MAX', environment='SPE, Free Space 1 AU'),
                        user_supplied_project_summary=dict(bfo_absorbed_dose_mGy=474.4,
                            bfo_gray_equivalent_mGy_eq=713.1, effective_dose_equivalent_mSv=603.2),
                        summary_provenance='User message in this thread on 2026-11-16; not derived from effective-dose file',
                        database_header=dict(job_name='job_5', created_local_time='Mon Nov 16 16:49:19 2026',
                            timezone='unspecified in file', taris_version='5.01'),
                        database_interpretation='Dose mGy vs Al/tissue depth; differential particle fluence per EU* per cm2 vs energy/isotope/depth, not anatomical dose',
                        fluence_energy_unit='MeV for photon/electron/positron; MeV/amu otherwise')
        manifest_path = OLD / 'provenance.json'
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    for folder in (RAW, OLD):
        manifest = json.loads((folder / 'provenance.json').read_text())
        for entry in manifest['files']:
            if digest(ROOT / entry['path']) != entry['sha256']:
                raise ValueError('Archived source checksum changed')
    summary, checks = process_current()
    process_previous()
    comparison, metrics, sources = validate_spectra(summary)
    write_report(summary, comparison, metrics)
    (OUT / 'validation.json').write_text(json.dumps(dict(
        checked_summary_organ_pairs=len(checks), source_spectra=sources, spectrum_metrics=metrics,
        distance_rescaling_applied=False, original_grid_nodes_per_event=81,
        corrected_solver_exports_verified=False, simulations_run=False,
        script_sha256=digest(Path(__file__)),
        current_source_manifest=str((RAW / 'provenance.json').relative_to(ROOT))), indent=2) + '\n')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
