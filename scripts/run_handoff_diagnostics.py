#!/usr/bin/env python3
"""Minimize joint normalized target excess under each reference revision scope."""
import argparse,csv,hashlib,json,platform,sys
from pathlib import Path
import gurobipy as gp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.hierarchical import instance_from_dict,solution_from_dict,solution_to_dict,build_hierarchical_model,solve_and_extract
from src.contract_audit import residuals

CASES={'allocation_only':('x','capacity','g'),'capacity_only':('x','g'),'links_only':('x','capacity'),'capacity_and_links':('x',),'all_decisions':()}

def components(inst,sol,carbon,water):
 values={'carbon_excess':max(0,sol.expected_co2/carbon-1)}
 values.update({t+'_water_excess':max(0,sol.period_water[t]/water[t]-1) for t in inst.T})
 return values

def verify(inst,base,sol,fixed,carbon,water):
 assert sol.status==2
 for k,v in residuals(inst,sol).items():
  if k.endswith(('error','excess')):assert v<1e-5,(k,v)
 for name in fixed:
  assert all(abs(v-getattr(base,name)[k])<1e-5 for k,v in getattr(sol,name).items())
 vals=components(inst,sol,carbon,water)
 assert abs(sum(vals.values())-sol.obj)<1e-7
 return vals

def main():
 p=argparse.ArgumentParser();p.add_argument('--reference-dir',default='artifacts/revision_2026_09_21');p.add_argument('--output-dir',default='results/handoff_diagnostics');p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 ref=Path(a.reference_dir);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 inst=instance_from_dict(json.loads((ref/'instance.json').read_text()));base=solution_from_dict(json.loads((ref/'solutions/baseline.json').read_text()),inst)
 carbon=.85*base.expected_co2;water={t:.9*v for t,v in base.period_water.items()};rows=[]
 for case,fixed in CASES.items():
  if a.verify_only:sol=solution_from_dict(json.loads((out/(case+'.json')).read_text()),inst)
  else:
   m,x,cap,g,y,_=build_hierarchical_model(inst)
   for name,variables in [('x',x),('capacity',cap),('g',g)]:
    if name in fixed:
     for k,v in variables.items():v.LB=v.UB=getattr(base,name)[k] if name=='capacity' else round(getattr(base,name)[k])
   sc=m.addVar(lb=0,name='carbon_excess');sw=m.addVars(inst.T,lb=0,name='water_excess')
   m.addConstr(gp.quicksum(inst.prob[w]*inst.e_location[i,t,w]*v for (i,r,t,k,w),v in y.items())<=carbon*(1+sc))
   for t in inst.T:
    m.addConstr(gp.quicksum(inst.prob[w]*inst.water[i,tt,w]*v for (i,r,tt,k,w),v in y.items() if tt==t)<=water[t]*(1+sw[t]))
   m.setObjective(sc+sw.sum(),gp.GRB.MINIMIZE)
   sol=solve_and_extract(inst,m,x,cap,g,y,accounting_mode='location_time',mip_gap=0.0,params={'diagnostic':True,'fixed_commitments':list(fixed),'gamma_co2':carbon,'gamma_w_by_period':water})
   m.dispose();(out/(case+'.json')).write_text(json.dumps(solution_to_dict(sol),indent=2))
  vals=verify(inst,base,sol,fixed,carbon,water)
  rows.append(dict(case=case,minimum_sum=sol.obj,**vals));print(rows[-1],flush=True)
 if a.verify_only:
  saved=list(csv.DictReader((out/'diagnostics.csv').open()))
  assert len(saved)==len(rows)
  for r,s in zip(rows,saved):
   for k,v in r.items():assert v==s[k] if k=='case' else abs(v-float(s[k]))<1e-8
  checks=json.loads((out/'SHA256SUMS.json').read_text())
  actual={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS.json'}
  assert checks==actual
 else:
  with (out/'diagnostics.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  source=['scripts/run_handoff_diagnostics.py','src/models/hierarchical.py','src/contract_audit.py']
  manifest={'python':platform.python_version(),'gurobi':'.'.join(map(str,gp.gurobi.version())),'threads':1,'mip_gap':0,'objective':'sum of positive carbon and four seasonal-water excesses divided by their own targets; equal weights','reference_sha256':{str(p.relative_to(ref)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ref/'instance.json',ref/'solutions/baseline.json']},'source_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in source}}
  (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
  checks={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS.json'}
  (out/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2))
 print('PASS: five diagnostic solutions and independently recomputed target excesses')
if __name__=='__main__':main()
