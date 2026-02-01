#!/usr/bin/env python3
"""Run scenario sensitivity analysis: test different carbon intensity scenarios."""
import sys
from pathlib import Path
import copy

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import make_toy_instance, solve_baseline, solve_capped_impact, CFLPInstance
from src.utils import save_instance, solution_to_dict, load_instance, EXISTING_SITES
from src.analysis import compute_kpis
import pandas as pd
import json


def create_carbon_scenario(inst: CFLPInstance, scenario_name: str) -> CFLPInstance:
    """
    Create a scenario by modifying carbon intensity factors.
    
    Scenarios:
    - "clean": Lower CO2 factors (multiply by 0.7)
    - "dirty": Higher CO2 factors (multiply by 1.3)
    """
    if scenario_name == "clean":
        # Clean grid year: lower CO2 factors
        new_e_co2 = {i: e * 0.7 for i, e in inst.e_co2.items()}
    elif scenario_name == "dirty":
        # Dirty grid year: higher CO2 factors
        new_e_co2 = {i: e * 1.3 for i, e in inst.e_co2.items()}
    else:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    
    # Create new instance with modified e_co2
    return CFLPInstance(
        I=inst.I,
        R=inst.R,
        F=inst.F,
        O=inst.O,
        C=inst.C,
        c=inst.c,
        e_co2=new_e_co2,
        w=inst.w,
        P=inst.P,
        d=inst.d,
        d_inf=inst.d_inf,
        d_train=inst.d_train,
        Lmax=inst.Lmax,
        Lmax_inf=inst.Lmax_inf,
        Lmax_train=inst.Lmax_train,
        phi=inst.phi,
    )


def main():
    # Load or generate instance
    instance_path = Path("data/toy_instance.json")
    if instance_path.exists():
        print(f"Loading instance from {instance_path}...")
        inst = load_instance(str(instance_path))
    else:
        print("Generating new toy instance with split demand...")
        inst = make_toy_instance(n_sites=10, n_regions=8, seed=3, phi=10.0, use_split_demand=True)
        save_instance(inst, str(instance_path))
    
    # Define scenarios
    scenarios = ["baseline_grid", "clean", "dirty"]
    
    # First solve baseline to get reference caps
    print("\nSolving baseline model for reference...")
    baseline_sol = solve_baseline(inst, output_flag=0, existing_sites=EXISTING_SITES)
    
    if baseline_sol.total_co2 is None or baseline_sol.total_water is None:
        print("ERROR: Baseline solution is invalid.")
        return
    
    # Set caps at 90% of baseline
    gamma_co2 = 0.90 * baseline_sol.total_co2
    gamma_w = 1.0 * baseline_sol.total_water
    
    print(f"\nUsing caps: CO₂={gamma_co2:.2f}, Water={gamma_w:.2f}")
    
    results = []
    
    for scenario_name in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario_name}")
        print(f"{'='*60}")
        
        # Create scenario instance
        if scenario_name == "baseline_grid":
            scenario_inst = inst
        else:
            scenario_inst = create_carbon_scenario(inst, scenario_name)
        
        # Solve baseline under this scenario
        print(f"\nSolving baseline model...")
        baseline_scenario_sol = solve_baseline(scenario_inst, output_flag=0, existing_sites=EXISTING_SITES)
        
        # Solve capped model under this scenario
        print(f"Solving capped model (90% CO₂ cap)...")
        capped_scenario_sol = solve_capped_impact(
            scenario_inst,
            gamma_co2=gamma_co2,
            gamma_w=gamma_w,
            output_flag=0,
            existing_sites=EXISTING_SITES
        )
        
        # Compute KPIs
        baseline_kpis = compute_kpis(scenario_inst, baseline_scenario_sol, EXISTING_SITES)
        capped_kpis = compute_kpis(scenario_inst, capped_scenario_sol, EXISTING_SITES)
        
        # Get opened sites
        baseline_sites = tuple(sorted(i for i in scenario_inst.I if baseline_scenario_sol.x.get(i, 0.0) > 0.5))
        capped_sites = tuple(sorted(i for i in scenario_inst.I if capped_scenario_sol.x.get(i, 0.0) > 0.5))
        
        # Check if plan changed
        plan_changed = baseline_sites != capped_sites
        
        print(f"\nBaseline results:")
        print(f"  Cost: {baseline_kpis['total_cost']:.2f}" if baseline_kpis['total_cost'] is not None else "  Cost: N/A")
        print(f"  CO₂: {baseline_kpis['total_co2']:.2f}" if baseline_kpis['total_co2'] is not None else "  CO₂: N/A")
        print(f"  Water: {baseline_kpis['total_water']:.2f}" if baseline_kpis['total_water'] is not None else "  Water: N/A")
        print(f"  Sites opened: {baseline_kpis['num_opened_sites']}")
        print(f"  Sites: {baseline_sites}")
        
        print(f"\nCapped results:")
        print(f"  Cost: {capped_kpis['total_cost']:.2f}" if capped_kpis['total_cost'] is not None else "  Cost: N/A (infeasible)")
        print(f"  CO₂: {capped_kpis['total_co2']:.2f}" if capped_kpis['total_co2'] is not None else "  CO₂: N/A")
        print(f"  Water: {capped_kpis['total_water']:.2f}" if capped_kpis['total_water'] is not None else "  Water: N/A")
        print(f"  Sites opened: {capped_kpis['num_opened_sites']}")
        print(f"  Sites: {capped_sites}")
        print(f"  Plan changed: {plan_changed}")
        
        # Store results
        baseline_cost = baseline_kpis['total_cost'] or 0.0
        baseline_co2 = baseline_kpis['total_co2'] or 0.0
        capped_cost = capped_kpis['total_cost']
        capped_co2 = capped_kpis['total_co2']
        
        results.append({
            "scenario": scenario_name,
            "baseline_cost": baseline_cost,
            "baseline_co2": baseline_co2,
            "baseline_water": baseline_kpis['total_water'] or 0.0,
            "baseline_sites": len(baseline_sites),
            "baseline_sites_list": ",".join(baseline_sites),
            "capped_cost": capped_cost,
            "capped_co2": capped_co2,
            "capped_water": capped_kpis['total_water'] or 0.0,
            "capped_sites": len(capped_sites),
            "capped_sites_list": ",".join(capped_sites),
            "plan_changed": plan_changed,
            "cost_change_pct": ((capped_cost - baseline_cost) / baseline_cost * 100) if baseline_cost > 0 and capped_cost is not None else None,
            "co2_change_pct": ((capped_co2 - baseline_co2) / baseline_co2 * 100) if baseline_co2 > 0 and capped_co2 is not None else None,
        })
    
    # Save results
    results_path = Path("results/scenario_sensitivity.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump({"scenarios": results, "gamma_co2": gamma_co2, "gamma_w": gamma_w}, f, indent=2)
    print(f"\nSaved scenario results to {results_path}")
    
    # Save as CSV table
    csv_path = Path("results/scenario_sensitivity.csv")
    df = pd.DataFrame(results)
    df.to_csv(csv_path, index=False)
    print(f"Saved scenario results table to {csv_path}")
    
    print("\n" + "="*60)
    print("SCENARIO SENSITIVITY SUMMARY")
    print("="*60)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

