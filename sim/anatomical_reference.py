"""MAX/FAX event totals; reference anatomy, not individual sex-based sensitivity."""
from functools import lru_cache
import json
import re
import pandas as pd
from radiation.anatomical_environment import ORGANS
from radiation.radiation_model import ROOT, sha256

FAX_DIRECTORY = ROOT/'data/raw/oltaris/fax_2026-11-18'
FAX_SOURCES = tuple(sorted(FAX_DIRECTORY.glob('*.txt'))) + (FAX_DIRECTORY/'provenance.json',)


@lru_cache(maxsize=1)
def fax_totals():
    records={}
    for entry in json.loads((FAX_DIRECTORY/'provenance.json').read_text()):
        path=FAX_DIRECTORY/entry['file']
        if sha256(path)!=entry['sha256']:
            raise ValueError('FAX source checksum mismatch')
        text=path.read_text()
        if 'Anatomical model is FAX' not in text:
            raise ValueError('Expected FAX anatomical source')
        normalization=re.search(r'J0=([^ ]+) particles/cm2',text)[1]
        years={'1.010E+11':100,'2.066E+11':1000}[normalization]
        depth=float(re.search(r'Al Sphere \(([0-9.]+) g/cm2',text)[1])
        absorbed=float(re.search(r'^BFO\s+([0-9.E+-]+)\s+mGy\s*$',text,re.M)[1])
        section=text.split('Gray Equivalent\nOrgan')[1].split('Data Tables')[0]
        equivalent={organ:float(value)*10 for organ,value in
            re.findall(r'(BFO|Skin|Lens)\s+([0-9.E+-]+)\s+cGy-eq',section)}
        key=years,depth
        if key in records or set(equivalent)!={'BFO','Skin','Lens'}:
            raise ValueError('Duplicate or incomplete FAX configuration')
        records[key]=(absorbed,equivalent['BFO'],equivalent['Skin'],equivalent['Lens'])
    if set(records)!={(years,depth) for years in (100,1000) for depth in (.4,20)}:
        raise ValueError('Incomplete FAX event library')
    return records


@lru_cache(maxsize=16)
def dose_vector(anatomy, severity, depth):
    """BFO mGy, then BFO/skin/lens mGy-Eq; full SPE totals, not dose rates."""
    if anatomy=='FAX':
        return fax_totals()[int(severity),depth]
    if anatomy!='MAX':
        raise ValueError('Anatomical reference must be MAX or FAX')
    data=pd.read_csv(ORGANS)
    rows=data[data.sapphire_return_period_years.eq(int(severity)) &
              data.aluminum_areal_density_g_cm2.eq(depth)].set_index('organ')
    return (float(rows.loc['BFO','absorbed_dose_mGy']),
            *(float(rows.loc[organ,'gray_equivalent_mGy_eq']) for organ in ('BFO','Skin','Lens')))
