#!/usr/bin/env python3
"""Run scalarized CFLP model scan over a grid of lambda values."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import make_toy_instance, pareto_scan_scalarized, solve_scalarized, CFLPSolution
from src.utils import save_instance, solution_to_dict, load_instance, EXISTING_SITES
import pandas as pd
import json
import itertools


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
    
    # Define lambda grid (expanded as per requirements)
    lambda_c_values = [0, 1, 5, 10, 25, 50, 100]
    lambda_w_values = [0, 1, 5, 10, 25, 50, 100]
    lambda_grid = list(itertools.product(lambda_c_values, lambda_w_values))
    
    print(f"\nRunning scalarized scan over {len(lambda_grid)} lambda combinations...")
    print(f"Lambda_C values: {lambda_c_values}")
    print(f"Lambda_W values: {lambda_w_values}")
    
    # Run scan
    results = pareto_scan_scalarized(inst, lambda_grid, output_flag=0, existing_sites=EXISTING_SITES)
    
    # Prepare results for CSV
    results_list = []
    scalarized_results = []
    
    for (lc, lw), (obj, cost, co2, water) in zip(lambda_grid, results):
        # Solve again to get full solution for one representative point
        if lc == 10.0 and lw == 10.0:
            sol = solve_scalarized(inst, lambda_c=lc, lambda_w=lw, output_flag=0, existing_sites=EXISTING_SITES)
            scalarized_sol = sol
        else:
            scalarized_sol = None
        
        # Create a minimal solution object for CSV export
        sol_obj = CFLPSolution(
            status=2,  # GRB.OPTIMAL
            obj=obj,
            x={},
            y={},
            total_cost=cost,
            total_latency_proxy=None,
            total_co2=co2,
            total_water=water,
        )
        result_dict = solution_to_dict(
            sol_obj,
            "scalarized",
            lambda_c=lc,
            lambda_w=lw
        )
        results_list.append(result_dict)
        
        scalarized_results.append((lc, lw, obj, cost, co2, water))
    
    # Save results to CSV
    results_path = Path("results/runs.csv")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(results_list)
    
    # Append to existing CSV or create new
    if results_path.exists():
        existing_df = pd.read_csv(results_path)
        df = pd.concat([existing_df, df], ignore_index=True)
    else:
        df.to_csv(results_path, index=False)
    
    df.to_csv(results_path, index=False)
    print(f"\nSaved {len(results_list)} results to {results_path}")
    
    # Save scalarized results for plotting
    scalarized_path = Path("results/scalarized_scan.json")
    with open(scalarized_path, "w") as f:
        json.dump({
            "lambda_grid": lambda_grid,
            "results": scalarized_results
        }, f, indent=2)
    print(f"Saved scalarized scan data to {scalarized_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("SCALARIZED SCAN SUMMARY")
    print("="*60)
    print(f"Total solutions: {len(results)}")
    valid_results = [r for r in results if not (pd.isna(r[1]) or pd.isna(r[2]) or pd.isna(r[3]))]
    print(f"Valid solutions: {len(valid_results)}")
    
    if valid_results:
        costs = [r[1] for r in valid_results]
        co2s = [r[2] for r in valid_results]
        waters = [r[3] for r in valid_results]
        
        print(f"\nCost range: [{min(costs):.2f}, {max(costs):.2f}]")
        print(f"CO₂ range: [{min(co2s):.2f}, {max(co2s):.2f}]")
        print(f"Water range: [{min(waters):.2f}, {max(waters):.2f}]")


if __name__ == "__main__":
    main()

