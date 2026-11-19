"""Read local reports before associating a SAPPHIRE spectrum with transport dose."""
from pathlib import Path
import hashlib
import re
import unicodedata
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_text(path):
    path = Path(path)
    if path.suffix == '.pdf':
        return unicodedata.normalize('NFKC', '\n'.join(page.extract_text() or '' for page in PdfReader(path).pages))
    if path.suffix == '.html':
        return BeautifulSoup(path.read_text(), 'html.parser').get_text(' ', strip=True)
    return path.read_text()


def load_verified_spectra():
    """Verify return-period labels and every spectral value against the PDF tables."""
    spectra = pd.read_csv(ROOT/'data/processed/spe_scenarios.csv')
    records = []
    for period in (100, 1000):
        scenario = f'SAPPHIRE-1-in-{period}'
        rows = spectra[spectra.scenario_id.eq(scenario)].sort_values('energy_MeV').copy()
        if rows.empty or rows.source_path.nunique() != 1:
            raise ValueError(f'Missing/ambiguous SAPPHIRE spectrum: {scenario}')
        path = ROOT/rows.source_path.iloc[0]
        text = report_text(path)
        if not re.search(rf'Event frequency:\s*1 in {period} years', text):
            raise ValueError(f'Return period not verified in {path}')
        parsed = []
        for line in text.splitlines():
            numbers = list(re.finditer(r'\d\.\d{3}E[+-]\d{2}', line))
            if len(numbers) == 4:
                parsed.append([float(line[:numbers[0].start()]), *[float(m.group()) for m in numbers]])
        columns = ['energy_MeV', 'spacecraft_integral_protons_cm2',
                   'spacecraft_differential_protons_cm2_MeV', 'model_1p2AU_integral_protons_cm2',
                   'model_1p2AU_differential_protons_cm2_MeV']
        raw = pd.DataFrame(parsed, columns=columns).sort_values('energy_MeV')
        np.testing.assert_allclose(rows[columns], raw, rtol=0, atol=0)
        if rows.energy_MeV.duplicated().any() or not (rows[columns].to_numpy() > 0).all():
            raise ValueError(f'Invalid spectrum for {scenario}')
        distance = float(re.search(r'Model fluence at ([\d.]+) AU', text).group(1))
        # Keep the report's displayed precision; do not replace it with user-reported 1.25 AU.
        np.testing.assert_allclose(rows.model_distance_AU, distance, rtol=0, atol=0)
        np.testing.assert_array_equal(rows.spacecraft_integral_protons_cm2, rows.model_1p2AU_integral_protons_cm2)
        np.testing.assert_array_equal(rows.spacecraft_differential_protons_cm2_MeV, rows.model_1p2AU_differential_protons_cm2_MeV)
        rows['spectrum_sha256'] = digest(path)
        records.append(rows)
    return pd.concat(records, ignore_index=True)


