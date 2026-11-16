"""Synthetic scenario conservation and fail-closed transport tests.

Small invented numbers below are isolated test fixtures, never scientific outputs.
"""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import radiation_model as model
from spenvis_audit import load_verified_spectra,audit_transport


class SapphireModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=model.load_config()
        cls.spectra=load_verified_spectra()
        cls.profiles=model.build_temporal_profiles(cls.cfg)

    def test_spectra_and_transport_evidence(self):
        self.assertEqual(set(self.spectra.return_period_years),{100,1000})
        audit=audit_transport(self.spectra)
        self.assertTrue(audit['legacy_shieldose_displayed_doses_identical'])
        self.assertTrue(all(x['input_return_period_verified'] for x in audit['transport_reports']))
        self.assertEqual(audit['missing_inputs'],[])
        refs,missing=model.load_sapphire_doses(self.spectra,self.cfg)
        self.assertEqual(len(refs),12)
        self.assertEqual(missing,[])

    def test_full_template_and_observation_preservation(self):
        raw=model.load_hourly()
        for _,g in self.profiles.groupby('member_id'):
            self.assertEqual(len(g),264)
            self.assertEqual(g.in_emergency_window.sum(),72)
            self.assertEqual(g.is_gap_filled.sum(),8)
            self.assertAlmostEqual(g.normalized_bin_weight.sum(),1,places=12)
            observed=raw[f'proton_flux_gt{g.proxy_threshold_MeV.iloc[0]}_MeV'].to_numpy()
            np.testing.assert_array_equal(g.modeled_proton_flux.to_numpy()[~np.isnan(observed)],observed[~np.isnan(observed)])

    def test_every_energy_conserves_sapphire_fluence(self):
        data=model.build_synthetic_fluence(self.spectra,self.profiles,self.cfg)
        self.assertEqual(len(data),162*264)
        for _,g in data.groupby(['scenario_id','energy_MeV']):
            np.testing.assert_allclose(g.integral_fluence_in_bin_protons_cm2.sum(),g.spacecraft_integral_protons_cm2.iloc[0],rtol=1e-12)
            np.testing.assert_allclose(g.differential_fluence_in_bin_protons_cm2_MeV.sum(),g.spacecraft_differential_protons_cm2_MeV.iloc[0],rtol=1e-12)
        self.assertEqual(set(data.scenario_role),{'main','worst_case'})
        self.assertFalse(any('dose' in c for c in data.columns))

    def test_king_changes_cannot_change_synthetic_inputs(self):
        altered={**self.cfg,'historical_reference_environments':{}}
        np.testing.assert_array_equal(model.build_temporal_profiles(altered).normalized_bin_weight,self.profiles.normalized_bin_weight)
        refs,_=model.load_sapphire_doses(self.spectra,altered)
        self.assertEqual(refs,model.load_sapphire_doses(self.spectra,self.cfg)[0])

    def test_scenario_separation_and_integration(self):
        references=[]
        for scenario,total in [('test_main',12.0),('test_worst',24.0)]:
            references.append(dict(scenario_id=scenario,scenario_role=scenario,location='test_location',event_absorbed_dose_mGy=total))
        full,window=model.calculate_sapphire_dose(self.profiles,references)
        for (scenario,member),g in full.groupby(['scenario_id','member_id']):
            self.assertAlmostEqual((g.absorbed_dose_rate_mGy_h*g.bin_duration_h).sum(),g.event_absorbed_dose_mGy.iloc[0])
        for _,g in window.groupby(['scenario_id','member_id']):
            self.assertEqual(g.cumulative_absorbed_dose_mGy.iloc[0],0)
            self.assertTrue(g.cumulative_end_absorbed_dose_mGy.is_monotonic_increasing)
            c=np.r_[0,g.cumulative_end_absorbed_dose_mGy]
            expected=np.interp(9.5,np.arange(73),c)-np.interp(2.5,np.arange(73),c)
            self.assertAlmostEqual(model.seven_hour_exposure(g,2.5),expected)
        with self.assertRaises(ValueError):
            model.seven_hour_exposure(window[window.member_id.eq('gt10MeV__log_linear')],0)

    def test_verified_unit_conversion_and_rejection(self):
        from spenvis_audit import verified_shieldose_rows
        dose=verified_shieldose_rows(self.spectra)
        expected={100:[7457.1,2230.6,796.35,166.4,47.616,13.4],
                  1000:[12728,3857.3,1386.2,290.37,83.093,23.383]}
        for period,rad in expected.items():
            group=dose[dose.return_period_years.eq(period)].sort_values('aluminum_areal_density_g_cm2')
            np.testing.assert_array_equal(group.aluminum_areal_density_g_cm2,[0.4,1,2,5,10,20])
            np.testing.assert_allclose(group.original_dose_rad,rad,rtol=0,atol=0)
            np.testing.assert_allclose(group.dose_value,np.array(rad)*10,rtol=1e-14)
            self.assertTrue(group.dose_unit.eq('mGy').all())
            self.assertTrue(group.irradiation_geometry.eq('4pi').all())
            self.assertFalse(group.proton_nuclear_attenuation_included.any())
        for field,value in [('dose_unit','mSv'),('input_spectrum_sha256','wrong'),('dose_value',np.nan)]:
            bad=dose.copy();bad.loc[0,field]=value
            with patch('radiation_model.pd.read_csv',return_value=bad):
                with self.assertRaises((ValueError,AssertionError)):
                    model.load_sapphire_doses(self.spectra,self.cfg)

    def test_actual_sapphire_totals_and_exported_intervals(self):
        references,missing=model.load_sapphire_doses(self.spectra,self.cfg)
        self.assertEqual(missing,[])
        full,window=model.calculate_sapphire_dose(self.profiles,references)
        self.assertEqual(len(window),2*6*9*72)
        self.assertEqual(len(full),2*6*9*264)
        for _,g in full.groupby(['scenario_id','location','member_id']):
            self.assertAlmostEqual((g.absorbed_dose_rate_mGy_h*g.bin_duration_h).sum(),g.event_absorbed_dose_mGy.iloc[0],places=8)
            self.assertTrue(g.cumulative_event_absorbed_dose_mGy.is_monotonic_increasing)
        for _,g in window.groupby(['scenario_id','location','member_id']):
            self.assertAlmostEqual(model.seven_hour_exposure(g,0),g[g.hour_since_emergency.lt(7)].absorbed_dose_rate_mGy_h.sum(),places=9)
            self.assertTrue(g.cumulative_end_absorbed_dose_mGy.is_monotonic_increasing)
            metric='cumulative_end_absorbed_dose_mGy'
            self.assertTrue(g[metric].between(g[metric+'_sensitivity_lower'],g[metric+'_sensitivity_upper']).all())
            self.assertNotIn('OLTARIS',g.source_path.iloc[0])
        saved=model.load_baseline()
        pd.testing.assert_frame_equal(saved,model.baseline_dataset(full),check_dtype=False,rtol=1e-12)
        self.assertFalse(saved.duplicated(['scenario','shielding_g_cm2','timing_variant','hour']).any())

    def test_full_baseline_and_all_seven_hour_starts(self):
        frame=model.load_baseline()
        self.assertEqual(len(frame),28512)
        for (scenario,depth,variant),g in frame.groupby(['scenario','shielding_g_cm2','timing_variant']):
            np.testing.assert_array_equal(g.hour,np.arange(264))
            self.assertAlmostEqual(g.normalized_bin_weight.sum(),1,places=12)
            self.assertAlmostEqual(g.dose_rate_mGy_h.sum(),g.event_absorbed_dose_mGy.iloc[0],places=8)
            self.assertTrue(g.cumulative_dose_mGy.is_monotonic_increasing)
            c=np.r_[g.cumulative_dose_mGy, g.cumulative_end_dose_mGy.iloc[-1]]
            for start in range(258):
                got=model.baseline_interval_dose(scenario,depth,start,start+7,variant,baseline=g)
                self.assertAlmostEqual(got,g.dose_rate_mGy_h.iloc[start:start+7].sum(),places=8)
                self.assertAlmostEqual(got,c[start+7]-c[start],places=8)
            got=model.baseline_interval_dose(scenario,depth,256.5,263.5,variant,baseline=g)
            self.assertAlmostEqual(got,np.interp(263.5,np.arange(265),c)-np.interp(256.5,np.arange(265),c),places=8)

    def test_dataset_query_needs_no_reconstruction(self):
        with patch.object(model,'build_environment',side_effect=AssertionError('No reconstruction')):
            self.assertGreater(model.baseline_interval_dose('SAPPHIRE-1-in-100',0.4,16,23),0)
        frame=model.load_baseline()
        for scenario,depth,start,end,variant in [
            ('unknown',0.4,0,7,None),('SAPPHIRE-1-in-100',3,0,7,None),
            ('SAPPHIRE-1-in-100',0.4,-1,6,None),('SAPPHIRE-1-in-100',0.4,258,265,None),
            ('SAPPHIRE-1-in-100',0.4,23,16,None),('SAPPHIRE-1-in-100',0.4,0,7,'unknown')]:
            with self.assertRaises(ValueError):
                model.baseline_interval_dose(scenario,depth,start,end,variant,baseline=frame)

    def test_freeze_guard(self):
        import hashlib,json
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'baseline.csv'; manifest=Path(temp)/'manifest.json'
            frame=pd.DataFrame({'value':[1.0]})
            manifest.write_text(json.dumps({'csv_sha256':hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()}))
            with patch.object(model,'BASELINE_PATH',path),patch.object(model,'BASELINE_MANIFEST',manifest):
                model.write_baseline(frame)
                before=path.read_bytes()
                with self.assertRaises(ValueError):model.write_baseline(pd.DataFrame({'value':[2.0]}))
                self.assertEqual(path.read_bytes(),before)

    def test_explicit_tissue_target_metadata(self):
        from spenvis_audit import verified_shieldose_rows
        dose=verified_shieldose_rows(self.spectra)
        mission=pd.read_csv(model.ROOT/'data/processed/mission_radiation_environment.csv')
        intervals=pd.read_csv(model.ROOT/'outputs/model/synthetic_sapphire_interval_exposure.csv')
        for frame in [dose,mission,intervals]:
            self.assertTrue(frame.dose_quantity.eq('absorbed_dose').all())
            self.assertTrue(frame.target_type.eq('idealized_tissue').all())
            self.assertTrue(frame.target_geometry.eq('centre_of_aluminium_spheres').all())
            self.assertTrue(frame.geometry.eq('center_of_aluminum_sphere').all())
            self.assertTrue(frame.unit.eq('mGy').all())
            self.assertFalse(frame.nuclear_attenuation.any())
        self.assertTrue(mission.dose_rate_unit.eq('mGy/h').all())

    def test_raw_preservation_and_idempotent_import(self):
        import json,hashlib
        from prepare_data import build
        root=model.ROOT
        before=json.loads((root/'data/raw/archive/before_verified_sapphire/preservation_manifest.json').read_text())
        # Old local backup snapshots and Finder metadata are not distributed via Git.
        # Check them when present; required importer inputs are checked by build().
        for path,expected in before.items():
            file=root/path
            optional=(path.startswith('data/raw/archive/') or file.name=='.DS_Store' or
                      file.name=='particle_fluence_vs_energy_isotope_and_depth.dat')
            if optional and not file.exists():continue
            self.assertEqual(model.sha256(file),expected)
        manifest=json.loads((root/'data/raw/spenvis/verified_sapphire_manifest.json').read_text())
        self.assertEqual(len(manifest['files']),8)
        for record in manifest['files']:self.assertEqual(model.sha256(root/record['path']),record['sha256'])
        if not (root/'data/raw/archive/previous_processed/shielding_dose.csv').exists():
            self.skipTest('Full source rebuild needs the local-only archived shielding_dose.csv')
        rebuilt=build()['shielding_dose.csv']
        saved=pd.read_csv(root/'data/processed/shielding_dose.csv')
        self.assertEqual(len(rebuilt),2764)
        self.assertEqual(saved.validation_status.eq('validated_spectrum_link').sum(),12)
        pd.testing.assert_frame_equal(rebuilt,saved,check_dtype=False,rtol=1e-12)


if __name__=='__main__':unittest.main()
