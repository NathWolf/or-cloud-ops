#!/usr/bin/env python3
"""Run capped-impact CFLP model and save results."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import make_toy_instance, solve_baseline, solve_capped_impact
from src.utils import save_instance, solution_to_dict, load_instance
import pandas as pd
import json


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
    
    # First solve baseline to get reference values
    print("\nSolving baseline model for reference...")
    baseline_sol = solve_baseline(inst, output_flag=0)
    
    if baseline_sol.total_co2 is None or baseline_sol.total_water is None:
        print("ERROR: Baseline solution is invalid. Cannot set caps.")
        return
    
    # Set caps as percentage of baseline
    # Note: 75% CO₂ cap is infeasible for this instance (baseline is already CO₂-efficient)
    # Using 80% as the closest feasible value to 75%
    alpha_co2 = 0.80  # 80% of baseline CO₂ (75% was infeasible)
    alpha_w = 1.0  # 100% of baseline water
    gamma_co2 = alpha_co2 * baseline_sol.total_co2
    gamma_w = alpha_w * baseline_sol.total_water
    
    print(f"\nSetting caps:")
    print(f"  CO₂ cap: {gamma_co2:.2f} ({alpha_co2*100}% of baseline {baseline_sol.total_co2:.2f})")
    print(f"  Water cap: {gamma_w:.2f} ({alpha_w*100}% of baseline {baseline_sol.total_water:.2f})")
    
    # Solve capped model
    print("\nSolving capped-impact model...")
    sol = solve_capped_impact(
        inst,
        gamma_co2=gamma_co2,
        gamma_w=gamma_w,
        output_flag=1
    )
    
    # Print results
    print("\n" + "="*60)
    print("CAPPED-IMPACT SOLUTION RESULTS")
    print("="*60)
    print(f"Status: {sol.status}")
    print(f"Objective: {sol.obj}")
    print(f"Total Cost: {sol.total_cost}")
    print(f"Total Latency Proxy: {sol.total_latency_proxy}")
    print(f"Total CO₂: {sol.total_co2} (cap: {gamma_co2:.2f})")
    print(f"Total Water: {sol.total_water} (cap: {gamma_w:.2f})")
    
    if sol.total_co2:
        co2_util = (sol.total_co2 / gamma_co2 * 100) if gamma_co2 > 0 else 0
        print(f"CO₂ cap utilization: {co2_util:.1f}%")
    if sol.total_water:
        water_util = (sol.total_water / gamma_w * 100) if gamma_w > 0 else 0
        print(f"Water cap utilization: {water_util:.1f}%")
    
    opened_sites = [i for i in inst.I if sol.x.get(i, 0) > 0.5]
    print(f"\nOpened Sites ({len(opened_sites)}): {opened_sites}")
    
    # Compare with baseline
    if baseline_sol.total_cost:
        cost_increase = ((sol.total_cost - baseline_sol.total_cost) / baseline_sol.total_cost * 100) if sol.total_cost else 0
        print(f"\nCost increase vs baseline: {cost_increase:.2f}%")
    
    # Save results to CSV
    results_path = Path("results/runs.csv")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    result_dict = solution_to_dict(
        sol,
        "capped_impact",
        gamma_co2=gamma_co2,
        gamma_w=gamma_w,
        alpha=alpha_co2  # Store CO₂ cap percentage
    )
    df = pd.DataFrame([result_dict])
    
    # Append to existing CSV or create new
    if results_path.exists():
        existing_df = pd.read_csv(results_path)
        df = pd.concat([existing_df, df], ignore_index=True)
    
    df.to_csv(results_path, index=False)
    print(f"\nSaved results to {results_path}")
    
    # Save detailed solution to JSON
    solution_path = Path("results/capped_solution.json")
    solution_dict = {
        "status": sol.status,
        "obj": sol.obj,
        "x": sol.x,
        "y": {f"{i},{r}": v for (i, r), v in sol.y.items()},
        "total_cost": sol.total_cost,
        "total_latency_proxy": sol.total_latency_proxy,
        "total_co2": sol.total_co2,
        "total_water": sol.total_water,
        "gamma_co2": gamma_co2,
        "gamma_w": gamma_w,
    }
    with open(solution_path, "w") as f:
        json.dump(solution_dict, f, indent=2)
    print(f"Saved detailed solution to {solution_path}")


if __name__ == "__main__":
    main()

