"""Clinical reference graphic, deliberately separate from mission dose predictions."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from environment_common import finish

# Published reference, NOT a fitted risk model or a classification of mission CSV rows.
SOURCE_URL = 'https://www.cdc.gov/radiation-emergencies/hcp/clinical-guidance/ars.html'
SOURCE_DATE = '2024-04-23'
FIGURE_SIZE = (12, 8)
REFERENCES = [
    ('300', 'Mild symptoms possible',
     'Reported at doses as low as 300 mGy.', '#b17d28'),
    ('700–10,000', 'Bone-marrow syndrome',
     'Blood-cell damage can lead to infection and bleeding.', '#bd692e'),
    ('>10,000', 'Severe gastrointestinal syndrome',
     'Some intestinal symptoms can begin around 6,000 mGy.', '#b84936'),
    ('>50,000', 'Cardiovascular / nervous-system syndrome',
     'Some symptoms can begin around 20,000 mGy.', '#893c54'),
]


def main():
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis('off')
    fig.suptitle('Clinical reference — acute radiation effects', fontsize=22, y=0.96, weight='bold')
    fig.text(0.5, 0.91, 'Exposure within minutes to most of the body • CDC beta/gamma/X-ray reference',
             ha='center', fontsize=12, color='#4b5563')
    ax.text(0.035, 0.95, 'ABSORBED DOSE [mGy]', fontsize=11, weight='bold', color='#4b5563')
    ax.text(0.325, 0.95, 'POTENTIAL EFFECT', fontsize=11, weight='bold', color='#4b5563')
    for index, (dose, title, description, color) in enumerate(REFERENCES):
        y = 0.72-index*0.215
        ax.add_patch(FancyBboxPatch((0.02, y), 0.96, 0.18,
                                   boxstyle='round,pad=0.012,rounding_size=0.012',
                                   facecolor='#f5f6f8', edgecolor='none'))
        ax.plot([0.025, 0.025], [y+0.015, y+0.165], color=color, linewidth=5, solid_capstyle='round')
        ax.text(0.055, y+0.09, dose, va='center', fontsize=23, weight='bold', color=color)
        ax.text(0.325, y+0.115, title, va='center', fontsize=14, weight='bold', color='#202a35')
        ax.text(0.325, y+0.055, description, va='center', fontsize=11, color='#4b5563')
    fig.text(0.5, 0.18, '1 Gy = 1,000 mGy • Approximate reference levels; effects overlap and vary between people.',
             ha='center', fontsize=10)
    fig.text(0.5, 0.125, 'Clinical exposure conditions are not the SHIELDOSE-2 idealized tissue target.\n'
             'Do not use these levels to classify modeled EVA doses as safe, fatal or symptom-producing.',
             ha='center', fontsize=10, color='#384555', linespacing=1.6)
    fig.text(0.5, 0.045, 'Source: CDC, Acute Radiation Syndrome: Information for Clinicians (23 April 2024)',
             ha='center', fontsize=9, color='#596575')
    caption = ('Figure 7. Selected CDC acute-radiation reference doses, converted from Gy to mGy. '
               'These are approximate clinical reference levels, not individual outcome predictions. '
               'These references concern acute exposure to most of the body, not an isolated idealized tissue target. '
               'Duration, anatomical dose distribution and radiation type matter; proton exposures require separate biological interpretation. '
               'No SHIELDOSE-2 result is overlaid or classified. This graphic does not establish a safe dose.\n\n'
               f'Source: {SOURCE_URL}\nSource date: {SOURCE_DATE}; accessed 2026-11-15.\n'
               'No project radiation data or modeled exposure values were changed.')
    finish(fig, '07_absorbed_dose_health_reference', caption, rect=(0.025, 0.22, 0.975, 0.885))


if __name__ == '__main__':
    main()