def audit_legacy_transport(spectra):
    """Describe evidence in existing reports; a folder name never verifies linkage."""
    reports, printed_doses = [], []
    dose = pd.read_csv(ROOT/'data/processed/shielding_dose.csv')
    for period in (100, 1000):
        scenario = f'SAPPHIRE-1-in-{period}'
        folder = ROOT/'data/raw/spenvis'/scenario
        shield_path = folder/('shieldose2-tissue-dose-report.html' if period == 100 else 'shieldose2-tissue-dose-report.pdf')
        text = report_text(shield_path)
        # Exactly 25 pairs: total dose and solar-proton contribution, in printed rad.
        values = np.array([float(x) for x in re.findall(r'\d\.\d{3}E[+-]\d{2}', text)])
        if len(values) != 50:
            raise ValueError(f'Unexpected SHIELDOSE report structure: {shield_path}')
        np.testing.assert_array_equal(values[::2], values[1::2])
        printed_doses.append(values[::2])
        cleaned = dose[(dose.scenario_id == scenario) & (dose.tool == 'SHIELDOSE-2') & dose.validation_status.eq('quarantined_scenario_association')].sort_values('aluminum_thickness_mm')
        if len(cleaned) != 25 or not cleaned.dose_unit.eq('rad').all():
            raise ValueError('Unexpected processed SHIELDOSE rows or units')
        np.testing.assert_allclose(cleaned.dose_value, values[::2], rtol=5e-4)
        if period == 100:
            raw_text = (folder/'shieldose2-tissue-dose-output.txt').read_text()
            pairs = re.findall(r'^\s*(\d\.\d{4}E[+-]\d{2}),\s*(\d\.\d{4}E[+-]\d{2})\s*$',raw_text,re.M)
            np.testing.assert_allclose(cleaned[['aluminum_thickness_mm','dose_value']],np.array(pairs,dtype=float),rtol=0,atol=0)
        reports.append(dict(scenario_folder=scenario, tool='SHIELDOSE-2',
            source_path=str(shield_path.relative_to(ROOT)), source_sha256=digest(shield_path),
            dose_quantity='absorbed_dose', unit='rad', rows=25,
            geometry='centre of aluminium spheres', target='tissue',
            nuclear_attenuation=False, maximum_thickness_mm=20, maximum_areal_density_g_cm2=5.4,
            input_return_period_verified=False, status='blocked_unverified_input_spectrum',
            reason='No return period or linked input spectrum in transport report; folder assignment is provisional.'))
        path = folder/'mulassis-effective-dose-output.txt'
        txt = path.read_text()
        if "'Dose','Sv'" not in txt or 'NaN' not in txt:
            raise ValueError('MULASSIS contents changed; review the new output.')
        reports.append(dict(scenario_folder=scenario, tool='MULASSIS', source_path=str(path.relative_to(ROOT)),
            source_sha256=digest(path), dose_quantity='effective_dose', unit='Sv',
            input_return_period_verified=False, status='blocked_nan_and_wrong_quantity',
            reason='Dose and error are NaN; effective dose in Sv is not absorbed dose. No return-period linkage.'))
    equal = bool(np.array_equal(*printed_doses))
    return dict(scenarios=[dict(scenario_id=s, return_period_years=int(g.return_period_years.iloc[0]),
                          spectrum_sha256=g.spectrum_sha256.iloc[0], spectrum_verified=True,
                          report_display_distance_AU=float(g.model_distance_AU.iloc[0]))
                          for s,g in spectra.groupby('scenario_id',sort=False)],
                transport_reports=reports, shieldose_displayed_doses_identical=equal,
                explanation='Identical dose tables do not establish identical scenario doses. The cause is unknown.',
                missing_inputs=['Spectrum-linked absorbed-dose transport output for the 100-year event (main).',
                                'Spectrum-linked absorbed-dose transport output for the 1,000-year event (worst-case).',
                                'Matching aluminium depths for each intended reference; existing tables do not reach 20 g/cm².',
                                'Run settings/input spectrum evidence establishing geometry, target and event normalization.'])


