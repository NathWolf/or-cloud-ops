#!/usr/bin/env python3
"""Test which pre-approval commitments must be revised to meet fixed targets."""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import gurobipy as gp
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.hierarchical import (
    instance_from_dict, instance_to_dict, solution_from_dict, solution_to_dict,
    make_public_calibrated_hierarchical_instance, solve_hierarchical_baseline,
    build_hierarchical_model, solve_and_extract,
)
from src.analysis_hierarchical import economic_cost
from src.contract_audit import residuals, target_metrics

# All cases permit allocation changes; names identify additional decisions reopened.
CASES = {
    'allocation_only': ('x', 'capacity', 'g'),
    'capacity_only': ('x', 'g'),
    'links_only': ('x', 'capacity'),
    'capacity_and_links': ('x',),
    'all_decisions': (),
}


def solve_revision(inst, baseline, fixed):
    carbon = .85 * baseline.expected_co2
    water = {t: .9 * v for t, v in baseline.period_water.items()}
    m, x, capacity, g, y, _ = build_hierarchical_model(
        inst, gamma_co2=carbon, gamma_w_by_period=water)
    for name, variables in [('x', x), ('capacity', capacity), ('g', g)]:
        if name in fixed:
            for key, var in variables.items():
                value = getattr(baseline, name)[key]
                var.LB = var.UB = value if name == 'capacity' else round(value)
    sol = solve_and_extract(inst, m, x, capacity, g, y,
        accounting_mode='location_time', mip_gap=0.0,
        params=dict(gamma_co2=carbon, gamma_w_by_period=water,
                    fixed_commitments=list(fixed), pre_approval_revision=True))
    m.dispose()
    return sol


def verify_case(inst, baseline, sol, fixed):
    assert sol.status in (2, 3), ('unexpected solver status', sol.status)
    if sol.status == 3:
        return
    for key, value in residuals(inst, sol).items():
        if key.endswith(('error', 'excess')):
            assert value < 1e-5, (key, value)
    for name in fixed:
        assert all(abs(value-getattr(baseline, name)[key]) < 1e-5
                   for key, value in getattr(sol, name).items()), name
    metrics = target_metrics(inst, sol, .85*baseline.expected_co2,
                             {t:.9*v for t,v in baseline.period_water.items()})
    assert metrics['expected_carbon_ratio'] <= 1+1e-7
    assert metrics['expected_water_ratio'] <= 1+1e-7
    assert abs(economic_cost(sol)-sol.obj) < 1e-5
    assert sol.params['mip_gap'] < 1e-8


def verify_archive(root):
    records = []
    for seed_dir in sorted(root.glob('seed_*')):
        inst = instance_from_dict(json.loads((seed_dir/'instance.json').read_text()))
        base = solution_from_dict(json.loads((seed_dir/'baseline.json').read_text()), inst)
        costs = {}
        for case, fixed in CASES.items():
            sol = solution_from_dict(json.loads((seed_dir/(case+'.json')).read_text()), inst)
            verify_case(inst, base, sol, fixed)
            costs[case] = economic_cost(sol) if sol.status == 2 else float('inf')
            records.append((int(seed_dir.name.split('_')[1]), case, sol.status, costs[case]))
        # Relaxing fixed commitments cannot raise the minimum planning cost.
        for stricter, looser in [('allocation_only','capacity_only'),('allocation_only','links_only'),
                                ('capacity_only','capacity_and_links'),('links_only','capacity_and_links'),
                                ('capacity_and_links','all_decisions')]:
            assert costs[looser] <= costs[stricter]+1e-5, (seed_dir, stricter, looser)
    data = pd.read_csv(root/'commitment_review.csv').set_index(['seed','case'])
    assert len(data) == len(records) and len(records) > 0
    for seed, case, status, cost in records:
        row = data.loc[seed,case]
        assert row.status == status
        if status == 2:
            assert abs(row.economic_cost-cost) < 1e-5
    checks = json.loads((root/'SHA256SUMS.json').read_text())
    actual = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.json'}
    assert checks == actual, 'archive checksums'
    print(f'PASS: {len(records)} commitment cases; fixed decisions, residuals, targets, objective ordering and checksums')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reference-dir', default='artifacts/revision_2026_09_21')
    p.add_argument('--output-dir', default='results/commitment_review')
    p.add_argument('--verify-only', action='store_true')
    a = p.parse_args()
    root = Path(a.output_dir)
    if a.verify_only:
        verify_archive(root)
        return
    ref = Path(a.reference_dir)
    rows = []
    for seed in range(11,21):
        if seed == 11:
            inst = instance_from_dict(json.loads((ref/'instance.json').read_text()))
            base = solution_from_dict(json.loads((ref/'solutions/baseline.json').read_text()), inst)
        else:
            inst = make_public_calibrated_hierarchical_instance(
                seed=seed, carbon_data_path='data/public/carbon_2024.csv')
            base = solve_hierarchical_baseline(inst, mip_gap=0.0)
        out = root/f'seed_{seed}'
        out.mkdir(parents=True,exist_ok=True)
        (out/'instance.json').write_text(json.dumps(instance_to_dict(inst),indent=2))
        (out/'baseline.json').write_text(json.dumps(solution_to_dict(base),indent=2))
        for case, fixed in CASES.items():
            sol = solve_revision(inst, base, fixed)
            verify_case(inst, base, sol, fixed)
            (out/(case+'.json')).write_text(json.dumps(solution_to_dict(sol),indent=2))
            row = dict(seed=seed,case=case,fixed_commitments=','.join(fixed),status=sol.status,
                       economic_cost=economic_cost(sol),cost_increase_pct=None)
            if sol.status == 2:
                row.update(cost_increase_pct=100*(economic_cost(sol)/economic_cost(base)-1),
                    capacity_change_l1=sum(abs(sol.capacity[i]-base.capacity[i]) for i in inst.I),
                    added_links=sum(sol.g[k]>.5 and base.g[k]<.5 for k in sol.g),
                    removed_links=sum(sol.g[k]<.5 and base.g[k]>.5 for k in sol.g),
                    **target_metrics(inst, sol, .85*base.expected_co2,
                                     {t:.9*v for t,v in base.period_water.items()}))
            rows.append(row)
        print('Completed seed',seed,flush=True)
    pd.DataFrame(rows).to_csv(root/'commitment_review.csv',index=False)
    source_files=['src/models/hierarchical.py','src/contract_audit.py','scripts/run_commitment_review.py']
    manifest=dict(python=platform.python_version(),gurobi='.'.join(map(str,gp.gurobi.version())),
                  threads=1,mip_gap=0,scope='Pre-approval reoptimization; excludes sunk and conversion costs',
                  source_sha256={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in source_files},
                  input_sha256=hashlib.sha256((ref/'instance.json').read_bytes()).hexdigest())
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    checks={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.json'}
    (root/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2))
    verify_archive(root)

if __name__ == '__main__':
    main()
