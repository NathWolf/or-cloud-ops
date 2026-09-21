#!/usr/bin/env python3
"""Fail-fast scientific checks on exported results, not implementation snapshots."""
import json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.hierarchical import instance_from_dict,solution_from_dict,make_public_calibrated_hierarchical_instance
from src.contract_audit import residuals

def verify(root):
 inst=instance_from_dict(json.loads((root/'instance.json').read_text()))
 src=pd.read_csv('data/public/carbon_2024.csv').set_index('country')
 for i in inst.I:
  mean=sum(inst.e_location[i,t,'base'] for t in inst.T)/len(inst.T)
  expected=src.loc[inst.metadata['site_info'][i]['country'],'value']/1000
  assert abs(mean-expected)<1e-12,('calibration_not_used',i)
 count=0
 for f in (root/'solutions').glob('*.json'):
  s=solution_from_dict(json.loads(f.read_text()),inst)
  if s.obj is None:
   assert s.status==3,(f,'unexpected failure',s.status)
   continue
  assert s.status==2,(f,'not optimal')
  for k,v in residuals(inst,s).items():
   if k.endswith(('error','excess')):assert v<1e-5,(f,k,v)
  p=s.params
  if p.get('gamma_co2') is not None:assert s.expected_co2<=p['gamma_co2']+1e-5
  if p.get('gamma_w_by_period'):
   assert all(s.period_water[t]<=v+1e-5 for t,v in p['gamma_w_by_period'].items())
  if not p.get('diagnostic'):
   obj=s.total_first_stage_cost+s.expected_operating_cost+s.expected_latency_proxy+p.get('lambda_c',0)*s.expected_co2+p.get('lambda_w',0)*s.expected_water
   assert abs(obj-s.obj)<1e-5,(f,'objective components inconsistent')
  count+=1
 cap=pd.read_csv(root/'cap_sweep.csv').sort_values('alpha',ascending=False)
 assert (cap.status==2).all()
 assert (cap.economic_cost.diff().dropna()>=-1e-6).all(),'tightening cap decreased optimal cost'
 assert (cap.expected_co2<=cap.gamma_co2+1e-5).all()
 a=pd.read_csv(root/'handoff_audit.csv').set_index('experiment')
 assert a.loc['Frozen cost-only / expected targets','status']==3
 assert a.loc['Frozen expected-target plan','status']==2
 assert a.loc['Frozen cost-only / minimum excess','minimum_normalized_excess']>1e-5
 assert a.loc['Scenario-wise targets / replan','worst_carbon_ratio']<=1+1e-6
 assert a.loc['Scenario-wise targets / replan','worst_water_ratio']<=1+1e-6
 acc=pd.read_csv(root/'accounting_experiments.csv')
 assert acc[acc.accounting_experiment=='cap_85'].gamma_co2.nunique()==1
 try:make_public_calibrated_hierarchical_instance(calibration_status='public_data')
 except ValueError:pass
 else:raise AssertionError('unloaded calibration was accepted')
 print(f'PASS: {count} feasible saved solutions; source calibration, residuals, objective, caps, handoffs and accounting invariants')

if __name__=='__main__':verify(Path(sys.argv[1] if len(sys.argv)>1 else 'artifacts/revision_2026_09_21'))