def html_numeric_rows(path, width):
    """Read numeric HTML table rows, preserving displayed precision."""
    rows=[]
    for tr in BeautifulSoup(Path(path).read_text(),'html.parser').find_all('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
        if len(cells)!=width: continue
        try: rows.append([float(c) for c in cells])
        except ValueError: continue
    return np.asarray(rows,dtype=float)


def verified_shieldose_rows(spectra=None):
    """Parse the November 16 exports; never hardcode doses into the model."""
    import json
    spectra=load_verified_spectra() if spectra is None else spectra
    manifest_path=ROOT/'data/raw/spenvis/verified_sapphire_manifest.json'
    if not manifest_path.exists():return pd.DataFrame()
    manifest=json.loads(manifest_path.read_text())
    for item in manifest['files']:
        path=ROOT/item['path']
        if not path.is_file() or digest(path)!=item['sha256']:
            raise ValueError(f'Imported raw file changed or missing: {path}')
    rows=[]
    for period in (100,1000):
        folder=ROOT/f'data/raw/spenvis/sapphire_{period}yr'
        prefix=f'sapphire_{period}yr_'
        source=folder/(prefix+'source_report.html')
        report=folder/(prefix+'shieldose_report.html')
        numerical=folder/(prefix+'shieldose_data.txt')
        source_text=report_text(source)
        if not re.search(rf'Event frequency:\s*1 in\s+{period}\s+years',source_text):
            raise ValueError(f'Wrong return period in {source}')
        scenario=f'SAPPHIRE-1-in-{period}'
        spectrum=spectra[spectra.scenario_id.eq(scenario)].sort_values('energy_MeV')
        cols=['energy_MeV','spacecraft_integral_protons_cm2','spacecraft_differential_protons_cm2_MeV',
              'model_1p2AU_integral_protons_cm2','model_1p2AU_differential_protons_cm2_MeV']
        np.testing.assert_allclose(html_numeric_rows(source,5),spectrum[cols],rtol=0,atol=0)
        text=numerical.read_text(); settings=report_text(report)
        for token in ["'Thick','g/cm2'","'Dose','rad'",'4pi Dose at Centre of Al Spheres','Solar Protons']:
            if token not in text: raise ValueError(f'Missing setting {token} in {numerical}')
        for token in ['Target material: Tissue','Centre of Al spheres','without nuclear attenuation','SHIELDOSE-2 Version 2.10']:
            if token not in settings:raise ValueError(f'Missing setting {token} in {report}')
        stamp=re.search(r'\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}:\d{2}',text).group()
        if ' '.join(stamp.split()) not in ' '.join(settings.split()):raise ValueError('Numerical/report run timestamps differ.')
        pairs=re.findall(r'^\s*(\d\.\d{4}E[+-]\d{2}),\s*(\d\.\d{4}E[+-]\d{2})\s*$',text,re.M)
        numbers=np.asarray(pairs,dtype=float)
        np.testing.assert_array_equal(numbers[:,0],[0.4,1,2,5,10,20])
        displayed=html_numeric_rows(report,5)
        np.testing.assert_array_equal(displayed[:,2],numbers[:,0])
        np.testing.assert_array_equal(displayed[:,3],displayed[:,4])
        # Reports print four significant figures; text exports retain five.
        np.testing.assert_array_equal(displayed[:,3],[float(f'{v:.3E}') for v in numbers[:,1]])
        for index,(depth,rad) in enumerate(numbers):
            rows.append(dict(source='SPENVIS',tool='SHIELDOSE-2',source_model='SAPPHIRE',dose_transport_model='SHIELDOSE-2 2.10',
                scenario_id=scenario,return_period_years=period,dose_quantity='absorbed_dose',dose_unit='mGy',dose_value=rad*10,
                target_type='idealized_tissue',target_geometry='centre_of_aluminium_spheres',unit='mGy',nuclear_attenuation=False,
                event_absorbed_dose_mGy=rad*10,original_dose_rad=rad,geometry='center_of_aluminum_sphere',target='tissue',
                irradiation_geometry='4pi',proton_nuclear_attenuation_included=False,aluminum_areal_density_g_cm2=depth,
                aluminum_thickness_mm=displayed[index,0],temporal_basis='event_integrated',
                configuration_status='verified_sapphire_input',validation_status='validated_spectrum_link',
                configuration_notes='Tissue at centre of aluminium spheres, 4π; no proton nuclear attenuation; not astronaut whole-body dose.',
                source_path=str(numerical.relative_to(ROOT)),source_sha256=digest(numerical),
                source_report_path=str(source.relative_to(ROOT)),source_report_sha256=digest(source),
                transport_report_path=str(report.relative_to(ROOT)),transport_report_sha256=digest(report),
                input_spectrum_sha256=spectrum.spectrum_sha256.iloc[0],
                input_link_evidence_path=str(manifest_path.relative_to(ROOT)),input_link_evidence_sha256=digest(manifest_path),
                association_basis=manifest['association_basis']))
    return pd.DataFrame(rows)


def audit_transport(spectra):
    audit=audit_legacy_transport(spectra)
    verified=verified_shieldose_rows(spectra)
    audit['legacy_transport_reports']=audit.pop('transport_reports')
    audit['legacy_shieldose_displayed_doses_identical']=audit.pop('shieldose_displayed_doses_identical')
    audit['transport_reports']=[]
    for scenario,g in verified.groupby('scenario_id',sort=False):
        audit['transport_reports'].append(dict(scenario_id=scenario,tool='SHIELDOSE-2',rows=len(g),
            input_return_period_verified=True,status='validated_spectrum_link',
            shielding_g_cm2=g.aluminum_areal_density_g_cm2.tolist(),
            event_absorbed_dose_mGy=g.dose_value.tolist(),source_path=g.source_path.iloc[0],
            source_report_path=g.source_report_path.iloc[0],association_basis=g.association_basis.iloc[0]))
    audit['explanation']='New exports verified against source spectra and matching numerical/report tables; run grouping and event-integrated interpretation confirmed by the user. Legacy ambiguous tables remain excluded.'
    audit['missing_inputs']=[] if len(verified)==12 else ['New verified SHIELDOSE exports are missing.']
    return audit
