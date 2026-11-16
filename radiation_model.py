"""Synthetic SAPPHIRE environment with historical OMNI timing.

SAPPHIRE defines the event spectrum and magnitude. Only spectrum-linked SPENVIS
absorbed-dose results may normalize synthetic doses. King outputs are retained
through explicitly named historical-reference functions.
"""
from pathlib import Path
import hashlib
import json
import shutil
import platform
import numpy as np
import pandas as pd
import scipy
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'radiation_config.json'
SCENARIO = 'Aug1972_King_OMNI_temporal_proxy'
MODEL_VERSION = '1.0'
FLUX_UNIT = 'protons/(cm²·s·sr)'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_preserving(path, content):
    """Keep a content-addressed backup when a generated result changes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode('utf-8')
    if path.exists():
        if path.read_bytes() == encoded:
            return
        name = path.relative_to(ROOT).as_posix().replace('/', '__')
        backup = ROOT / 'data/raw/archive/model_output_versions' / (name + '.' + sha256(path)[:16])
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(path, backup)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(encoded)
    temporary.replace(path)


def load_config(path=CONFIG, historical=False):
    cfg = json.loads(Path(path).read_text())
    if historical:
        cfg['environments'] = cfg['historical_reference_environments']
    require(set(cfg['environments']) == {'external_eva_reference', 'spacecraft_cabin_reference'},
            'Define the two common exposure environments explicitly.')
    require(cfg['central_proxy_MeV'] in cfg['sensitivity_proxy_MeV'], 'Central channel must be in sensitivity channels.')
    require(cfg['central_gap_method'] in cfg['gap_methods'], 'Central gap method must be in gap methods.')
    require(len(set(cfg['gap_methods'])) == len(cfg['gap_methods']), 'Duplicate gap methods.')
    require(len(set(cfg['sensitivity_proxy_MeV'])) == len(cfg['sensitivity_proxy_MeV']), 'Duplicate channels.')
    require(0 <= cfg['eva_start_hour'] and cfg['eva_duration_hours'] > 0 and
            cfg['eva_start_hour'] + cfg['eva_duration_hours'] <= cfg['emergency_duration_hours'],
            'Highlighted interval must fit inside the emergency window.')
    return cfg


def load_hourly():
    """Verify the processed measurements against the original six-field export."""
    data = pd.read_csv(ROOT / 'data/processed/spe_hourly.csv')
    data['timestamp_utc'] = pd.to_datetime(data.timestamp_utc, utc=True)
    times = data.timestamp_utc
    require(not times.isna().any() and not times.duplicated().any() and times.is_monotonic_increasing,
            'Invalid, duplicate or unsorted timestamps.')
    require(times.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all(), 'Expected consecutive one-hour bins.')
    require(data.flux_unit.eq(FLUX_UNIT).all(), 'Unexpected flux unit.')
    require(data.source.eq('OMNIWeb').all() and data.temporal_basis.eq('hourly_average').all(), 'Not OMNI hourly averages.')
    np.testing.assert_allclose(data.hours_since_start, (times-times.iloc[0]).dt.total_seconds()/3600, rtol=0, atol=0)
    require(data.source_path.nunique() == 1, 'Ambiguous OMNI source.')
    raw = pd.read_csv(ROOT / data.source_path.iloc[0], sep=r'\s+', header=None)
    require(raw.shape == (len(data), 6), 'Unexpected raw OMNI shape.')
    raw_times = pd.to_datetime(raw[0].astype(str), format='%Y', utc=True) + pd.to_timedelta(raw[1]-1, unit='D') + pd.to_timedelta(raw[2], unit='h')
    require((times == raw_times).all(), 'Processed/raw timestamp mismatch.')
    for i, energy in enumerate((10, 30, 60), start=3):
        values = data[f'proton_flux_gt{energy}_MeV']
        np.testing.assert_allclose(values, raw[i].mask(raw[i].eq(99999.99)), rtol=0, atol=0, equal_nan=True)
        require(np.isfinite(values.dropna()).all() and values.dropna().ge(0).all(), 'Invalid observed flux.')
    data['bin_duration_h'] = 1.0
    return data


def parse_absorbed_grid(path):
    """Read only the inspected two-axis mGy format; reject anything else."""
    text = Path(path).read_text()
    require('Dose (mGy) vs. Depth (g/cm2)' in text, 'Expected absorbed dose in mGy, not mSv.')
    require('Depth in aluminum@2.7 unit= g/cm2' in text and 'Depth in tissue@1.0 unit= g/cm2' in text,
            'Unknown depth axes or units.')
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith('C')]
    tokens = ' '.join(lines).split()
    offset = 0
    axes = []
    for _ in range(2):
        lo, hi = map(int, tokens[offset:offset+2]); offset += 2
        require(lo == 1 and hi >= lo, 'Unsupported axis bounds.')
        axes.append(np.array(tokens[offset:offset+hi], dtype=float)); offset += hi
    dims = list(map(int, tokens[offset:offset+4])); offset += 4
    require(dims == [1, len(axes[0]), 1, len(axes[1])], 'Inconsistent grid dimensions.')
    values = np.array(tokens[offset:], dtype=float)
    require(len(values) == len(axes[0])*len(axes[1]) and np.isfinite(values).all() and (values >= 0).all(),
            'Malformed absorbed-dose payload.')
    return pd.DataFrame({'aluminum_depth_g_cm2': np.tile(axes[0], len(axes[1])),
                         'tissue_depth_g_cm2': np.repeat(axes[1], len(axes[0])),
                         'dose_value': values})


def load_historical_shielding(cfg):
    dose = pd.read_csv(ROOT / 'data/processed/shielding_dose.csv')
    references, grids = {}, {}
    for location, spec in cfg['environments'].items():
        grid = dose[(dose.source == 'OLTARIS') & (dose.scenario_id == spec['oltaris_scenario_id']) &
                    (dose.dose_quantity == 'absorbed_dose') & (dose.dose_unit == 'mGy') &
                    (dose.geometry == 'aluminum_tissue_depth_grid') & (dose.target == 'tissue')].copy()
        require(not grid.empty and grid.source_path.nunique() == 1, f'Missing/ambiguous absorbed grid for {location}.')
        require(grid.temporal_basis.eq('event_integrated').all(), 'Expected an event-integrated dose.')
        raw_path = ROOT / grid.source_path.iloc[0]
        raw = parse_absorbed_grid(raw_path)
        keys = ['aluminum_depth_g_cm2', 'tissue_depth_g_cm2']
        pd.testing.assert_frame_equal(grid[keys+['dose_value']].sort_values(keys).reset_index(drop=True),
                                      raw.sort_values(keys).reset_index(drop=True), check_dtype=False, rtol=1e-12)
        target = grid[grid.tissue_depth_g_cm2.eq(cfg['tissue_depth_g_cm2'])].sort_values(keys[0])
        require(not target.empty and not target.aluminum_depth_g_cm2.duplicated().any(), 'Missing/duplicate tissue-depth slice.')
        selected = target[target.aluminum_depth_g_cm2.eq(spec['shielding_g_cm2'])]
        require(len(selected) == 1, f'No exact shielding coordinate for {location}; no approximation is performed.')
        row = selected.iloc[0]
        text = raw_path.read_text()
        job = next(line.split('Job Name:', 1)[1].strip() for line in text.splitlines() if 'Job Name:' in line)
        references[location] = dict(**spec, event_absorbed_dose_mGy=float(row.dose_value),
                                    tissue_depth_g_cm2=cfg['tissue_depth_g_cm2'], geometry=row.geometry,
                                    source_path=row.source_path, source_sha256=sha256(raw_path), job_name=job,
                                    configuration_status=row.configuration_status,
                                    evidence='exact_exported_absorbed_dose_grid_value',
                                    location_interpretation='illustrative grid-based reference; not verified suit/cabin geometry')
        grids[location] = target.reset_index(drop=True)
    require(references['external_eva_reference']['geometry'] == references['spacecraft_cabin_reference']['geometry'],
            'Reference geometries must match.')
    return references, grids


def fill_gaps(observed, method):
    """Fill interior NaNs only; observations are unchanged. No boundary extrapolation."""
    y = np.asarray(observed, dtype=float)
    missing = np.isnan(y)
    require(len(y) > 1 and not missing[0] and not missing[-1], 'Cannot extrapolate missing event boundaries.')
    good = ~missing
    require(np.isfinite(y[good]).all() and (y[good] >= 0).all(), 'Invalid measured flux.')
    x = np.arange(len(y), dtype=float)
    result = y.copy()
    if method == 'linear':
        result[missing] = np.interp(x[missing], x[good], y[good])
    elif method == 'log_linear':
        require((y[good] > 0).all(), 'Log-linear filling requires positive observations; no arbitrary floor is added.')
        result[missing] = np.exp(np.interp(x[missing], x[good], np.log(y[good])))
    elif method == 'pchip':
        result[missing] = PchipInterpolator(x[good], y[good], extrapolate=False)(x[missing])
    else:
        raise ValueError(f'Unknown gap method: {method}')
    require(np.isfinite(result).all() and (result >= 0).all(), 'Gap filling produced invalid values.')
    np.testing.assert_array_equal(result[good], y[good])
    return result


def normalize_profile(flux, durations):
    """Dimensionless bin weights. This is temporal allocation, not flux-to-dose conversion."""
    weighted = np.asarray(flux) * np.asarray(durations)
    require(np.isfinite(weighted).all() and (weighted >= 0).all() and weighted.sum() > 0, 'Invalid normalization.')
    weights = weighted / weighted.sum()
    np.testing.assert_allclose(weights.sum(), 1.0, rtol=0, atol=1e-12)
    return weights


def select_window(hourly, cfg):
    start = pd.Timestamp(cfg['emergency_start_utc'])
    require(start.tzinfo is not None, 'Emergency start must include UTC/timezone information.')
    start = start.tz_convert('UTC')
    duration = cfg['emergency_duration_hours']
    require(duration > 0 and float(duration).is_integer(), 'Emergency duration must be a positive whole number of hours.')
    require(start == start.floor('h'), 'Emergency start must align with an hourly bin.')
    end = start + pd.Timedelta(hours=duration)
    require(start >= hourly.timestamp_utc.iloc[0] and end <= hourly.timestamp_utc.iloc[-1]+pd.Timedelta(hours=1),
            'Emergency window falls outside the modeled record; no extrapolation is allowed.')
    return (hourly.timestamp_utc >= start) & (hourly.timestamp_utc < end), start


def accumulated_dose(intervals, start_hour, end_hour):
    """Integrate one location/member using exact bin overlaps, including partial hours."""
    require(np.isfinite([start_hour, end_hour]).all() and end_hour >= start_hour,
            'Exposure endpoints must be finite and ordered.')
    for column in ('scenario_id', 'location', 'member_id'):
        if column in intervals:
            require(intervals[column].nunique() == 1, f'Select one {column} before integrating.')
    bins = intervals.sort_values('hour_since_emergency')
    starts = bins.hour_since_emergency.to_numpy()
    ends = bins.hour_end_since_emergency.to_numpy()
    require(len(bins) > 0 and np.all(ends > starts), 'Invalid intervals.')
    require(np.allclose(starts[1:], ends[:-1], rtol=0, atol=1e-12), 'Overlapping or missing intervals.')
    require(start_hour >= starts[0] and end_hour <= ends[-1], 'Exposure window outside available bins.')
    rates = bins.absorbed_dose_rate_mGy_h.to_numpy()
    require(np.isfinite(rates).all() and (rates >= 0).all(), 'Invalid absorbed-dose rates.')
    overlap = np.maximum(0, np.minimum(ends, end_hour) - np.maximum(starts, start_hour))
    return float(np.dot(overlap, bins.absorbed_dose_rate_mGy_h))


def seven_hour_exposure(intervals, start_hour):
    return accumulated_dose(intervals, start_hour, start_hour + 7)


def sensitivity_bounds(frame, value_column, central_proxy=None):
    """Pointwise envelopes of complete trajectories, not independent integrated bounds."""
    chosen = frame if central_proxy is None else frame[frame.proxy_threshold_MeV.eq(central_proxy)]
    return chosen.groupby('hour_since_emergency', sort=True)[value_column].agg(lower='min', upper='max')


def build_historical_environment(config_path=CONFIG):
    cfg = load_config(config_path, historical=True)
    hourly = load_hourly()
    references, grids = load_historical_shielding(cfg)
    mask, emergency_start = select_window(hourly, cfg)
    durations = hourly.bin_duration_h.to_numpy()
    full_profiles, records, checks = [], [], []
    config_hash = sha256(config_path)
    for channel in cfg['sensitivity_proxy_MeV']:
        require(channel in (10, 30, 60), 'Unsupported measured channel.')
        observed = hourly[f'proton_flux_gt{channel}_MeV'].to_numpy()
        for method in cfg['gap_methods']:
            filled = fill_gaps(observed, method)
            weights = normalize_profile(filled, durations)
            member_id = f'gt{channel}MeV__{method}'
            central = channel == cfg['central_proxy_MeV'] and method == cfg['central_gap_method']
            full_profiles.append(pd.DataFrame({
                'timestamp_utc': hourly.timestamp_utc, 'hour_since_record_start': hourly.hours_since_start,
                'bin_duration_h': durations, 'member_id': member_id, 'proxy_threshold_MeV': channel,
                'gap_method': method, 'observed_proton_flux': observed, 'modeled_proton_flux': filled,
                'flux_unit': FLUX_UNIT, 'is_gap_filled': np.isnan(observed),
                'normalized_bin_weight': weights, 'in_emergency_window': mask.to_numpy()}))
            for location, ref in references.items():
                event_dose = ref['event_absorbed_dose_mGy']
                full_rates = event_dose * weights / durations
                np.testing.assert_allclose(np.dot(full_rates, durations), event_dose, rtol=1e-12)
                rates = full_rates[mask]
                increments = rates * durations[mask]
                cumulative = np.concatenate(([0.0], np.cumsum(increments)))
                elapsed = (hourly.loc[mask, 'timestamp_utc'] - emergency_start).dt.total_seconds()/3600
                frame = pd.DataFrame({
                    'scenario_id': SCENARIO, 'timestamp_utc': hourly.loc[mask, 'timestamp_utc'].to_numpy(),
                    'hour_since_emergency': elapsed.to_numpy(), 'hour_end_since_emergency': elapsed.to_numpy()+1,
                    'location': location, 'shielding_g_cm2': ref['shielding_g_cm2'],
                    'tissue_depth_g_cm2': ref['tissue_depth_g_cm2'], 'geometry': ref['geometry'],
                    'absorbed_dose_rate_mGy_h': rates, 'absorbed_dose_in_bin_mGy': increments,
                    'cumulative_absorbed_dose_mGy': cumulative[:-1],
                    'cumulative_end_absorbed_dose_mGy': cumulative[1:],
                    'estimate_type': 'central' if central else 'sensitivity_member',
                    'member_id': member_id, 'proxy_threshold_MeV': channel, 'gap_method': method,
                    'observed_proton_flux': observed[mask], 'modeled_proton_flux': filled[mask],
                    'flux_unit': FLUX_UNIT, 'is_gap_filled': np.isnan(observed[mask]),
                    'normalized_bin_weight': weights[mask], 'event_absorbed_dose_mGy': event_dose,
                    'source_model': 'OLTARIS absorbed-dose grid + normalized OMNIWeb temporal proxy',
                    'oltaris_scenario_id': ref['oltaris_scenario_id'], 'source_path': ref['source_path'],
                    'source_sha256': ref['source_sha256'], 'configuration_status': ref['configuration_status'],
                    'normalization_start_utc': hourly.timestamp_utc.iloc[0].isoformat(),
                    'normalization_end_utc': (hourly.timestamp_utc.iloc[-1]+pd.Timedelta(hours=1)).isoformat(),
                    'normalization_duration_h': float(durations.sum()),
                    'normalization_assumption': 'full event dose allocated to entire available record; event closure unverified',
                    'dose_interpretation': 'estimated grid-target dose; not whole-body or verified cabin/suit dose',
                    'config_sha256': config_hash, 'model_version': MODEL_VERSION})
                require(np.all(np.diff(cumulative) >= 0), 'Cumulative dose decreased.')
                a, b = cfg['eva_start_hour'], cfg['eva_start_hour']+cfg['eva_duration_hours']
                exposure = accumulated_dose(frame, a, b)
                edges = np.r_[frame.hour_since_emergency, frame.hour_end_since_emergency.iloc[-1]]
                expected = np.interp(b, edges, cumulative) - np.interp(a, edges, cumulative)
                np.testing.assert_allclose(exposure, expected, rtol=1e-12, atol=1e-10)
                checks.append(dict(member_id=member_id, location=location, weight_sum=float(weights.sum()),
                                   full_record_integrated_mGy=float(np.dot(full_rates, durations)),
                                   event_total_mGy=event_dose, emergency_total_mGy=float(cumulative[-1]),
                                   highlighted_interval_mGy=exposure))
                records.append(frame)
    mission = pd.concat(records, ignore_index=True)
    profiles = pd.concat(full_profiles, ignore_index=True)
    # Each location/member is a coherent trajectory. Derived envelope fields are NOT trajectories.
    metrics = ['absorbed_dose_rate_mGy_h', 'cumulative_absorbed_dose_mGy', 'cumulative_end_absorbed_dose_mGy']
    for metric in metrics:
        group = mission.groupby(['location', 'hour_since_emergency'])[metric]
        mission[metric + '_sensitivity_lower'] = group.transform('min')
        mission[metric + '_sensitivity_upper'] = group.transform('max')
        require((mission[metric] >= mission[metric+'_sensitivity_lower']).all() and
                (mission[metric] <= mission[metric+'_sensitivity_upper']).all(), 'Inconsistent sensitivity envelope.')
    # Identical underlying event profiles for EVA/cabin; only the shielding response changes.
    for _, group in mission.groupby(['member_id', 'hour_since_emergency']):
        require(len(group) == 2 and group.normalized_bin_weight.nunique() == 1, 'Locations do not share one event profile.')
    all_grids_equal = np.array_equal(grids['external_eva_reference'].dose_value, grids['spacecraft_cabin_reference'].dose_value)
    report = dict(model_version=MODEL_VERSION, config=cfg, config_sha256=config_hash,
                  runtime={'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__},
                  input_sha256={str(p.relative_to(ROOT)): sha256(p) for p in (ROOT/'data/processed').glob('*.csv') if p.name != 'mission_radiation_environment.csv'},
                  references=references, full_record_hours=float(durations.sum()), modeled_members=mission.member_id.nunique(),
                  missing_hours_utc=hourly.loc[hourly.missing_measurement, 'timestamp_utc'].astype(str).tolist(),
                  identical_target_depth_tables_between_jobs=all_grids_equal, validation_checks=checks,
                  scientific_limits=[
                      'Entire available record is assumed to receive the King event total; physical event closure is unverified.',
                      'OMNIWeb is a near-Earth profile; no Earth-to-Mars propagation, distance scaling or event-arrival forecast is applied.',
                      'King spectrum and measured OMNI spectrum are not established as identical.',
                      'Each proxy assumes fixed dose response through time; channels are alternative timing proxies, not additive dose components.',
                      'Gap filling cannot recover unobserved peaks; envelope is a scenario sensitivity range, not a confidence interval or physical bound.',
                      'EVA/cabin refer to exact exported grid depths; sphere/organ mSv outputs are not used. Actual location geometries remain unverified.',
                      'SHIELDOSE scenario associations are unresolved and MULASSIS doses are NaN; neither contributes to baseline dose.',
                      'No reactor radiation, strategy optimization, biodosimetry or crew scheduling.'])
    return cfg, mission, profiles, grids, report


def export_historical_environment(config_path=CONFIG):
    result = build_historical_environment(config_path)
    cfg, mission, profiles, grids, report = result
    write_preserving(ROOT/'outputs/model/historical/mission_radiation_environment.csv', mission.to_csv(index=False))
    write_preserving(ROOT/'outputs/model/historical/full_event_profiles.csv', profiles.to_csv(index=False))
    write_preserving(ROOT/'outputs/model/historical/radiation_environment_audit.json', json.dumps(report, indent=2)+'\n')
    print(f'Validated {len(mission):,} mission rows; {mission.member_id.nunique()} temporal members; full-record normalization {report["full_record_hours"]:g} h.')
    return result


class MissingTransportError(ValueError):
    """A synthetic spectrum must not borrow the King event's dose normalization."""


