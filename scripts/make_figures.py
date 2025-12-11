#!/usr/bin/env python3
"""Generate all figures from saved results."""
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import CFLPInstance, CFLPSolution
from src.utils import load_instance, FIXED_SITES
import pandas as pd
from src.plots import (
    extract_coordinates,
    plot_map,
    plot_eligibility_heatmap,
    plot_tradeoff_curves,
    plot_kpi_bars,
    plot_all_sites,
    plot_baseline_selections,
    plot_capped_selections,
    plot_side_by_side_maps,
    plot_sensitivity_analysis,
    plot_sustainability_heatmap,
    plot_cumulative_impact_curves,
    plot_pareto_dual_axis,
    plot_objective_breakdown_stacked,
    plot_site_utilization,
    plot_impact_per_region,
    plot_impact_per_site,
    plot_cost_breakdown_by_site,
    plot_site_selection_comparison,
    plot_site_flows,
    plot_lambda_heatmaps,
    plot_scalarized_selections,
)


def load_solution(filepath: str) -> CFLPSolution:
    """Load a solution from JSON."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    # Reconstruct y dictionary
    y = {}
    for key, value in data.get("y", {}).items():
        i, r = key.split(",")
        y[(i, r)] = value
    
    return CFLPSolution(
        status=data["status"],
        obj=data.get("obj"),
        x=data.get("x", {}),
        y=y,
        total_cost=data.get("total_cost"),
        total_latency_proxy=data.get("total_latency_proxy"),
        total_co2=data.get("total_co2"),
        total_water=data.get("total_water"),
    )


def main():
    print("Generating figures...")
    
    # Load instance
    instance_path = Path("data/toy_instance.json")
    if not instance_path.exists():
        print(f"ERROR: Instance file not found at {instance_path}")
        print("Please run run_baseline.py first to generate the instance.")
        return
    
    inst = load_instance(str(instance_path))
    print(f"Loaded instance: {len(inst.I)} sites, {len(inst.R)} regions")
    
    # Extract coordinates (using seed=3 to match generation)
    site_xy, reg_xy = extract_coordinates(inst, seed=3)
    
    # Load solutions
    baseline_path = Path("results/baseline_solution.json")
    capped_path = Path("results/capped_solution.json")
    scalarized_path = Path("results/scalarized_scan.json")
    
    baseline_sol = None
    capped_sol = None
    scalarized_sol = None
    
    if baseline_path.exists():
        print("Loading baseline solution...")
        baseline_sol = load_solution(str(baseline_path))
    else:
        print("WARNING: Baseline solution not found. Run run_baseline.py first.")
    
    capped_alpha = None
    if capped_path.exists():
        print("Loading capped solution...")
        capped_sol = load_solution(str(capped_path))
        # Try to get alpha from runs.csv (get the most recent row)
        try:
            runs_df = pd.read_csv("results/runs.csv")
            capped_rows = runs_df[runs_df["model_variant"] == "capped_impact"]
            if not capped_rows.empty and "alpha" in capped_rows.columns:
                # Get the last row (most recent)
                capped_alpha = capped_rows.iloc[-1]["alpha"]
                if pd.notna(capped_alpha):
                    capped_alpha = int(capped_alpha * 100)  # Convert to percentage
        except:
            # Default to 80 if not found
            capped_alpha = 80
    else:
        print("WARNING: Capped solution not found. Run run_capped.py first.")
    
    # Always load scalarized solution (lambda=50,50) - generate it if needed
    print("Loading scalarized solution (lambda=50,50)...")
    from src.models.cflp import solve_scalarized
    scalarized_sol = solve_scalarized(inst, lambda_c=50.0, lambda_w=50.0, output_flag=0, fixed_sites=FIXED_SITES)
    if scalarized_sol.status == 2:
        print(f"   Scalarized solution loaded successfully (status: optimal)")
    else:
        print(f"   WARNING: Scalarized solution status: {scalarized_sol.status}")
    
    # Generate figures
    figures_dir = Path("results/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Map plot (baseline)
    if baseline_sol:
        print("\n1. Generating map plot...")
        plot_map(inst, baseline_sol, site_xy, reg_xy, 
                str(figures_dir / "fig_map.png"), seed=3)
        print(f"   Saved to {figures_dir / 'fig_map.png'}")
    
    # 2. Eligibility heatmap - DISABLED
    # print("\n2. Generating eligibility heatmap...")
    # plot_eligibility_heatmap(inst, str(figures_dir / "fig_eligibility.png"))
    # print(f"   Saved to {figures_dir / 'fig_eligibility.png'}")
    
    # 3. Trade-off curves - DISABLED
    # if scalarized_path.exists():
    #     print("\n3. Generating trade-off curves...")
    #     with open(scalarized_path, "r") as f:
    #         scan_data = json.load(f)
    #     
    #     scalarized_results = scan_data["results"]
    #     plot_tradeoff_curves(scalarized_results, str(figures_dir))
    #     print(f"   Saved trade-off curves to {figures_dir}")
    # else:
    #     print("\n3. WARNING: Scalarized scan data not found. Run run_scalarized_scan.py first.")
    
    # 4. KPI bar charts (separate files)
    if baseline_sol:
        print("\n4. Generating KPI bar charts...")
        # scalarized_sol is already loaded above, use it
        plot_kpi_bars(baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_kpi_cost.png'}, fig_kpi_co2.png, fig_kpi_water.png")
    
    # 5. All sites plot (grey squares)
    print("\n5. Generating all sites plot...")
    plot_all_sites(inst, site_xy, str(figures_dir / "fig_all_sites.png"))
    print(f"   Saved to {figures_dir / 'fig_all_sites.png'}")
    
    # 6. Baseline selections (red)
    if baseline_sol:
        print("\n6. Generating baseline selections plot...")
        plot_baseline_selections(inst, baseline_sol, site_xy, str(figures_dir / "fig_baseline_selections.png"))
        print(f"   Saved to {figures_dir / 'fig_baseline_selections.png'}")
    
    # 7. Capped selections (blue)
    if capped_sol:
        print("\n7. Generating capped selections plot...")
        capped_pct = f"_{capped_alpha}pct" if capped_alpha else ""
        capped_filename = f"fig_capped_selections{capped_pct}.png"
        plot_capped_selections(inst, capped_sol, site_xy, str(figures_dir / capped_filename))
        print(f"   Saved to {figures_dir / capped_filename}")
    
    # 7b. Scalarized selections (green, lambda=50,50)
    if scalarized_sol:
        print("\n7b. Generating scalarized selections plot (lambda=50,50)...")
        scalarized_filename = "fig_scalarized_selections_50_50.png"
        plot_scalarized_selections(inst, scalarized_sol, site_xy, 50.0, 50.0, 
                                   str(figures_dir / scalarized_filename))
        print(f"   Saved to {figures_dir / scalarized_filename}")
    
    # 8. Separate baseline and capped maps
    if baseline_sol and capped_sol:
        print("\n8. Generating separate baseline and capped maps...")
        plot_side_by_side_maps(inst, baseline_sol, capped_sol, site_xy, reg_xy, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_map_baseline.png'} and fig_map_capped.png")
    
    # 9. Sensitivity analysis (separate files)
    sensitivity_path = Path("results/sensitivity_analysis.json")
    if sensitivity_path.exists():
        print("\n9. Generating sensitivity analysis plots...")
        with open(sensitivity_path, "r") as f:
            sens_data = json.load(f)
        plot_sensitivity_analysis(sens_data["results"], str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_sensitivity_cost.png'} and fig_sensitivity_sites.png")
    else:
        print("\n9. WARNING: Sensitivity analysis not found. Run run_sensitivity.py first.")
    
    # 10. Sustainability heatmaps (separate files) - DISABLED
    # if baseline_sol and capped_sol:
    #     print("\n10. Generating sustainability heatmaps...")
    #     plot_sustainability_heatmap(inst, baseline_sol, capped_sol, str(figures_dir))
    #     print(f"   Saved to {figures_dir / 'fig_heatmap_baseline.png'} and fig_heatmap_capped.png")
    
    # 11. Cumulative impact curves (separate files) - DISABLED
    # if baseline_sol and capped_sol:
    #     print("\n11. Generating cumulative impact curves...")
    #     plot_cumulative_impact_curves(inst, baseline_sol, capped_sol, str(figures_dir))
    #     print(f"   Saved to {figures_dir / 'fig_cumulative_co2.png'} and fig_cumulative_water.png")
    
    # 12. Pareto plots with dual axes
    scalarized_results_data = None
    lambda_grid_data = None
    if scalarized_path.exists():
        print("\n12. Generating Pareto plots with dual axes...")
        with open(scalarized_path, "r") as f:
            scan_data = json.load(f)
        scalarized_results_data = scan_data["results"]
        lambda_grid_data = scan_data["lambda_grid"]
        plot_pareto_dual_axis(scalarized_results_data, lambda_grid_data, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_pareto_co2_cost.png'} and fig_pareto_water_cost.png")
        
        # 12b. Lambda heatmaps
        print("\n12b. Generating lambda heatmaps...")
        plot_lambda_heatmaps(scalarized_results_data, lambda_grid_data, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_heatmap_cost.png'}, fig_heatmap_co2.png, fig_heatmap_water.png, fig_heatmap_objective.png")
    
    # 13. Objective function breakdown (stacked bars)
    if baseline_sol and capped_sol:
        print("\n13. Generating objective breakdown stacked bars...")
        plot_objective_breakdown_stacked(inst, baseline_sol, capped_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_objective_breakdown.png'}")
    
    # 14. Site utilization comparison
    if baseline_sol and capped_sol:
        print("\n14. Generating site utilization plot...")
        plot_site_utilization(inst, baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_site_utilization.png'}")
    
    # 15. Impact per region
    if baseline_sol and capped_sol:
        print("\n15. Generating impact per region plots...")
        plot_impact_per_region(inst, baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_co2_per_region.png'} and fig_water_per_region.png")
    
    # 15b. Impact per site
    if baseline_sol and capped_sol:
        print("\n15b. Generating impact per site plots...")
        plot_impact_per_site(inst, baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_co2_per_site.png'} and fig_water_per_site.png")
    
    # 16. Cost breakdown by site
    if baseline_sol and capped_sol:
        print("\n16. Generating cost breakdown by site...")
        plot_cost_breakdown_by_site(inst, baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_cost_by_site.png'}")
    
    # 18. Site flows comparison
    if baseline_sol and capped_sol:
        print("\n18. Generating site flows plot...")
        print(f"   Scalarized solution available: {scalarized_sol is not None}")
        if scalarized_sol:
            total_flow = sum(scalarized_sol.y.values())
            print(f"   Scalarized total flow: {total_flow:.2f}")
        plot_site_flows(inst, baseline_sol, capped_sol, scalarized_sol, str(figures_dir))
        print(f"   Saved to {figures_dir / 'fig_site_flows.png'}")
    
    # 17. Site selection comparison matrix - DISABLED
    # if baseline_sol and capped_sol:
    #     print("\n17. Generating site selection comparison matrix...")
    #     plot_site_selection_comparison(inst, baseline_sol, capped_sol, str(figures_dir))
    #     print(f"   Saved to {figures_dir / 'fig_site_selection_matrix.png'}")
    
    print("\n" + "="*60)
    print("Figure generation complete!")
    print(f"All figures saved to: {figures_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

