#!/usr/bin/env python3
"""Run baseline CFLP model and save results."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import make_toy_instance, solve_baseline
from src.utils import save_instance, solution_to_dict, FIXED_SITES
import pandas as pd
import json


def main():
    # Generate or load instance
    print("Generating toy instance...")
    inst = make_toy_instance(n_sites=10, n_regions=8, seed=3, phi=10.0)
    
    # Save instance for reproducibility
    instance_path = Path("data/toy_instance.json")
    instance_path.parent.mkdir(parents=True, exist_ok=True)
    save_instance(inst, str(instance_path))
    print(f"Saved instance to {instance_path}")
    
    # Solve baseline
    print("\nSolving baseline model...")
    sol = solve_baseline(inst, output_flag=1, fixed_sites=FIXED_SITES)
    
    # Print results
    print("\n" + "="*60)
    print("BASELINE SOLUTION RESULTS")
    print("="*60)
    print(f"Status: {sol.status}")
    print(f"Objective: {sol.obj}")
    print(f"Total Cost: {sol.total_cost}")
    print(f"Total Latency Proxy: {sol.total_latency_proxy}")
    print(f"Total CO₂: {sol.total_co2}")
    print(f"Total Water: {sol.total_water}")
    
    opened_sites = [i for i in inst.I if sol.x.get(i, 0) > 0.5]
    print(f"\nOpened Sites ({len(opened_sites)}): {opened_sites}")
    
    # Save results to CSV
    results_path = Path("results/runs.csv")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    result_dict = solution_to_dict(sol, "baseline")
    df = pd.DataFrame([result_dict])
    
    # Append to existing CSV or create new
    if results_path.exists():
        existing_df = pd.read_csv(results_path)
        df = pd.concat([existing_df, df], ignore_index=True)
    
    df.to_csv(results_path, index=False)
    print(f"\nSaved results to {results_path}")
    
    # Save detailed solution to JSON
    solution_path = Path("results/baseline_solution.json")
    solution_dict = {
        "status": sol.status,
        "obj": sol.obj,
        "x": sol.x,
        "y": {f"{i},{r}": v for (i, r), v in sol.y.items()},
        "total_cost": sol.total_cost,
        "total_latency_proxy": sol.total_latency_proxy,
        "total_co2": sol.total_co2,
        "total_water": sol.total_water,
    }
    with open(solution_path, "w") as f:
        json.dump(solution_dict, f, indent=2)
    print(f"Saved detailed solution to {solution_path}")


if __name__ == "__main__":
    main()