def build_temporal_profiles(cfg):
    """Unit-sum timing templates for the complete available record, with gap flags."""
    hourly = load_hourly()
    mask, start = select_window(hourly, cfg)
    records = []
    for channel in cfg['sensitivity_proxy_MeV']:
        require(channel in (10, 30, 60), 'Unsupported measured channel.')
        observed = hourly[f'proton_flux_gt{channel}_MeV'].to_numpy()
        for method in cfg['gap_methods']:
            filled = fill_gaps(observed, method)
            records.append(pd.DataFrame({
                'template_timestamp_utc': hourly.timestamp_utc,
                'hour_since_event_start': hourly.hours_since_start,
                'hour_since_emergency': (hourly.timestamp_utc-start).dt.total_seconds()/3600,
                'bin_duration_h': hourly.bin_duration_h,
                'member_id': f'gt{channel}MeV__{method}', 'proxy_threshold_MeV': channel,
                'gap_method': method, 'observed_proton_flux': observed, 'modeled_proton_flux': filled,
                'observed_flux_unit': FLUX_UNIT, 'is_gap_filled': np.isnan(observed),
                'normalized_bin_weight': normalize_profile(filled, hourly.bin_duration_h),
                'in_emergency_window': mask,
                'estimate_type': 'central' if channel == cfg['central_proxy_MeV'] and method == cfg['central_gap_method'] else 'sensitivity_member'}))
    return pd.concat(records, ignore_index=True)


