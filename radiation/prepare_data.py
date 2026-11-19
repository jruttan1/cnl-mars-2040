"""Rebuild the three small datasets from the previously validated exports.

Ordinary chart use does not need this script. The archived pipeline and its
validation records preserve the earlier raw-to-clean checks.
"""
from pathlib import Path
import argparse
import hashlib
import shutil
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'data/raw/archive/previous_processed'
PROCESSED = ROOT / 'data/processed'


def relocated(path):
    """Resolve old provenance paths without changing archived source contents."""
    path = str(path)
    if path.startswith('data/raw/'):
        tail = path.removeprefix('data/raw/')
        source = 'oltaris' if tail.startswith('OLTARIS') else 'spenvis' if tail.startswith('SAPPHIRE') else 'omniweb'
        return f'data/raw/{source}/{tail}'
    return path


def build(source_dir=ARCHIVE):
    hourly_old = pd.read_csv(source_dir / 'spe_hourly.csv')
    flux = [f'proton_flux_gt{e}_MeV' for e in (10, 30, 60)]
    hourly = hourly_old[['timestamp_utc', 'hours_since_start', *flux,
                         'missing_measurement', 'threshold_order_inversion',
                         'source', 'scenario_id', 'temporal_basis', 'source_path']].copy()
    hourly['flux_unit'] = 'protons/(cm²·s·sr)'
    times = pd.to_datetime(hourly.timestamp_utc, utc=True)
    assert times.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all()
    np.testing.assert_array_equal(hourly.hours_since_start, (times-times.iloc[0]).dt.total_seconds()/3600)
    assert hourly[flux].isna().any(axis=1).equals(hourly.missing_measurement)
    assert not (hourly[flux] < 0).any().any()

    spectra_old = pd.read_csv(source_dir / 'spe_spectra.csv')
    settings = pd.read_csv(source_dir / 'exposure_settings.csv')
    spectral_columns = [c for c in spectra_old if c.startswith(('energy_', 'spacecraft_', 'model_'))]
    scenarios = spectra_old[['scenario_id', *spectral_columns, 'source', 'tool',
                             'shielding', 'temporal_basis', 'source_path']].copy()
    settings_columns = ['mission_average_exposure_factor', 'segment_1_exposure_factor',
                        'mission_total_hours', 'segment_1_orbit_exposure_hours', 'segment_1_exposure_hours']
    scenarios = scenarios.merge(settings[['scenario_id', 'energy_MeV', *settings_columns]],
                                on=['scenario_id', 'energy_MeV'], validate='one_to_one')
    scenarios['return_period_years'] = scenarios.scenario_id.str.extract(r'1-in-(\d+)$')[0].astype(int)
    scenarios['model_distance_AU'] = 1.2  # Explicit in both source reports.
    assert len(scenarios) == len(spectra_old)
    pd.testing.assert_frame_equal(scenarios[spectral_columns], spectra_old[spectral_columns])
    for _, group in scenarios.groupby('scenario_id', sort=False):
        assert group.energy_MeV.diff().iloc[1:].gt(0).all()
        assert (group[spectral_columns] > 0).all().all()
        assert group.spacecraft_integral_protons_cm2.diff().iloc[1:].le(0).all()

    previous = pd.read_csv(source_dir / 'shielding_dose.csv')
    # Keep total depth tables; particle-resolved tables stay available in the archive.
    selected = previous[previous.particle.isna()].copy()
    # The 100-year text export has more digits than its duplicate report table.
    duplicate = selected.scenario_id.eq('SAPPHIRE-1-in-100') & selected.source_path.str.contains('dose-report')
    selected = selected[~duplicate]
    rows = []
    for _, row in selected.iterrows():
        oltaris = row.source == 'OLTARIS'
        column = ('absorbed_dose_mGy' if row.quantity == 'absorbed_dose' else 'dose_equivalent_mSv') if oltaris else (
            'absorbed_dose_rad' if pd.notna(row.absorbed_dose_rad) else 'total_absorbed_dose_rad')
        rows.append(dict(source=row.source, tool=row.tool, scenario_id=row.scenario_id,
                         dose_quantity=row.quantity, dose_value=row[column],
                         dose_unit='mGy' if column.endswith('mGy') else 'mSv' if column.endswith('mSv') else 'rad',
                         geometry='aluminum_tissue_depth_grid' if oltaris else 'center_of_aluminum_sphere',
                         target='tissue', aluminum_depth_g_cm2=row.aluminum_depth_g_cm2,
                         tissue_depth_g_cm2=row.tissue_depth_g_cm2,
                         aluminum_thickness_mm=row.aluminum_thickness_mm,
                         aluminum_areal_density_g_cm2=row.aluminum_areal_density_g_cm2,
                         selected_sphere_g_cm2=np.nan,  # Grid coordinates do not define a selected sphere.
                         configuration_notes=row.shielding,
                         configuration_status=row.configuration_status,
                         validation_status=row.validation_status,
                         temporal_basis=row.temporal_basis, source_path=row.source_path))
    organs = pd.read_csv(source_dir / 'organ_dose.csv')
    for _, row in organs.iterrows():
        rows.append(dict(source=row.source, tool=row.tool, scenario_id=row.scenario_id,
                         dose_quantity='effective_dose_equivalent' if row.reported_quantity_or_organ == 'Effective Dose Equivalent' else 'reported_organ_total',
                         dose_value=row.event_total_mSv, dose_unit='mSv', geometry='user_reported_aluminum_sphere',
                         target=row.reported_quantity_or_organ,
                         selected_sphere_g_cm2=0.4 if 'Al0p4' in row.scenario_id else 20.0,
                         configuration_notes=row.shielding, configuration_status=row.configuration_status,
                         validation_status=row.validation_status, temporal_basis=row.temporal_basis, source_path=row.source_path))
    dose = pd.DataFrame(rows)
    # Exact numerical fidelity: no averaging, interpolation, dose conversion or scenario merging.
    expected = [r['dose_value'] for r in rows]
    np.testing.assert_array_equal(dose.dose_value, expected)
    assert np.isfinite(dose.dose_value).all() and dose.dose_value.ge(0).all()
    assert len(dose) == len(selected) + len(organs)
    assert not dose.duplicated().any()
    result = {'spe_hourly.csv': hourly, 'shielding_dose.csv': dose, 'spe_scenarios.csv': scenarios}
    for frame in result.values():
        frame['source_path'] = frame.source_path.map(relocated)
    from radiation.spenvis_audit import verified_shieldose_rows
    verified = verified_shieldose_rows()
    if not verified.empty:
        result['shielding_dose.csv'] = pd.concat([result['shielding_dose.csv'], verified], ignore_index=True)
    return result


def save(datasets, destination=PROCESSED):
    destination.mkdir(parents=True, exist_ok=True)
    for name, frame in datasets.items():
        target = destination / name
        temporary = destination / (name + '.tmp')
        frame.to_csv(temporary, index=False)
        pd.testing.assert_frame_equal(pd.read_csv(temporary), frame, check_dtype=False, rtol=1e-12)
        if target.exists():
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest == hashlib.sha256(temporary.read_bytes()).hexdigest():
                temporary.unlink()
                continue
            backup = ROOT / 'data/raw/archive/consolidated_backups' / f'{name}.{digest[:16]}'
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(target, backup)
        temporary.replace(target)
        print(f'{name}: {len(frame):,} rows')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    datasets = build()
    for frame in datasets.values():
        assert all((ROOT / p).is_file() for p in frame.source_path.unique()), 'Missing provenance source'
    save(datasets)
