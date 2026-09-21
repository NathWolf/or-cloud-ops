#!/usr/bin/env python3
"""Audit main results and run frozen-envelope, uncertainty and repeat-seed tests."""
import sys, json, platform, hashlib, argparse
from pathlib import Path
from dataclasses import replace
import pandas as pd
import gurobipy as gp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.hierarchical import (instance_from_dict, solution_from_dict,
    solution_to_dict, make_public_calibrated_hierarchical_instance,
    solve_hierarchical_baseline, solve_hierarchical_capped, emission_factor)
from src.analysis_hierarchical import economic_cost
from src.contract_audit import solve_contract, residuals, target_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--results-dir',default='results/revision_2026_09_21')
    args=p.parse_args();root=Path(args.results_dir)
    inst=instance_from_dict(json.loads((root/'instance.json').read_text()))
    def read(name):
        return solution_from_dict(json.loads((root/'solutions'/f'{name}.json').read_text()),inst)
    baseline=read('baseline');hard=read('handoff_hard_envelope')
    carbon=.85*baseline.expected_co2;water={t:.9*v for t,v in baseline.period_water.items()}
    rows=[]
    for file in sorted((root/'solutions').glob('*.json')):
        sol=solution_from_dict(json.loads(file.read_text()),inst)
        row={'solution':file.stem,**residuals(inst,sol)}
        for k,v in row.items():
            if k.endswith(('error','excess')): assert v<1e-5,(file,k,v)
        rows.append(row)
    pd.DataFrame(rows).to_csv(root/'verification.csv',index=False)
    experiments=[('Cost-only',baseline),('Expected-target plan',hard)]
    for name,plan,robust,diagnose in [
        ('Frozen cost-only / expected targets',baseline,False,False),
        ('Frozen cost-only / minimum excess',baseline,False,True),
        ('Frozen expected-target plan',hard,False,False),
        ('Scenario-wise targets / replan',None,True,False),
        ('Frozen expected plan / scenario-wise targets',hard,True,False)]:
        print(name,flush=True)
        sol=solve_contract(inst,carbon,water,plan=plan,scenario_wise=robust,diagnose=diagnose)
        experiments.append((name,sol))
        (root/'solutions'/('audit_'+str(len(experiments))+'.json')).write_text(json.dumps(solution_to_dict(sol),indent=2))
    pd.DataFrame([dict(experiment=name,status=sol.status,cost=economic_cost(sol),
        minimum_normalized_excess=sol.obj if sol.params.get('diagnostic') else None,
        **target_metrics(inst,sol,carbon,water)) for name,sol in experiments]).to_csv(root/'handoff_audit.csv',index=False)
    # Finite scenario-set stress tests: no probability-of-failure claim.
    robust=experiments[5][1]
    stress=[]
    for factor in [1.0,1.05,1.10,1.20]:
        stressed=replace(inst,demand={k:v*factor for k,v in inst.demand.items()})
        for label,plan in [('Expected plan',hard),('Scenario-wise plan',robust)]:
            sol=solve_contract(stressed,carbon,water,plan=plan,scenario_wise=True)
            stress.append(dict(plan=label,demand_multiplier=factor,status=sol.status,
                               **target_metrics(stressed,sol,carbon,water)))
    pd.DataFrame(stress).to_csv(root/'stress_tests.csv',index=False)
    seed_rows=[]
    for seed in range(11,21):
        print('Replication seed',seed,flush=True)
        ins=make_public_calibrated_hierarchical_instance(seed=seed,carbon_data_path='data/public/carbon_2024.csv')
        b=solve_hierarchical_baseline(ins,mip_gap=0.0)
        h=solve_hierarchical_capped(ins,gamma_co2=.85*b.expected_co2,
             gamma_w_by_period={t:.9*v for t,v in b.period_water.items()},mip_gap=0.0)
        f=solve_contract(ins,.85*b.expected_co2,{t:.9*v for t,v in b.period_water.items()},plan=b)
        seed_rows.append(dict(seed=seed,baseline_status=b.status,hard_status=h.status,
          frozen_status=f.status,cost_increase_pct=100*(economic_cost(h)/economic_cost(b)-1),
          **residuals(ins,h)))
    pd.DataFrame(seed_rows).to_csv(root/'seed_sensitivity.csv',index=False)
    # Common-boundary re-evaluation prevents comparing accounting metrics as physical savings.
    accounting=pd.read_csv(root/'accounting_experiments.csv')
    for mode in ['location_time','location_annual','market_time','market_annual']:
        sol=solve_hierarchical_capped(inst,gamma_co2=carbon,accounting_mode=mode,mip_gap=0.0)
        mask=(accounting.accounting_mode==mode)&(accounting.accounting_experiment=='cap_85')
        accounting.loc[mask,'common_boundary_carbon']=sum(inst.prob[w]*inst.e_location[i,t,w]*v for (i,r,t,k,w),v in sol.y.items())
        accounting.loc[mask,'portfolio']=','.join(i for i in inst.I if sol.x[i]>.5)
    accounting.to_csv(root/'accounting_experiments.csv',index=False)
    manifest=dict(python=platform.python_version(),platform=platform.platform(),host=platform.node(),
      gurobi='.'.join(map(str,gp.gurobi.version())),threads=1,mip_gap_requested=0.0,
      public_data_sha256=hashlib.sha256(Path('data/public/carbon_2024.csv').read_bytes()).hexdigest(),
      source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path('src/models/hierarchical.py'),Path('src/contract_audit.py'),Path(__file__)]})
    (root/'audit_manifest.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