def build_synthetic_fluence(spectra, profiles, cfg):
    """Allocate each spectral bin's event fluence using the central timing template.

No sr-to-area conversion is applied: OMNI contributes dimensionless weights only.
The spectrum is assumed fixed through time. Alternative timing members are saved
separately so their weights can be applied without duplicating the entire spectrum.
"""
    central = profiles[profiles.estimate_type.eq('central')]
    rows = []
    for spec in cfg['synthetic_scenarios']:
        spectrum = spectra[spectra.scenario_id.eq(spec['scenario_id'])]
        require(not spectrum.empty, 'Configured SAPPHIRE spectrum is missing.')
        product = spectrum[['scenario_id','energy_MeV','spacecraft_integral_protons_cm2',
                            'spacecraft_differential_protons_cm2_MeV','spectrum_sha256','model_distance_AU']].merge(central,how='cross')
        product['scenario_role'] = spec['role']
        product['integral_fluence_in_bin_protons_cm2'] = product.spacecraft_integral_protons_cm2*product.normalized_bin_weight
        product['differential_fluence_in_bin_protons_cm2_MeV'] = product.spacecraft_differential_protons_cm2_MeV*product.normalized_bin_weight
        product['user_reported_simulation_distance_AU'] = cfg['user_reported_simulation_distance_AU']
        product['applied_radial_scaling_factor'] = cfg['applied_radial_scaling_factor']
        product['source_model'] = 'Synthetic SAPPHIRE SPE using August 1972 historical temporal template'
        for energy, group in product.groupby('energy_MeV'):
            np.testing.assert_allclose(group.integral_fluence_in_bin_protons_cm2.sum(),group.spacecraft_integral_protons_cm2.iloc[0],rtol=1e-12)
            np.testing.assert_allclose(group.differential_fluence_in_bin_protons_cm2_MeV.sum(),group.spacecraft_differential_protons_cm2_MeV.iloc[0],rtol=1e-12)
        rows.append(product)
    return pd.concat(rows,ignore_index=True)


