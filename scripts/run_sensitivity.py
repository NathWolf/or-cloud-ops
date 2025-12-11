#!/usr/bin/env python3
"""Run sensitivity analysis for capped model with varying cap levels."""
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import make_toy_instance, solve_baseline, solve_capped_impact
from src.utils import save_instance, load_instance, FIXED_SITES


def main():
    # Load or generate instance
    instance_path = Path("data/toy_instance.json")
    if instance_path.exists():
        print(f"Loading instance from {instance_path}...")
        inst = load_instance(str(instance_path))
    else:
        print("Generating new toy instance...")
        inst = make_toy_instance(n_sites=10, n_regions=8, seed=3, phi=10.0)
        save_instance(inst, str(instance_path))
    
    # Solve baseline to get reference values
    print("\nSolving baseline model for reference...")
    baseline_sol = solve_baseline(inst, output_flag=0, fixed_sites=FIXED_SITES)
    
    if baseline_sol.total_co2 is None or baseline_sol.total_water is None:
        print("ERROR: Baseline solution is invalid.")
        return
    
    baseline_co2 = baseline_sol.total_co2
    baseline_water = baseline_sol.total_water
    
    # Run sensitivity analysis with different cap levels
    cap_levels = [1.0, 0.95, 0.90, 0.85, 0.80]  # 100%, 95%, 90%, 85%, 80%
    sensitivity_results = []
    
    print("\nRunning sensitivity analysis...")
    for alpha in cap_levels:
        gamma_co2 = alpha * baseline_co2
        gamma_w = alpha * baseline_water
        
        print(f"  Testing cap at {alpha*100:.0f}% of baseline...")
        sol = solve_capped_impact(
            inst,
            gamma_co2=gamma_co2,
            gamma_w=gamma_w,
            output_flag=0,
            fixed_sites=FIXED_SITES
        )
        
        if sol.status == 2 and sol.total_cost is not None:  # Optimal
            num_opened = sum(1 for v in sol.x.values() if abs(v) > 0.5)
            sensitivity_results.append((alpha * 100, sol.total_cost, num_opened))
            print(f"    Cost: {sol.total_cost:.2f}, Sites opened: {num_opened}")
        else:
            print(f"    Model infeasible or failed (status: {sol.status})")
            break  # Stop if infeasible
    
    # Save results
    results_path = Path("results/sensitivity_analysis.json")
    with open(results_path, "w") as f:
        json.dump({
            "baseline_co2": baseline_co2,
            "baseline_water": baseline_water,
            "results": sensitivity_results
        }, f, indent=2)
    
    print(f"\nSaved sensitivity results to {results_path}")
    print(f"\nSensitivity analysis complete: {len(sensitivity_results)} valid solutions")


if __name__ == "__main__":
    main()

