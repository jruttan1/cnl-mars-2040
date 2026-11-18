"""Audit supplied OLTARIS Band exports without changing radiation or mission inputs."""
from pathlib import Path
import argparse
import hashlib
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'outputs/model/band_validation'
PARAMETERS = {
    100: dict(J0=6.24437e11, R0_MV=65.90468, gamma1=.263780, gamma2=4.674330),
    1000: dict(J0=7.18915e11, R0_MV=65.09875, gamma1=.180525, gamma2=4.675966),
}
# Physical proton rest energy. Also test 938 MeV as an export-compatibility hypothesis.
PROTON_REST_MEV = 938.2720813


def sha256(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def band(energy, parameters, *, rigidity_reference_MV=1000., mass_MeV=PROTON_REST_MEV):
    """Integral protons/cm² and differential protons/(cm² MeV).

    The reference is 1000 MV (GV powers) for export-compatible normalization;
    1 MV reproduces the apparent original fitting convention. R0 is always MV.
    """
    e=np.asarray(energy,dtype=float)
    if np.any(e<=0):
        raise ValueError('Positive kinetic energy in MeV required.')
    j,r0,g1,g2=(parameters[k] for k in ('J0','R0_MV','gamma1','gamma2'))
    if not (j>0 and r0>0 and 0<g1<g2 and rigidity_reference_MV>0):
        raise ValueError('Require J0,R0>0 and 0<gamma1<gamma2.')
    r=np.sqrt(e*(e+2*mass_MeV))  # MV for a proton, charge +1
    rb=(g2-g1)*r0
    loglow=np.log(j)-g1*np.log(r/rigidity_reference_MV)-r/r0
    loghigh=(np.log(j)-g2*np.log(r/rigidity_reference_MV)
             +(g2-g1)*np.log(rb/rigidity_reference_MV)+g1-g2)
    integral=np.exp(np.where(r<=rb,loglow,loghigh))
    differential=integral*np.where(r<=rb,g1/r+1/r0,g2/r)*(e+mass_MeV)/r
    return integral,differential


def corrected_parameters(parameters):
    """Exact MV-to-GV normalization conversion, not an empirical dose rescale."""
    return {**parameters,'J0':parameters['J0']/1000**parameters['gamma1']}


def read_transport(path):
    """Strictly parse the four declared axes and Fortran-ordered differential table."""
    text=path.read_text()
    if 'Fluence (particles/(EU*-cm2))' not in text.splitlines()[0]:
        raise ValueError('Unexpected quantity/units.')
    sections=re.split(r'^C[^\n]*array dimensions and data\s*\n',text,flags=re.M)[1:]
    if len(sections)!=5:
        raise ValueError('Expected energy, particle, aluminium, tissue, then data.')
    axes=[]
    for i,section in enumerate(sections):
        lines=[s for s in section.splitlines() if s.strip() and not s.startswith('C')]
        dims=np.array(lines[0].split(),int).reshape(-1,2)
        shape=tuple(dims[:,1]-dims[:,0]+1)
        body=' '.join(lines[1:])
        values=np.array(body.split(),str) if i==1 else np.fromstring(body,sep=' ')
        if values.size!=np.prod(shape):
            raise ValueError(f'{path}: dimension mismatch in block {i}')
        if i==4:
            grid=values.reshape(shape,order='F')
        else:
            axes.append(values)
    if tuple(map(len,axes))!=grid.shape or not np.isfinite(grid).all() or (grid<0).any():
        raise ValueError('Invalid transport array.')
    metadata={key:re.search(pattern,text).group(1).strip() for key,pattern in {
        'job_name':r'Job Name:\s*([^\n]+)',
        'created':r'Created on\s*([^\n]+)',
        'version':r'TARIS FORTRAN code version\s*([^\n]+)'}.items()}
    return axes,grid,metadata


def sapphire_spectrum(n):
    """Verify processed integral AND differential data against the original report."""
    path=ROOT/f'data/raw/spenvis/sapphire_{n}yr/sapphire_{n}yr_source_report.html'
    soup=BeautifulSoup(path.read_text(),'html.parser')
    if not re.search(rf'Event frequency:\s*1 in\s*{n} years',soup.get_text()):
        raise ValueError('Wrong SAPPHIRE return period.')
    table=[t for t in soup.find_all('table') if 'Fluence at spacecraft' in t.get_text()]
    if len(table)!=1:
        raise ValueError('Ambiguous source spectrum table.')
    rows=[]
    for tr in table[0].find_all('tr'):
        cells=tr.find_all('td',recursive=False)
        if len(cells)==5:
            rows.append([float(c.get_text()) for c in cells])
    original=np.array(rows)
    clean=pd.read_csv(ROOT/'data/processed/spe_scenarios.csv')
    clean=clean[clean.scenario_id.eq(f'SAPPHIRE-1-in-{n}')].sort_values('energy_MeV')
    np.testing.assert_array_equal(original[:,:3],clean[['energy_MeV',
        'spacecraft_integral_protons_cm2','spacecraft_differential_protons_cm2_MeV']].to_numpy())
    return original[:,:3],path


def locate_export(n,downloads):
    name=f'sapphire1in{n}.dat'
    matches=list(ROOT.rglob(name))
    if (downloads/name).exists():
        matches.append(downloads/name)
    if not matches:
        raise FileNotFoundError(f'{name}: provide --downloads directory.')
    if len({sha256(p) for p in matches})!=1:
        raise ValueError(f'Different versions of {name}: resolve ambiguity first.')
    return matches[0]


def plot_diagnostics(spectra,exports):
    colors={100:'#155e9b',1000:'#b34332'}
    fig,ax=plt.subplots(2,2,figsize=(12,8),sharex='col',layout='constrained')
    for col,n in enumerate((100,1000)):
        s=spectra[spectra.return_period_years.eq(n)]
        a=ax[0,col]
        a.loglog(s.energy_MeV,s.sapphire_integral_protons_cm2,'k-',label='Original SAPPHIRE')
        a.loglog(s.energy_MeV,s.export_convention_integral_protons_cm2,'--',color='#b34332',label='Supplied J₀, export GV convention')
        a.loglog(s.energy_MeV,s.corrected_integral_protons_cm2,':',lw=2.5,color='#155e9b',label='Unit-corrected J₀ (proposed)')
        a.set_title(f'SAPPHIRE 1-in-{n:,}-year event')
        a.set_ylabel('Integral fluence above E (protons/cm²)')
        a.legend(fontsize=8)
        a=ax[1,col]
        a.semilogx(s.energy_MeV,s.corrected_integral_error_percent,color='#155e9b',label='Integral fluence error')
        a.semilogx(s.energy_MeV,s.corrected_differential_error_percent,'--',color='#b34332',label='Differential fluence error')
        a.axhline(0,color='black',lw=.8)
        a.set_ylabel('Corrected fit − SAPPHIRE (%)')
        a.set_xlabel('Proton kinetic energy E (MeV)')
        a.legend(fontsize=8)
    fig.suptitle('Band normalization audit — unchanged spectrum shape, corrected units',fontsize=15)
    for a in ax.flat:a.grid(alpha=.2,which='major')
    fig.savefig(OUT/'band_vs_sapphire.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for n in (100,1000):
        x=exports[exports.return_period_years.eq(n)]
        ax[0,0].loglog(x.energy_MeV,x.boundary_proton_per_cm2_MeV,color=colors[n],label=f'{n:,}-year export')
        ax[0,0].loglog(x.energy_MeV,x.expected_GV_per_cm2_MeV,'--',color=colors[n],alpha=.7)
        ax[1,0].semilogx(x.energy_MeV,x.boundary_GV_error_percent,color=colors[n],label=f'{n:,}-year')
    ax[0,0].set_title('Boundary: zero aluminium and zero tissue depth')
    ax[0,0].set_ylabel('Differential proton fluence\n(protons/(cm² MeV))')
    ax[0,0].legend(fontsize=8)
    ax[0,0].text(.04,.06,'Solid: export; dashed: analytic GV-normalized Band',transform=ax[0,0].transAxes,fontsize=8)
    ax[1,0].set_ylabel('Export / analytic GV Band − 1 (%)')
    ax[1,0].set_title('Small residual: physical proton rest energy = 938.2720813 MeV',fontsize=10)
    a=exports[exports.return_period_years.eq(100)].reset_index(drop=True)
    b=exports[exports.return_period_years.eq(1000)].reset_index(drop=True)
    sa=spectra[spectra.return_period_years.eq(100)].reset_index(drop=True)
    sb=spectra[spectra.return_period_years.eq(1000)].reset_index(drop=True)
    ax[0,1].semilogx(sa.energy_MeV,sb.sapphire_differential_per_cm2_MeV/sa.sapphire_differential_per_cm2_MeV,'k-',label='Original SAPPHIRE differential')
    ax[0,1].semilogx(a.energy_MeV,b.boundary_proton_per_cm2_MeV/a.boundary_proton_per_cm2_MeV,color='#b34332',label='Exported boundary differential')
    ax[0,1].semilogx(a.energy_MeV,b.al0p4_tissue0_proton_per_cm2_MeV/a.al0p4_tissue0_proton_per_cm2_MeV,color='#155e9b',label='Exported at Al 0.4; tissue 0')
    ax[0,1].axhline(1,color='grey',ls=':');ax[0,1].set_ylabel('1,000-year / 100-year fluence')
    ax[0,1].set_title('Severity ordering is reversed in the exports')
    ax[0,1].legend(fontsize=8)
    ax[1,1].semilogx(sa.energy_MeV,sb.sapphire_integral_protons_cm2/sa.sapphire_integral_protons_cm2,'k-',label='Original SAPPHIRE integral')
    ax[1,1].semilogx(sa.energy_MeV,sb.corrected_integral_protons_cm2/sa.corrected_integral_protons_cm2,color='#155e9b',ls='--',label='Proposed corrected Band integral')
    ax[1,1].set_ylabel('1,000-year / 100-year fluence');ax[1,1].set_title('Unit correction restores intended severity ordering')
    ax[1,1].legend(fontsize=8)
    for a in ax.flat:
        a.set_xlabel('Proton kinetic energy E (MeV)');a.grid(alpha=.2,which='major')
    fig.suptitle('OLTARIS differential-fluence checks — boundary versus depth',fontsize=15)
    fig.savefig(OUT/'export_diagnostics.png',dpi=170);plt.close(fig)


def write_report(spectra, exports, summaries, parameters):
    a=exports[exports.return_period_years.eq(100)].reset_index(drop=True)
    b=exports[exports.return_period_years.eq(1000)].reset_index(drop=True)
    ratio=b.al0p4_tissue0_proton_per_cm2_MeV/a.al0p4_tissue0_proton_per_cm2_MeV
    rows='| Event | Supplied J0 | Corrected J0 | R0 (MV) | R0 (GV) | gamma1 | gamma2 |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for p in parameters:
        rows+=f"| {p['return_period_years']}-year | {p['J0_supplied']:.8g} | {p['J0_corrected']:.10g} | {p['R0_MV']} | {p['R0_GV']:.8f} | {p['gamma1']} | {p['gamma2']} |\n"
    report=f"""# OLTARIS Band / SAPPHIRE discrepancy audit

## Finding

**The exports use GV-normalized rigidity powers, whereas the supplied J0 values reproduce SAPPHIRE under MV-normalized powers.** This inflates the 100-year spectrum by {summaries[0]['normalization_inflation']:.6f} and the 1,000-year spectrum by {summaries[1]['normalization_inflation']:.6f}. It reverses their severity ordering. The exported 1,000-year proton fluence at aluminium 0.4 g/cm² / tissue 0 is {ratio.min():.6f}–{ratio.max():.6f} times the 100-year result, below it at all 100 energy nodes.

This establishes a normalization mismatch, not evidence that SAPPHIRE's extreme scenario is weaker. Whether the mismatch originated in a fitting script, copied values, or an interface misunderstanding cannot be determined from exports alone.

## File interpretation and provenance

The two named files were read in place from Downloads (or the project if already present). `audit.json` records full paths, SHA-256 hashes, actual job names, creation timestamps, code version and axes. They are not copied into Git.

Both are **event-integrated DIFFERENTIAL fluence lookup databases**, not integral spectra, hourly fluxes or anatomical-dose tables. Header units are particles/(EU* cm²): EU* is MeV for photons/electrons/positrons, MeV/amu otherwise. For protons this gives the energy-per-nucleon convention used here as proton kinetic energy in MeV. Axes: 100 energies (0.01–2500 MeV), 66 particle identities, 21 aluminium depths and 21 tissue depths. Array ordering is Fortran, with energy varying fastest. All 2,910,600 values per file are finite and nonnegative.

The **proton** channel is selected by its label, not an assumed particle index. Al=0/tissue=0 is the unshielded boundary. Al=0.4/tissue=0 is a transported depth-grid sample; it is not an organ spectrum or necessarily the final spherical-geometry point response. Depth grids contain many shielding levels and do not independently confirm the selected sphere or MAX phantom. Those run settings remain user-supplied.

The 81 energy points in each processed SAPPHIRE spectrum exactly match its original SPENVIS HTML report, in both integral and differential columns. Reported distance is 1.2 AU and no distance scaling is applied by this audit. Comparison against SAPPHIRE is restricted to its supplied 0.1–1000 MeV range; export checks use all 100 native points without extrapolating SAPPHIRE.

## Equation and independent verification

For proton kinetic energy E in MeV and proton rest energy m = 938.2720813 MeV:

```text
R_MV = sqrt(E * (E + 2*m))
r = R_MV / 1000                  # numerical rigidity in GV
r0 = R0_MV / 1000
rb = (gamma2 - gamma1) * r0

F(>E) = J0 * r^(-gamma1) * exp(-r/r0)                    if r <= rb
F(>E) = J0 * rb^(gamma2-gamma1) * exp(gamma1-gamma2)
             * r^(-gamma2)                              if r > rb

f(E) = -dF/dE
     = F * (gamma1/R_MV + 1/R0_MV) * (E+m)/R_MV         low branch
     = F * (gamma2/R_MV) * (E+m)/R_MV                    high branch
```

F is integral fluence in protons/cm²; f is differential fluence in protons/(cm² MeV). The energy-to-rigidity derivative is essential. J0 is the normalization coefficient for this specific rigidity convention, not a unit-independent total proton count. The integral diverges toward zero energy for positive gamma1, so it must not be interpreted as an all-energies total.

The published OLTARIS-use equation is in Adamczyk et al., equation (1), page 2: https://www.irpa.net/members/TS10a.2.pdf . NASA's guide describes the user-defined Band option and separate sphere/body transport: https://oltaris.larc.nasa.gov/static_pages/OLTARIS_USER_GUIDE/sendfile . The authenticated live input form was not accessible in this audit; the convention is independently established by the actual exports, not a claim to have viewed that form.

With supplied J0 and GV powers, the analytic differential matches every boundary proton value within **0.067%**. Using m=938 MeV as a separate compatibility check reduces maximum residuals to {summaries[0]['export_max_M938_error_percent']:.6f}% and {summaries[1]['export_max_M938_error_percent']:.6f}%. This strongly suggests a rounded rest-energy constant/parameter precision in the implementation; it is not a verified source-code detail. The main comparison retains the physical rest energy. No fitted multiplier is used in either check.

## Supported input correction

To preserve the fitted spectrum when converting numerical rigidity powers from MV to GV:

```text
J0_GV = J0_MV / 1000^gamma1
```

The same identity holds on both branches. Keep gamma1, gamma2 and the physical R0 unchanged. This is an algebraic unit-convention conversion, not a new fit or a dose-calibration factor.

{rows}
Enter R0 in **the units shown by your actual form**: use the MV column for an MV field, or the GV column for a GV field. Do not enter 65.9 in a GV field. The exports already support the stated physical R0 of about 65 MV, so the demonstrated issue is J0 normalization, not an apparent 1000-fold R0 error.

After this proposed correction, maximum absolute integral errors over 0.1–1000 MeV are **{summaries[0]['corrected_max_integral_error_percent']:.3f}%** and **{summaries[1]['corrected_max_integral_error_percent']:.3f}%**. Maximum differential errors are **{summaries[0]['corrected_max_differential_error_percent']:.3f}%** and **{summaries[1]['corrected_max_differential_error_percent']:.3f}%**, both at 0.1 MeV. Close integral agreement does not imply identical differential spectra or an established organ-dose accuracy. The corrected curves again put 1,000-year above 100-year at every original energy node.

## BFO and point-dose interpretation

**Confirmed:** the new runs were driven by different, incorrectly normalized incident spectra relative to the intended SAPPHIRE scenarios. The 1,000-year boundary proton fluence is lower at every exported node, and the ordering remains reversed at Al=0.4/tissue=0. For otherwise identical transport/body settings, this provides a direct physical explanation for lower BFO dose. Numerical BFO differences cannot be independently reproduced from these two fluence files.

**Not independently verified:** the actual BFO absorbed doses, their units, and the new runs' point-dose values were not supplied in identifiable job-linked dose reports. Downloads contains `effective_dose_equivalent-4.txt`, but it has no job identifier and contains mSv organ equivalents (BFO 3300.2249 mSv); it is not assigned to either scenario here. No mSv value is relabeled as mGy or mGy-Eq. Older King or deleted Weibull-run dose files are not used.

The existing verified SHIELDOSE-2 results at 0.4 g/cm² are **74,571 mGy** (100-year) and **127,280 mGy** (1,000-year), tissue at the centre of aluminium spheres, proton nuclear attenuation not included. The Band normalization error alone increases fluence and, for a fixed linear transport/dose response, dose by the factors above relative to the same Band shape with corrected normalization. This establishes a major expected contribution to a point-dose mismatch; it does not prove an exact factor relative to SHIELDOSE-2.

Remaining possible contributors require matched job reports: geometry/path-length treatment, definition of the point/tissue target, proton nuclear interactions/secondary particles, energy limits and residual spectrum differences. OLTARIS and SHIELDOSE-2 are different transport models. A depth-grid value or an anatomical BFO dose must not be compared as if it were the same quantity as a centre-of-sphere tissue-target dose. Without identified point-dose exports, the exact remaining discrepancy cannot be quantified or uniquely attributed.

## Next action

1. Check the form's displayed equation and R0 unit against the equation above; use the corrected J0 values with unchanged physical R0 and slopes.
2. Before trusting doses from a future run, export the boundary spectrum and check it against the proposed curves. Preserve the full environment/geometry/MAX configuration and both runs' labeled BFO/point-dose reports.
3. Compare absorbed mGy with absorbed mGy using matching target/geometry, then assess any residual transport differences. Do not automatically replace the frozen baseline or infer medical limits from this audit.

No simulation was submitted or rerun. No mission logic, baseline, original report, or downloaded export was modified. Reproduce with `python audit_band_spectra.py` (or `--downloads PATH`). `spectrum_comparison.csv` and `export_comparison.csv` contain all calculated comparisons; `proposed_parameters.csv` contains the exact conversion. The two PNGs show spectra/residuals and exported boundary/depth diagnostics.
"""
    (OUT/'README.md').write_text(report)


def main(downloads):
    OUT.mkdir(parents=True,exist_ok=True)
    protected=[ROOT/'data/processed/mission_radiation_environment.csv',ROOT/'outputs/mission_radiation_environment.csv',ROOT/'radiation_model.py',*ROOT.glob('sim/*.py')]
    before={str(p.relative_to(ROOT)):sha256(p) for p in protected}
    spectrum_rows=[];export_rows=[];summaries=[];provenance=[];parameter_rows=[]
    for n,p in PARAMETERS.items():
        source,path=sapphire_spectrum(n)
        e,integral,differential=source.T
        raw_i,raw_d=band(e,p)
        corrected=corrected_parameters(p)
        ci,cd=band(e,corrected)
        mi,md=band(e,p,rigidity_reference_MV=1)
        np.testing.assert_allclose(ci,mi,rtol=1e-13)
        np.testing.assert_allclose(cd,md,rtol=1e-13)
        spectrum_rows.append(pd.DataFrame(dict(return_period_years=n,energy_MeV=e,
            sapphire_integral_protons_cm2=integral,sapphire_differential_per_cm2_MeV=differential,
            export_convention_integral_protons_cm2=raw_i,export_convention_differential_per_cm2_MeV=raw_d,
            corrected_integral_protons_cm2=ci,corrected_differential_per_cm2_MeV=cd,
            corrected_integral_error_percent=100*(ci/integral-1),
            corrected_differential_error_percent=100*(cd/differential-1))))
        export=locate_export(n,downloads)
        axes,grid,meta=read_transport(export)
        energy,particles,al,tissue=axes
        proton=np.flatnonzero(particles=='proton').item()
        a0=np.flatnonzero(al==0).item();a04=np.flatnonzero(al==.4).item();t0=np.flatnonzero(tissue==0).item()
        boundary=grid[:,proton,a0,t0];transported=grid[:,proton,a04,t0]
        _,expected=band(energy,p);_,mv=band(energy,p,rigidity_reference_MV=1)
        _,compat=band(energy,p,mass_MeV=938.)
        # Explicit numerical verification of convention, without fitting a scale to the export.
        np.testing.assert_allclose(boundary,expected,rtol=.001,atol=0)
        np.testing.assert_allclose(boundary,compat,rtol=.00002,atol=0)
        export_rows.append(pd.DataFrame(dict(return_period_years=n,energy_MeV=energy,
            boundary_proton_per_cm2_MeV=boundary,al0p4_tissue0_proton_per_cm2_MeV=transported,
            expected_GV_per_cm2_MeV=expected,expected_MV_per_cm2_MeV=mv,
            boundary_GV_error_percent=100*(boundary/expected-1),
            boundary_MV_ratio=boundary/mv,boundary_mass938_error_percent=100*(boundary/compat-1))))
        factor=1000**p['gamma1']
        summaries.append(dict(return_period_years=n,normalization_inflation=factor,
            corrected_max_integral_error_percent=float(max(abs(100*(ci/integral-1)))),
            corrected_max_differential_error_percent=float(max(abs(100*(cd/differential-1)))),
            original_integral_ratio_range=[float(min(raw_i/integral)),float(max(raw_i/integral))],
            export_max_GV_error_percent=float(max(abs(100*(boundary/expected-1)))),
            export_max_M938_error_percent=float(max(abs(100*(boundary/compat-1))))))
        provenance.append(dict(export=str(export),sha256=sha256(export),bytes=export.stat().st_size,
            metadata=meta,shape=list(grid.shape),axes={'energy_MeV':energy.tolist(),'particles':particles.tolist(),
            'aluminium_g_cm2':al.tolist(),'tissue_g_cm2':tissue.tolist()},
            sapphire_report=str(path.relative_to(ROOT)),sapphire_report_sha256=sha256(path),
            settings_status='0.4 g/cm² sphere and MAX reported by user; no full job configuration in exports'))
        parameter_rows.append(dict(return_period_years=n,J0_supplied=p['J0'],J0_corrected=corrected['J0'],
            R0_MV=p['R0_MV'],R0_GV=p['R0_MV']/1000,gamma1=p['gamma1'],gamma2=p['gamma2'],
            division_factor=factor,basis='Exact conversion from MV powers to GV powers; not a refit'))
        del grid
    spectra=pd.concat(spectrum_rows,ignore_index=True);exports=pd.concat(export_rows,ignore_index=True)
    spectra.to_csv(OUT/'spectrum_comparison.csv',index=False)
    exports.to_csv(OUT/'export_comparison.csv',index=False)
    pd.DataFrame(parameter_rows).to_csv(OUT/'proposed_parameters.csv',index=False)
    plot_diagnostics(spectra,exports)
    write_report(spectra,exports,summaries,parameter_rows)
    assert before=={str(p.relative_to(ROOT)):sha256(p) for p in protected}
    for entry in provenance:assert sha256(Path(entry['export']))==entry['sha256']
    result=dict(summary=summaries,provenance=provenance,protected_sha256=before,
                settings_source='User-supplied parameters; empirical boundary-spectrum verification',
                interface_limit='Authenticated live form not inspected; published GV equation plus exports establish convention.',
                equation_sources=['https://www.irpa.net/members/TS10a.2.pdf',
                                  'https://oltaris.larc.nasa.gov/static_pages/OLTARIS_USER_GUIDE/sendfile'])
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads',type=Path,default=Path.home()/'Downloads')
    main(parser.parse_args().downloads)