def load_sapphire_doses(spectra, cfg):
    """Accept only reviewed, spectrum-linked absorbed-dose rows. Fail closed.

Future imports must retain the input-spectrum hash and a reviewed linkage-evidence
file/hash, as well as the transport source hash. Changing a folder label is insufficient.
"""
    table = pd.read_csv(ROOT/'data/processed/shielding_dose.csv')
    from spenvis_audit import verified_shieldose_rows
    raw_verified=verified_shieldose_rows(spectra)
    approved=table[table.validation_status.eq('validated_spectrum_link')].copy()
    keys=['scenario_id','aluminum_areal_density_g_cm2']
    columns=keys+['dose_value','dose_unit','source_path','source_sha256','input_spectrum_sha256',
                  'source_report_sha256','transport_report_sha256','geometry','target','temporal_basis',
                  'irradiation_geometry','proton_nuclear_attenuation_included']
    if not approved.empty:
        require(not approved.duplicated(keys).any(),'Duplicate verified shielding rows.')
        pd.testing.assert_frame_equal(approved[columns].sort_values(keys).reset_index(drop=True),
            raw_verified[columns].sort_values(keys).reset_index(drop=True),check_dtype=False,rtol=1e-12)
    matches, missing = [], []
    environments=dict(cfg['environments'])
    # Retain all six exported depths in reusable data; plots select the two named references.
    for depth in raw_verified.aluminum_areal_density_g_cm2.unique() if not raw_verified.empty else []:
        if depth not in [e['shielding_g_cm2'] for e in environments.values()]:
            environments[f'shielding_{depth:g}_g_cm2']=dict(shielding_g_cm2=float(depth),geometry='center_of_aluminum_sphere',target='tissue')
    for spec in cfg['synthetic_scenarios']:
        for location, env in environments.items():
            candidates = table[(table.source == 'SPENVIS') & (table.scenario_id == spec['scenario_id']) &
                table.tool.isin(['SHIELDOSE-2','MULASSIS']) & (table.dose_quantity == 'absorbed_dose') &
                (table.validation_status == 'validated_spectrum_link') &
                (table.configuration_status == 'verified_sapphire_input') &
                (table.geometry == env['geometry']) & (table.target == env['target']) &
                (table.aluminum_areal_density_g_cm2 == env['shielding_g_cm2'])]
            if candidates.empty:
                missing.append(f'{spec["scenario_id"]} / {location}: no verified absorbed-dose result at {env["shielding_g_cm2"]:g} g/cm² for {env["geometry"]}, {env["target"]}.')
                continue
            require(len(candidates)==1, 'Ambiguous transport rows; select one verified calculation.')
            row = candidates.iloc[0]
            require(row.temporal_basis == 'event_integrated', 'Transport normalization must explicitly be event-integrated.')
            require(row.dose_unit in ('mGy','Gy','rad'), 'Only absorbed-dose units can normalize synthetic dose.')
            require(np.isfinite(row.dose_value) and row.dose_value > 0, 'Invalid absorbed-dose value.')
            required = ['input_spectrum_sha256','input_link_evidence_path','input_link_evidence_sha256','source_sha256']
            require(all(c in row.index and pd.notna(row[c]) for c in required), 'Missing spectrum-link provenance.')
            spectrum_hash = spectra.loc[spectra.scenario_id.eq(spec['scenario_id']),'spectrum_sha256'].iloc[0]
            require(row.input_spectrum_sha256 == spectrum_hash, 'Transport uses a different spectrum export.')
            for name, expected in [(row.source_path,row.source_sha256),(row.input_link_evidence_path,row.input_link_evidence_sha256)]:
                path = ROOT/name
                require(path.is_file() and sha256(path)==expected, f'Missing or changed transport evidence: {name}')
            matches.append(dict(scenario_id=spec['scenario_id'],scenario_role=spec['role'],location=location,
                shielding_g_cm2=env['shielding_g_cm2'],geometry=row.geometry,target=row.target,
                return_period_years=spec['return_period_years'],irradiation_geometry=row.irradiation_geometry,
                proton_nuclear_attenuation_included=row.proton_nuclear_attenuation_included,
                dose_interpretation='Absorbed dose in an idealized tissue target at the centre of aluminium spheres; not organ or whole-body astronaut dose',
                dose_quantity='absorbed_dose',target_type='idealized_tissue',target_geometry='centre_of_aluminium_spheres',
                unit='mGy',dose_rate_unit='mGy/h',nuclear_attenuation=False,
                source_report_path=row.source_report_path,source_report_sha256=row.source_report_sha256,
                transport_report_path=row.transport_report_path,transport_report_sha256=row.transport_report_sha256,
                event_absorbed_dose_mGy=float(row.dose_value)*{'mGy':1,'Gy':1000,'rad':10}[row.dose_unit],
                source_model=f'{row.tool} / SAPPHIRE + August 1972 temporal template',
                source_path=row.source_path,source_sha256=row.source_sha256,input_spectrum_sha256=spectrum_hash,
                input_link_evidence_path=row.input_link_evidence_path,input_link_evidence_sha256=row.input_link_evidence_sha256))
    return matches, missing


