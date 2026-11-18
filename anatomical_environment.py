"""Common OLTARIS BFO environment, separate from the frozen SHIELDOSE reference."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from radiation_model import ROOT, build_temporal_profiles, load_config, sha256, write_preserving
from organize_oltaris_anatomical import validate_doses

DIRECTORY = ROOT / 'data/processed/oltaris'
SUMMARY = DIRECTORY / 'oltaris_sapphire_anatomical_summary.csv'
ORGANS = DIRECTORY / 'oltaris_sapphire_organ_doses.csv'
DATA = DIRECTORY / 'mission_bfo_environment.csv'
MANIFEST = DIRECTORY / 'mission_bfo_environment_manifest.json'
FREEZE = DIRECTORY / 'radiation_environment_freeze.json'
TEMPLATES = ('august_1972', 'october_2003_goes10')
DESCRIPTION = 'SAPPHIRE-derived organ-dose estimates distributed using historical solar particle event timing profiles.'
NASA_REFERENCE = 'https://www.nasa.gov/wp-content/uploads/2023/11/nasa-std-3001-vol-1-rev-c-with-signature.pdf'


def build_environment():
    summary, organs = pd.read_csv(SUMMARY), pd.read_csv(ORGANS)
    validate_doses(summary, organs)
    sources = {str(path.relative_to(ROOT)): sha256(path) for path in (SUMMARY, ORGANS)}
    for frame in (summary, organs):
        for source, expected in frame[['source_path', 'source_sha256']].drop_duplicates().itertuples(index=False):
            if sha256(ROOT / source) != expected:
                raise ValueError('Corrected anatomical source hash mismatch')
            sources[source] = expected
    records = []
    for template in TEMPLATES:
        profiles = build_temporal_profiles(load_config(historical_template=template))
        for source, expected in profiles[['template_source_path', 'template_source_sha256']].drop_duplicates().itertuples(index=False):
            sources[source] = expected
        for _, run in summary.iterrows():
            frame = profiles[['historical_template', 'member_id', 'hour_since_event_start',
                              'bin_duration_h', 'normalized_bin_weight', 'is_gap_filled',
                              'template_timestamp_utc', 'proxy_threshold_MeV', 'gap_method']].copy()
            frame = frame.rename(columns={'member_id': 'timing_variant', 'hour_since_event_start': 'hour'})
            frame['hour_end'] = frame.hour + frame.bin_duration_h
            frame['scenario'] = f'SAPPHIRE-1-in-{int(run.sapphire_return_period_years)}'
            frame['shielding_g_cm2'] = run.aluminum_areal_density_g_cm2
            frame['grid_engine_id'] = run.grid_engine_id
            for quantity, column in [('absorbed_dose_mGy', 'bfo_absorbed_dose_mGy'),
                                     ('gray_equivalent_mGy_eq', 'bfo_gray_equivalent_mGy_eq')]:
                total = float(run[column])
                if not np.isfinite(total) or total <= 0:
                    raise ValueError(f'Invalid anatomical event total: {column}')
                frame[f'event_bfo_{quantity}'] = total
                frame[f'bfo_{quantity}_per_h'] = total * frame.normalized_bin_weight / frame.bin_duration_h
            records.append(frame)
    data = pd.concat(records, ignore_index=True)
    validate_environment(data)
    metadata = dict(schema_version='oltaris_bfo_v1', description=DESCRIPTION,
                    source_sha256=sources, builder_sha256=sha256(Path(__file__)),
                    timing_implementation_sha256=sha256(ROOT / 'radiation_model.py'),
                    anatomy='MAX adult male 2005; no personalization by crew gender or weight',
                    shielding='0.4 and 20 g/cm² aluminium spheres only; no depth interpolation',
                    mission_reference_distance_AU=1.25, source_report_distance_AU=1.2,
                    oltaris_environment_label='SPE free space 1 AU', radial_scaling_factor=1.0,
                    distance_interpretation='Reference solar proton spectra applied to a hypothetical mission near 1.25 AU; magnitudes are not distance-adjusted.',
                    provenance_status='user_supplied_corrected_summaries; native corrected exports pending',
                    temporal_model='Fixed spectral shape; separately unit-normalized complete historical records',
                    health_response_model=None, nasa_rbe_definition_independently_verified=False,
                    quantity_roles={'bfo_absorbed_dose_mGy': 'Exposure input for future biological response models; no response inferred',
                                    'bfo_gray_equivalent_mGy_eq': 'Separate NASA organ-limit reference comparison, not absorbed mGy or mSv'})
    return data, metadata


def validate_environment(data):
    keys = ['historical_template', 'scenario', 'shielding_g_cm2', 'timing_variant']
    if data.duplicated(keys + ['hour']).any():
        raise ValueError('Duplicate anatomical bins')
    for _, member in data.groupby(keys):
        member = member.sort_values('hour')
        if not np.isfinite(member[['hour', 'hour_end', 'bin_duration_h', 'normalized_bin_weight']]).all().all():
            raise ValueError('Nonfinite anatomical timeline')
        np.testing.assert_array_equal(member.hour_end.iloc[:-1], member.hour.iloc[1:])
        if (member.bin_duration_h <= 0).any() or (member.normalized_bin_weight < 0).any():
            raise ValueError('Invalid anatomical intervals/weights')
        np.testing.assert_allclose(member.hour_end - member.hour, member.bin_duration_h)
        np.testing.assert_allclose(member.normalized_bin_weight.sum(), 1, rtol=0, atol=1e-12)
        for quantity in ('absorbed_dose_mGy', 'gray_equivalent_mGy_eq'):
            rates = member[f'bfo_{quantity}_per_h']
            totals = member[f'event_bfo_{quantity}']
            if not np.isfinite(rates).all() or (rates < 0).any() or totals.nunique() != 1:
                raise ValueError('Invalid anatomical dose values')
            np.testing.assert_allclose((rates * member.bin_duration_h).sum(), totals.iloc[0], rtol=1e-12)


def export_environment():
    if FREEZE.exists():
        raise ValueError('Radiation environment v1 is frozen for strategy comparisons; create an explicitly authorized new version instead of overwriting it')
    data, manifest = build_environment()
    write_preserving(DATA, data.to_csv(index=False))
    manifest['csv_sha256'] = sha256(DATA)
    manifest['rows'] = len(data)
    write_preserving(MANIFEST, json.dumps(manifest, indent=2) + '\n')
    return data


def load_environment(template):
    if FREEZE.exists():
        frozen = json.loads(FREEZE.read_text())
        for path in (DATA, MANIFEST):
            if sha256(path) != frozen['artifact_sha256'][path.name]:
                raise ValueError('Frozen anatomical environment changed; restore the frozen artifacts')
    manifest = json.loads(MANIFEST.read_text())
    if manifest['schema_version'] != 'oltaris_bfo_v1' or sha256(DATA) != manifest['csv_sha256']:
        raise ValueError('Anatomical environment checksum/schema mismatch; rebuild explicitly')
    for source, expected in manifest['source_sha256'].items():
        if sha256(ROOT / source) != expected:
            raise ValueError(f'Anatomical source changed: {source}; rebuild explicitly')
    data = pd.read_csv(DATA)
    data = data[data.historical_template.eq(template)].copy()
    if data.empty:
        raise ValueError('Unknown anatomical timing template')
    return data


def interval_exposure(member, start, end, quantity='absorbed_dose_mGy'):
    if quantity not in ('absorbed_dose_mGy', 'gray_equivalent_mGy_eq'):
        raise ValueError('Unsupported BFO quantity')
    keys = ['historical_template', 'scenario', 'shielding_g_cm2', 'timing_variant']
    if member.empty or any(member[key].nunique() != 1 for key in keys):
        raise ValueError('Select exactly one anatomical history')
    if not np.isfinite([start, end]).all() or not member.hour.min() <= start <= end <= member.hour_end.max():
        raise ValueError('Interval outside anatomical radiation record')
    overlap = np.maximum(0, np.minimum(member.hour_end, end) - np.maximum(member.hour, start))
    return float(np.sum(member[f'bfo_{quantity}_per_h'] * overlap))


def nasa_bfo_comparisons(exposure_history):
    """Compare mission contributions only; never certify limits or expose truth to strategies."""
    frame = pd.DataFrame(exposure_history)
    if frame.empty:
        return []
    records = []
    for astronaut, rows in frame.groupby('astronaut'):
        starts, ends = rows.start_hour.to_numpy(), rows.end_hour.to_numpy()
        rates = rows.bfo_gray_equivalent_mGy_eq.to_numpy() / (ends - starts)
        for days, limit in ((30, 250.0), (365, 500.0)):
            hours = days * 24
            boundaries = np.unique(np.r_[starts, ends, starts + hours, ends + hours])
            boundaries = boundaries[boundaries <= ends.max()]
            maximum = max(float(np.sum(rates * np.maximum(0, np.minimum(ends, end) - np.maximum(starts, end - hours))))
                          for end in boundaries)
            records.append(dict(astronaut=astronaut, organ='BFO', window_days=days,
                                max_modeled_mission_contribution_mGy_eq=maximum, reference_limit_mGy_eq=limit,
                                fraction_of_reference=maximum / limit, modeled_contribution_exceeds_reference=maximum > limit,
                                reference='NASA-STD-3001 Vol 1 Rev C, Table 4.8-1', source_url=NASA_REFERENCE,
                                scope='Mission contribution only; prior/background exposure absent; source RBE correspondence unverified',
                                compliance_status='not_assessed'))
    return records


if __name__ == '__main__':
    print(f'Wrote {len(export_environment())} anatomical exposure bins to {DATA.relative_to(ROOT)}')
