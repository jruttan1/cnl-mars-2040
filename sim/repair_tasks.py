"""Team-defined external repair workload; not CNL-specified repair procedures."""
REPAIRS = ('communications', 'monitoring', 'propulsion_initial', 'propulsion')
REFERENCE_ORDER = ('monitoring', 'propulsion_initial', 'propulsion', 'communications')


def task_descriptions(engine):
    shared = {
        'monitoring': 'Restore external sensors and wiring needed to assess subsequent repair work',
        'communications': 'Repair damaged antenna/feed connections',
    }
    if engine == 'NTP':
        return dict(shared,
            propulsion_initial='Repair an accessible hydrogen-feed section after remote isolation',
            propulsion='Repair separate external engine-control connections needed for restart readiness')
    if engine == 'NEP':
        return dict(shared,
            propulsion_initial='Isolate and bypass the damaged accessible radiator-loop section',
            propulsion='Restore additional heat-rejection capacity needed for sustained reactor operation')
    raise ValueError('Unknown engine')