def calculate_sapphire_dose(profiles, references):
    """One common environmental baseline per verified scenario/location/member."""
    full, window = [], []
    for ref in references:
        for member, profile in profiles.groupby('member_id',sort=False):
            frame = profile.copy().sort_values('hour_since_event_start')
            for key,value in ref.items(): frame[key]=value
            frame['absorbed_dose_rate_mGy_h'] = frame.event_absorbed_dose_mGy*frame.normalized_bin_weight/frame.bin_duration_h
            frame['hour_end_since_emergency'] = frame.hour_since_emergency+frame.bin_duration_h
            increments = frame.absorbed_dose_rate_mGy_h*frame.bin_duration_h
            np.testing.assert_allclose(increments.sum(),ref['event_absorbed_dose_mGy'],rtol=1e-12)
            frame['cumulative_event_absorbed_dose_mGy'] = increments.cumsum()
            frame['spectrum_time_assumption'] = 'fixed SAPPHIRE spectrum; historical OMNI timing independent of event magnitude'
            full.append(frame)
            cut = frame[frame.in_emergency_window].copy()
            amounts = cut.absorbed_dose_rate_mGy_h*cut.bin_duration_h
            cut['cumulative_end_absorbed_dose_mGy'] = amounts.cumsum()
            cut['cumulative_absorbed_dose_mGy'] = cut.cumulative_end_absorbed_dose_mGy-amounts
            cut.iloc[0,cut.columns.get_loc('cumulative_absorbed_dose_mGy')]=0.0
            require(cut.cumulative_end_absorbed_dose_mGy.is_monotonic_increasing,'Cumulative dose decreased.')
            window.append(cut)
    if not full: return pd.DataFrame(),pd.DataFrame()
    full_frame,mission=pd.concat(full,ignore_index=True),pd.concat(window,ignore_index=True)
    for metric in ['absorbed_dose_rate_mGy_h','cumulative_absorbed_dose_mGy','cumulative_end_absorbed_dose_mGy']:
        group=mission.groupby(['scenario_id','location','hour_since_emergency'])[metric]
        mission[metric+'_sensitivity_lower']=group.transform('min')
        mission[metric+'_sensitivity_upper']=group.transform('max')
    mission['interval_interpretation']='model-generated timing sensitivity range; not a statistical confidence interval'
    return full_frame,mission


