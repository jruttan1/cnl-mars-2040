"""One event, quantity, geometry and target per plot. Use --list to see choices."""
import argparse
import matplotlib.pyplot as plt
from common import load, save

# Settings: the OLTARIS default is a transport-grid slice, not whole-body dose.
SCENARIO = 'OLTARIS_Aug1972_King_Al0p4_gcm2'
QUANTITY = 'absorbed_dose'
GEOMETRY = 'aluminum_tissue_depth_grid'
TARGET = 'tissue'
TISSUE_DEPTH_G_CM2 = 0.0
ALLOW_PROVISIONAL = False  # SHIELDOSE event association needs source verification.
SHOW = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--scenario', default=SCENARIO)
    parser.add_argument('--quantity', default=QUANTITY)
    parser.add_argument('--geometry', default=GEOMETRY)
    parser.add_argument('--target', default=TARGET)
    parser.add_argument('--tissue-depth', type=float, default=TISSUE_DEPTH_G_CM2)
    parser.add_argument('--allow-provisional', action='store_true', default=ALLOW_PROVISIONAL)
    args = parser.parse_args()
    data = load('shielding_dose.csv')
    if args.list:
        print(data[['scenario_id', 'dose_quantity', 'geometry', 'target', 'dose_unit',
                    'validation_status']].drop_duplicates().to_string(index=False))
        return
    data = data[(data.scenario_id == args.scenario) & (data.dose_quantity == args.quantity)
                & (data.geometry == args.geometry) & (data.target == args.target)]
    if args.geometry == 'aluminum_tissue_depth_grid':
        data = data[data.tissue_depth_g_cm2 == args.tissue_depth]
        x, label = 'aluminum_depth_g_cm2', 'Aluminium grid depth [g/cm²]'
        context = f'Transport grid; tissue depth {args.tissue_depth:g} g/cm²'
    elif args.geometry == 'center_of_aluminum_sphere':
        x, label = 'aluminum_thickness_mm', 'Aluminium sphere thickness [mm]'
        context = 'Idealized tissue at sphere centre; no proton nuclear attenuation'
    elif args.geometry == 'user_reported_aluminum_sphere':
        x, label = 'selected_sphere_g_cm2', 'User-reported aluminium sphere shielding [g/cm²]'
        context = 'Reported sphere result; one point per selected scenario'
    else:
        parser.error('Unknown geometry; run --list')
    if data.empty:
        parser.error('No matching data; run --list and choose an available combination')
    verified = data.validation_status.eq('validated_spectrum_link')
    if verified.any():
        data = data[~verified] if args.allow_provisional else data[verified]
    provisional = data.validation_status.str.startswith('quarantined').any()
    if provisional and not args.allow_provisional:
        parser.error('Unverified SHIELDOSE event association; use --allow-provisional only for inspection')
    if data.dose_unit.nunique() != 1 or data[x].isna().any() or data[x].duplicated().any():
        parser.error('Selection has mixed units, missing coordinates or duplicate depths')
    data = data.sort_values(x)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(data[x], data.dose_value, marker='o', markersize=3)
    if data.dose_value.gt(0).all():
        ax.set_yscale('log')
    title = f'{args.scenario}\n{context}'
    if provisional:
        title += '\nPROVISIONAL — event association unverified'
    quantity_label = 'Tissue-target absorbed dose' if data.tool.eq('SHIELDOSE-2').all() and args.quantity == 'absorbed_dose' else args.quantity.replace('_', ' ')
    ax.set(xlabel=label, ylabel=f'{quantity_label} [{data.dose_unit.iloc[0]}]', title=title)
    save(fig, '02_shielding_vs_dose.png', SHOW)


if __name__ == '__main__':
    main()
