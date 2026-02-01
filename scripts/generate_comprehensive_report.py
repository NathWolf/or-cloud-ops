#!/usr/bin/env python3
"""Generate comprehensive report: binding constraints, Pareto fronts, stability thresholds."""
import sys
from pathlib import Path
import json
import pandas as pd
import itertools

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import CFLPInstance, solve_scalarized, CFLPSolution
from src.utils import load_instance, EXISTING_SITES
from src.analysis import (
    compute_binding_constraints,
    extract_pareto_front,
    compute_decision_stability,
    compute_kpis,
)


def load_solution_from_json(filepath: str) -> CFLPSolution:
    """Load a solution from JSON and convert to CFLPSolution object."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    # Convert y dictionary keys from strings to tuples
    y_dict = {}
    for k, v in data.get("y", {}).items():
        if isinstance(k, str):
            i, r = k.split(",")
            y_dict[(i, r)] = v
        else:
            y_dict[k] = v
    
    return CFLPSolution(
        status=data.get("status", 0),
        obj=data.get("obj"),
        x=data.get("x", {}),
        y=y_dict,
        total_cost=data.get("total_cost"),
        total_latency_proxy=data.get("total_latency_proxy"),
        total_co2=data.get("total_co2"),
        total_water=data.get("total_water"),
    )


def generate_binding_constraints_table(inst: CFLPInstance) -> pd.DataFrame:
    """Generate binding constraints/slack table for all model variants."""
    results = []
    
    # Load solutions
    baseline_path = Path("results/baseline_solution.json")
    capped_90_path = Path("results/capped_solution_90pct.json")
    capped_80_path = Path("results/capped_solution_80pct.json")
    
    # Baseline
    if baseline_path.exists():
        baseline_sol = load_solution_from_json(str(baseline_path))
        binding = compute_binding_constraints(inst, baseline_sol)
        kpis = compute_kpis(inst, baseline_sol, EXISTING_SITES)
        
        results.append({
            "Model Variant": "Baseline",
            "CO₂ Slack": "N/A",
            "Water Slack": "N/A",
            "CO₂ Utilization (%)": "N/A",
            "Water Utilization (%)": "N/A",
            "Binding Capacity Sites": binding.num_binding_capacity,
            "Regions Near Boundary": binding.num_regions_near_boundary,
            "Max Utilization (%)": f"{kpis['max_utilization']:.1f}",
            "New Sites Opened": kpis['num_new_sites'],
        })
    
    # Capped 90%
    if capped_90_path.exists():
        capped_90_sol = load_solution_from_json(str(capped_90_path))
        # Load gamma values from JSON
        with open(capped_90_path, "r") as f:
            capped_90_data = json.load(f)
        gamma_co2 = capped_90_data.get("gamma_co2")
        gamma_w = capped_90_data.get("gamma_w")
        
        binding = compute_binding_constraints(inst, capped_90_sol, gamma_co2, gamma_w)
        kpis = compute_kpis(inst, capped_90_sol, EXISTING_SITES)
        
        results.append({
            "Model Variant": "Capped (90%)",
            "CO₂ Slack": f"{binding.co2_slack:.2f}" if binding.co2_slack is not None else "N/A",
            "Water Slack": f"{binding.water_slack:.2f}" if binding.water_slack is not None else "N/A",
            "CO₂ Utilization (%)": f"{binding.co2_utilization:.1f}" if binding.co2_utilization is not None else "N/A",
            "Water Utilization (%)": f"{binding.water_utilization:.1f}" if binding.water_utilization is not None else "N/A",
            "Binding Capacity Sites": binding.num_binding_capacity,
            "Regions Near Boundary": binding.num_regions_near_boundary,
            "Max Utilization (%)": f"{kpis['max_utilization']:.1f}",
            "New Sites Opened": kpis['num_new_sites'],
        })
    
    # Capped 80%
    if capped_80_path.exists():
        capped_80_sol = load_solution_from_json(str(capped_80_path))
        # Load gamma values from JSON
        with open(capped_80_path, "r") as f:
            capped_80_data = json.load(f)
        gamma_co2 = capped_80_data.get("gamma_co2")
        gamma_w = capped_80_data.get("gamma_w")
        
        binding = compute_binding_constraints(inst, capped_80_sol, gamma_co2, gamma_w)
        kpis = compute_kpis(inst, capped_80_sol, EXISTING_SITES)
        
        results.append({
            "Model Variant": "Capped (80%)",
            "CO₂ Slack": f"{binding.co2_slack:.2f}" if binding.co2_slack is not None else "N/A",
            "Water Slack": f"{binding.water_slack:.2f}" if binding.water_slack is not None else "N/A",
            "CO₂ Utilization (%)": f"{binding.co2_utilization:.1f}" if binding.co2_utilization is not None else "N/A",
            "Water Utilization (%)": f"{binding.water_utilization:.1f}" if binding.water_utilization is not None else "N/A",
            "Binding Capacity Sites": binding.num_binding_capacity,
            "Regions Near Boundary": binding.num_regions_near_boundary,
            "Max Utilization (%)": f"{kpis['max_utilization']:.1f}",
            "New Sites Opened": kpis['num_new_sites'],
        })
    
    return pd.DataFrame(results)


def generate_pareto_fronts() -> dict:
    """Extract Pareto fronts from scalarized scan results."""
    scalarized_path = Path("results/scalarized_scan.json")
    if not scalarized_path.exists():
        return {}
    
    with open(scalarized_path, "r") as f:
        data = json.load(f)
    
    lambda_grid = data["lambda_grid"]
    results = data["results"]  # List of [lc, lw, obj, cost, co2, water]
    
    # Extract Pareto front for Cost vs CO2
    # Results format: [lambda_c, lambda_w, obj, cost, co2, water]
    # So cost is at index 3, co2 at index 4
    pareto_co2 = extract_pareto_front(results, objective1_idx=3, objective2_idx=4)
    
    # Extract Pareto front for Cost vs Water
    # cost is at index 3, water at index 5
    pareto_water = extract_pareto_front(results, objective1_idx=3, objective2_idx=5)
    
    return {
        "pareto_co2": pareto_co2,
        "pareto_water": pareto_water,
        "all_results": results,
        "lambda_grid": lambda_grid,
    }


def generate_stability_table(inst: CFLPInstance) -> pd.DataFrame:
    """Generate decision stability thresholds table."""
    scalarized_path = Path("results/scalarized_scan.json")
    if not scalarized_path.exists():
        return pd.DataFrame()
    
    with open(scalarized_path, "r") as f:
        data = json.load(f)
    
    lambda_grid = data["lambda_grid"]
    
    # Re-solve to get full solutions (we need x values)
    solutions = []
    for lc, lw in lambda_grid:
        sol = solve_scalarized(inst, lambda_c=lc, lambda_w=lw, output_flag=0, existing_sites=EXISTING_SITES)
        solutions.append(sol)
    
    # Compute stability
    stability = compute_decision_stability(inst, lambda_grid, solutions)
    
    # Format as table
    rows = []
    for sig, info in stability.items():
        sites_list = sorted(info["sites"])
        sites_str = "{" + ",".join(sites_list) + "}"
        
        # Find lambda range
        lambda_region = info["lambda_region"]
        if lambda_region:
            lc_vals = [lc for lc, lw in lambda_region]
            lw_vals = [lw for lc, lw in lambda_region]
            lc_range = f"[{min(lc_vals):.0f}, {max(lc_vals):.0f}]"
            lw_range = f"[{min(lw_vals):.0f}, {max(lw_vals):.0f}]"
        else:
            lc_range = "N/A"
            lw_range = "N/A"
        
        rows.append({
            "Plan": sites_str,
            "λ_C Range": lc_range,
            "λ_W Range": lw_range,
            "First Threshold": f"{info.get('first_threshold', 'N/A'):.0f}" if info.get('first_threshold') is not None else "N/A",
        })
    
    return pd.DataFrame(rows)


def main():
    print("Generating comprehensive report...")
    
    # Load instance
    instance_path = Path("data/toy_instance.json")
    if not instance_path.exists():
        print(f"ERROR: Instance file not found at {instance_path}")
        return
    
    inst = load_instance(str(instance_path))
    
    tables_dir = Path("results/tables")
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Binding constraints table
    print("\nGenerating binding constraints table...")
    binding_table = generate_binding_constraints_table(inst)
    binding_table.to_csv(tables_dir / "table_binding_constraints.csv", index=False)
    binding_table.to_latex(tables_dir / "table_binding_constraints.tex", index=False, float_format="%.2f")
    print(binding_table.to_string(index=False))
    
    # 2. Pareto fronts
    print("\nExtracting Pareto fronts...")
    pareto_data = generate_pareto_fronts()
    if pareto_data:
        pareto_path = Path("results/pareto_fronts.json")
        with open(pareto_path, "w") as f:
            json.dump(pareto_data, f, indent=2)
        print(f"Found {len(pareto_data['pareto_co2'])} Pareto points for Cost vs CO₂")
        print(f"Found {len(pareto_data['pareto_water'])} Pareto points for Cost vs Water")
    
    # 3. Stability table
    print("\nGenerating stability thresholds table...")
    stability_table = generate_stability_table(inst)
    if not stability_table.empty:
        stability_table.to_csv(tables_dir / "table_stability_thresholds.csv", index=False)
        stability_table.to_latex(tables_dir / "table_stability_thresholds.tex", index=False)
        print(stability_table.to_string(index=False))
    
    # 4. Scenario sensitivity (if available)
    scenario_path = Path("results/scenario_sensitivity.csv")
    if scenario_path.exists():
        print("\nScenario sensitivity table:")
        scenario_df = pd.read_csv(scenario_path)
        print(scenario_df.to_string(index=False))
    
    print("\n" + "="*60)
    print("Comprehensive report generation complete!")
    print(f"All tables saved to: {tables_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