def build_environment(config_path=CONFIG):
    """Build synthetic inputs; unavailable dose is explicit, never borrowed from OLTARIS."""
    from spenvis_audit import load_verified_spectra,audit_transport
    cfg = load_config(config_path)
    require(cfg['applied_radial_scaling_factor']==1.0,'Use the exported fluences without additional radial attenuation.')
    require([(s['return_period_years'],s['role']) for s in cfg['synthetic_scenarios']]==[(100,'main'),(1000,'worst_case')],
            'Use 100-year main and 1,000-year worst-case scenarios separately.')
    spectra = load_verified_spectra()
    audit = audit_transport(spectra)
    profiles = build_temporal_profiles(cfg)
    fluence = build_synthetic_fluence(spectra,profiles,cfg)
    references,missing = load_sapphire_doses(spectra,cfg)
    full,mission = calculate_sapphire_dose(profiles,references)
    exposures=[]
    if not mission.empty:
        for (scenario,location,member),group in mission.groupby(['scenario_id','location','member_id']):
            a=cfg['eva_start_hour']; b=a+cfg['eva_duration_hours']
            exposures.append(dict(scenario_id=scenario,location=location,member_id=member,
                interval_start_hour=a,interval_end_hour=b,absorbed_dose_mGy=accumulated_dose(group,a,b),
                shielding_g_cm2=group.shielding_g_cm2.iloc[0],estimate_type=group.estimate_type.iloc[0],
                scenario_role=group.scenario_role.iloc[0],dose_quantity='absorbed_dose',target_type='idealized_tissue',
                geometry=group.geometry.iloc[0],target_geometry='centre_of_aluminium_spheres',unit='mGy',nuclear_attenuation=False))
    audit.update(status='blocked_missing_transport' if not references else ('partial' if missing else 'ready'),
        missing_matches=missing,config=cfg,config_sha256=sha256(config_path),
        model_source_sha256=sha256(Path(__file__)),full_template_duration_hours=264,
        template_record_assumption='Available 264-hour record defines the complete assumed synthetic event; physical event closure is unverified.',
        spectral_timing_assumption='Fixed SAPPHIRE spectrum through time; historical threshold channels are alternative timing proxies, not independent spectral dose components.',
        timing_uncertainty='Interior log-linear, linear and PCHIP fills; nine timing members; no confidence intervals or bound on unobserved peaks.',
        mission_date_note='1972 timestamps identify the historical template; they are not a predicted 2040 event date.',
        distance_note=cfg['radial_scaling_note'],verified_references=references)
    return dict(config=cfg,spectra=spectra,profiles=profiles,fluence=fluence,full_dose=full,
                mission=mission,exposures=pd.DataFrame(exposures),audit=audit)


BASELINE_PATH = ROOT / 'data/processed/mission_radiation_environment.csv'
BASELINE_MANIFEST = ROOT / 'outputs/model/baseline_manifest.json'
BASELINE_VERSION = '1.0'


def baseline_dataset(full_event):
    """Strategy-facing full-event table. Hour/cumulative dose refer to bin START."""
    frame=full_event.copy()
    frame['scenario']=frame.scenario_id
    frame['hour']=frame.hour_since_event_start
    frame['hour_end']=frame.hour+frame.bin_duration_h
    frame['dose_rate_mGy_h']=frame.absorbed_dose_rate_mGy_h
    frame['cumulative_end_dose_mGy']=frame.cumulative_event_absorbed_dose_mGy
    frame['cumulative_dose_mGy']=frame.cumulative_end_dose_mGy-frame.dose_rate_mGy_h*frame.bin_duration_h
    frame.loc[frame.hour.eq(0),'cumulative_dose_mGy']=0.0
    frame['timing_variant']=frame.member_id
    frame['data_quality']=np.where(frame.is_gap_filled,'interpolated_template_gap','observed_template_hour')
    frame['baseline_version']=BASELINE_VERSION
    for metric in ['dose_rate_mGy_h','cumulative_dose_mGy','cumulative_end_dose_mGy']:
        group=frame.groupby(['scenario','shielding_g_cm2','hour'])[metric]
        frame[metric+'_sensitivity_lower']=group.transform('min')
        frame[metric+'_sensitivity_upper']=group.transform('max')
    columns=['scenario','hour','shielding_g_cm2','dose_rate_mGy_h','cumulative_dose_mGy',
             'timing_variant','data_quality','hour_end','bin_duration_h','cumulative_end_dose_mGy',
             'event_absorbed_dose_mGy','scenario_role','location','estimate_type','proxy_threshold_MeV',
             'gap_method','normalized_bin_weight','template_timestamp_utc','observed_proton_flux','is_gap_filled',
             'dose_quantity','target_type','geometry','target_geometry','unit','dose_rate_unit','nuclear_attenuation',
             'irradiation_geometry','source_model','source_path','source_sha256',
             'source_report_path','source_report_sha256','input_spectrum_sha256',
             'transport_report_path','transport_report_sha256','input_link_evidence_path','input_link_evidence_sha256',
             'baseline_version']
    columns += [c for c in frame if c.endswith(('_sensitivity_lower','_sensitivity_upper'))]
    return frame[columns].sort_values(['scenario','shielding_g_cm2','timing_variant','hour']).reset_index(drop=True)


def write_baseline(frame):
    """Never silently replace a frozen baseline with a different calculation."""
    content=frame.to_csv(index=False)
    if BASELINE_MANIFEST.exists():
        manifest=json.loads(BASELINE_MANIFEST.read_text())
        require(hashlib.sha256(content.encode('utf-8')).hexdigest()==manifest['csv_sha256'],
                'Frozen baseline would change. Create an explicitly reviewed new baseline version; do not overwrite v1.0.')
    write_preserving(BASELINE_PATH,content)


def load_baseline(path=BASELINE_PATH):
    """Read the shared CSV only; no source parsing or transport/model reconstruction."""
    path=Path(path)
    if path.resolve()==BASELINE_PATH.resolve() and BASELINE_MANIFEST.exists():
        require(sha256(path)==json.loads(BASELINE_MANIFEST.read_text())['csv_sha256'],
                'Frozen baseline checksum mismatch; restore the reviewed artifact before using it.')
    frame=pd.read_csv(path)
    needed={'scenario','hour','hour_end','bin_duration_h','shielding_g_cm2','dose_rate_mGy_h',
            'cumulative_dose_mGy','cumulative_end_dose_mGy','timing_variant','data_quality','estimate_type'}
    require(needed.issubset(frame.columns),'Baseline CSV has an unsupported schema.')
    require(not frame.duplicated(['scenario','shielding_g_cm2','timing_variant','hour']).any(),'Duplicate baseline bins.')
    return frame


def baseline_interval_dose(scenario, shielding_g_cm2, start_hour, end_hour,
                           timing_variant=None, *, baseline=None):
    """Return tissue-target mGy over [start, end), measured from STORM start.

Load once with load_baseline() and pass baseline=frame for repeated strategy calls.
None selects the central timing member. No extrapolation or shielding interpolation.
"""
    frame=load_baseline() if baseline is None else baseline
    selected=frame[frame.scenario.eq(scenario)&frame.shielding_g_cm2.eq(shielding_g_cm2)]
    selected=selected[selected.estimate_type.eq('central')] if timing_variant is None else selected[selected.timing_variant.eq(timing_variant)]
    require(not selected.empty and selected.timing_variant.nunique()==1,'Select an available scenario, exact shielding and one timing variant.')
    # Reuse exact bin-overlap integration; use storm-relative coordinates locally.
    bins=selected[['hour','hour_end','dose_rate_mGy_h']].rename(columns={
        'hour':'hour_since_emergency','hour_end':'hour_end_since_emergency','dose_rate_mGy_h':'absorbed_dose_rate_mGy_h'})
    return accumulated_dose(bins,start_hour,end_hour)


def export_environment(config_path=CONFIG, require_dose=False):
    result = build_environment(config_path)
    directory=ROOT/'outputs/model'
    for name,key in [('synthetic_sapphire_temporal_weights.csv','profiles'),('synthetic_sapphire_hourly_fluence.csv','fluence')]:
        write_preserving(directory/name,result[key].to_csv(index=False))
    write_preserving(directory/'sapphire_transport_audit.json',json.dumps(result['audit'],indent=2)+'\n')
    report='SAPPHIRE TRANSPORT AUDIT\n100-year: main. 1,000-year: worst-case.\n\n'
    report+='\n'.join(result['audit']['missing_matches'])
    for entry in result['audit']['transport_reports']:
        report+=f"\n{entry['scenario_id']}: {entry['rows']} verified tissue absorbed-dose points, 4π Al spheres, no proton nuclear attenuation.\n"
    report+='\nLegacy SHIELDOSE tables remain quarantined; legacy MULASSIS NaN effective doses remain excluded.\n'
    report+='New source-report event frequencies and spectra, exact g/cm² coordinates, and rounded HTML dose values were checked against numerical exports. Run pairing and event-integrated interpretation are user-confirmed.\n'
    report+='\n'+result['config']['radial_scaling_note']+'\n'
    write_preserving(directory/'sapphire_transport_audit.txt',report)
    if not result['mission'].empty:
        write_baseline(baseline_dataset(result['full_dose']))
        write_preserving(directory/'synthetic_sapphire_full_event_dose.csv',result['full_dose'].to_csv(index=False))
        write_preserving(directory/'synthetic_sapphire_interval_exposure.csv',result['exposures'].to_csv(index=False))
    else:
        if BASELINE_MANIFEST.exists():
            raise MissingTransportError('Rebuild failed; the frozen baseline is preserved. See the source audit.')
        # Prevent a stale successful result from masquerading as this blocked run.
        for path in [ROOT/'data/processed/mission_radiation_environment.csv',directory/'synthetic_sapphire_full_event_dose.csv',directory/'synthetic_sapphire_interval_exposure.csv',
                     *[ROOT/'outputs/charts'/f'{stem}.{suffix}' for stem in ('04_radiation_dose_rate','05_cumulative_exposure') for suffix in ('png','txt')]]:
            if path.exists():
                backup=ROOT/'data/raw/archive/model_output_versions'/(path.name+'.'+sha256(path)[:16])
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists(): shutil.copy2(path,backup)
                path.unlink()
    print('Synthetic SAPPHIRE spectra and full-record timing verified. Dose status: '+result['audit']['status'])
    if result['audit']['missing_matches']:
        print('\n'.join(result['audit']['missing_matches']))
    if require_dose and result['mission'].empty:
        raise MissingTransportError('No synthetic absorbed-dose chart can be generated: matching SAPPHIRE transport results are unverified. See outputs/model/sapphire_transport_audit.txt.')
    return result


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical-reference',action='store_true')
    args=parser.parse_args()
    export_historical_environment() if args.historical_reference else export_environment()
