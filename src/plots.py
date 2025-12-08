"""Plotting functions for CFLP visualization."""
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from src.models.cflp import CFLPInstance, CFLPSolution, Arc


def extract_coordinates(inst: CFLPInstance, seed: int = 1) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    """
    Extract or regenerate 2D coordinates for sites and regions.
    Since the instance doesn't store coordinates, we regenerate them using the same seed.
    This assumes the instance was generated with make_toy_instance.
    """
    import random
    import math
    
    rng = random.Random(seed)
    
    # Regenerate site coordinates
    site_xy = {i: (rng.random(), rng.random()) for i in inst.I}
    
    # Regenerate region coordinates
    reg_xy = {r: (rng.random(), rng.random()) for r in inst.R}
    
    return site_xy, reg_xy


def plot_map(
    inst: CFLPInstance,
    sol: CFLPSolution,
    site_xy: Dict[str, Tuple[float, float]],
    reg_xy: Dict[str, Tuple[float, float]],
    output_path: str,
    seed: int = 1,
) -> None:
    """Plot a map showing sites, regions, and opened sites."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot all sites (closed)
    for i, (x, y) in site_xy.items():
        ax.scatter(x, y, c='lightgray', s=200, marker='s', edgecolors='black', linewidth=1, label='Site (closed)' if i == inst.I[0] else '')
    
    # Plot opened sites
    opened_sites = [i for i in inst.I if sol.x.get(i, 0) > 0.5]
    for i in opened_sites:
        x, y = site_xy[i]
        ax.scatter(x, y, c='green', s=300, marker='s', edgecolors='darkgreen', linewidth=2, label='Site (opened)' if i == opened_sites[0] else '')
        ax.text(x, y, i, ha='center', va='center', fontsize=8, fontweight='bold')
    
    # Plot regions
    for r, (x, y) in reg_xy.items():
        ax.scatter(x, y, c='blue', s=150, marker='o', edgecolors='darkblue', linewidth=1, alpha=0.7, label='Region' if r == inst.R[0] else '')
        ax.text(x + 0.02, y + 0.02, r, ha='left', va='bottom', fontsize=8)
    
    # Draw allocation flows (only for significant flows)
    for (i, r), flow in sol.y.items():
        if flow > 0.01 and i in site_xy and r in reg_xy:
            x1, y1 = site_xy[i]
            x2, y2 = reg_xy[r]
            ax.plot([x1, x2], [y1, y2], 'k--', alpha=0.2, linewidth=0.5)
    
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_eligibility_heatmap(
    inst: CFLPInstance,
    output_path: str,
) -> None:
    """Plot a heatmap showing which arcs (i,r) are eligible."""
    A = inst.eligibility_sets()
    
    # Create binary matrix
    matrix = []
    for i in inst.I:
        row = []
        for r in inst.R:
            row.append(1 if i in A[r] else 0)
        matrix.append(row)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    
    # Set ticks
    ax.set_xticks(range(len(inst.R)))
    ax.set_yticks(range(len(inst.I)))
    ax.set_xticklabels(inst.R, rotation=45, ha='right')
    ax.set_yticklabels(inst.I)
    
    # Add text annotations
    for i in range(len(inst.I)):
        for r in range(len(inst.R)):
            text = ax.text(r, i, matrix[i][r], ha="center", va="center", color="black", fontsize=8)
    
    ax.set_xlabel('Regions', fontsize=12)
    ax.set_ylabel('Sites', fontsize=12)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Eligible (1) / Not Eligible (0)', rotation=270, labelpad=20)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_tradeoff_curves(
    scalarized_results: List[Tuple[float, float, float, float, float, float]],
    output_dir: str,
) -> None:
    """
    Plot trade-off curves from scalarized scan results.
    Input: list of (lambda_c, lambda_w, obj, total_cost, total_co2, total_water)
    """
    if not scalarized_results:
        return
    
    # Extract data
    costs = [r[3] for r in scalarized_results if r[3] is not None and not np.isnan(r[3])]
    co2s = [r[4] for r in scalarized_results if r[4] is not None and not np.isnan(r[4])]
    waters = [r[5] for r in scalarized_results if r[5] is not None and not np.isnan(r[5])]
    
    if not costs:
        print("Warning: No valid data for trade-off curves")
        return
    
    # Cost vs CO2
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(co2s, costs, c=range(len(costs)), cmap='viridis', s=100, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Total CO₂ (kgCO₂e)', fontsize=12)
    ax.set_ylabel('Total Cost', fontsize=12)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Solution Index')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_tradeoff_cost_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Cost vs Water
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(waters, costs, c=range(len(costs)), cmap='viridis', s=100, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Total Water (liters)', fontsize=12)
    ax.set_ylabel('Total Cost', fontsize=12)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Solution Index')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_tradeoff_cost_water.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_kpi_bars(
    baseline_sol: CFLPSolution,
    capped_sol: Optional[CFLPSolution],
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot separate bar charts for each KPI comparing model variants."""
    variants = ["Baseline"]
    costs = [baseline_sol.total_cost or 0]
    co2s = [baseline_sol.total_co2 or 0]
    waters = [baseline_sol.total_water or 0]
    
    if capped_sol and capped_sol.total_cost is not None:
        variants.append("Capped")
        costs.append(capped_sol.total_cost)
        co2s.append(capped_sol.total_co2 or 0)
        waters.append(capped_sol.total_water or 0)
    
    if scalarized_sol and scalarized_sol.total_cost is not None:
        variants.append("Scalarized")
        costs.append(scalarized_sol.total_cost)
        co2s.append(scalarized_sol.total_co2 or 0)
        waters.append(scalarized_sol.total_water or 0)
    
    x = np.arange(len(variants))
    width = 0.6
    
    # Normalize for comparison (show as percentage of baseline)
    baseline_cost = costs[0] if costs[0] > 0 else 1
    baseline_co2 = co2s[0] if co2s[0] > 0 else 1
    baseline_water = waters[0] if waters[0] > 0 else 1
    
    costs_norm = [c / baseline_cost * 100 for c in costs]
    co2s_norm = [c / baseline_co2 * 100 for c in co2s]
    waters_norm = [w / baseline_water * 100 for w in waters]
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Cost bar chart
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(x, costs_norm, width, label='Cost', color='blue', alpha=0.7)
    ax.set_ylabel('Cost (% of Baseline)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(variants)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_kpi_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # CO2 bar chart
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(x, co2s_norm, width, label='CO₂', color='red', alpha=0.7)
    ax.set_ylabel('CO₂ (% of Baseline)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(variants)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_kpi_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water bar chart
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(x, waters_norm, width, label='Water', color='cyan', alpha=0.7)
    ax.set_ylabel('Water (% of Baseline)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(variants)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_kpi_water.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_all_sites(
    inst: CFLPInstance,
    site_xy: Dict[str, Tuple[float, float]],
    output_path: str,
) -> None:
    """Plot all possible site locations as grey squares."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot all sites as grey squares
    for i, (x, y) in site_xy.items():
        ax.scatter(x, y, c='grey', s=300, marker='s', edgecolors='black', linewidth=1.5, alpha=0.7)
        ax.text(x, y, i, ha='center', va='center', fontsize=10, fontweight='bold', color='white')
    
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_baseline_selections(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    site_xy: Dict[str, Tuple[float, float]],
    output_path: str,
) -> None:
    """Plot baseline selected sites in red, others in grey."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Get opened sites
    opened_sites = [i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5]
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        if i in opened_sites:
            # Selected sites in red
            ax.scatter(x, y, c='red', s=400, marker='s', edgecolors='darkred', linewidth=2, alpha=0.8)
            ax.text(x, y, i, ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        else:
            # Unselected sites in grey
            ax.scatter(x, y, c='grey', s=300, marker='s', edgecolors='black', linewidth=1, alpha=0.5)
            ax.text(x, y, i, ha='center', va='center', fontsize=9, color='white', alpha=0.7)
    
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_capped_selections(
    inst: CFLPInstance,
    capped_sol: CFLPSolution,
    site_xy: Dict[str, Tuple[float, float]],
    output_path: str,
) -> None:
    """Plot capped model selected sites in blue, others in grey."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Get opened sites
    opened_sites = [i for i in inst.I if capped_sol.x.get(i, 0) > 0.5]
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        if i in opened_sites:
            # Selected sites in blue
            ax.scatter(x, y, c='blue', s=400, marker='s', edgecolors='darkblue', linewidth=2, alpha=0.8)
            ax.text(x, y, i, ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        else:
            # Unselected sites in grey
            ax.scatter(x, y, c='grey', s=300, marker='s', edgecolors='black', linewidth=1, alpha=0.5)
            ax.text(x, y, i, ha='center', va='center', fontsize=9, color='white', alpha=0.7)
    
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()



def plot_side_by_side_maps(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    site_xy: Dict[str, Tuple[float, float]],
    reg_xy: Dict[str, Tuple[float, float]],
    output_dir: str,
) -> None:
    """Plot separate baseline and sustainability-aware maps."""
    # Use existing plot_map function for each solution separately
    plot_map(inst, baseline_sol, site_xy, reg_xy, 
             f"{output_dir}/fig_map_baseline.png", seed=3)
    plot_map(inst, capped_sol, site_xy, reg_xy, 
             f"{output_dir}/fig_map_capped.png", seed=3)


def plot_sensitivity_analysis(
    sensitivity_results: List[Tuple[float, float, int]],
    output_dir: str,
) -> None:
    """
    Plot separate sensitivity analysis plots.
    Input: list of (cap_percentage, total_cost, num_sites_opened)
    """
    if not sensitivity_results:
        return
    
    cap_pcts = [r[0] for r in sensitivity_results]
    costs = [r[1] for r in sensitivity_results]
    num_sites = [r[2] for r in sensitivity_results]
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Cost vs cap percentage
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(cap_pcts, costs, 'o-', color='blue', linewidth=2, markersize=8)
    ax.set_xlabel('CO₂ Cap (% of Baseline)', fontsize=11)
    ax.set_ylabel('Total Cost', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()  # Show tightening from right to left
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_sensitivity_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Number of sites vs cap percentage
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(cap_pcts, num_sites, 's-', color='red', linewidth=2, markersize=8)
    ax.set_xlabel('CO₂ Cap (% of Baseline)', fontsize=11)
    ax.set_ylabel('Number of Sites Opened', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_sensitivity_sites.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_sustainability_heatmap(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """
    Plot separate heatmaps showing allocation intensity from regions to sites.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    for sol, suffix in [(baseline_sol, "baseline"), (capped_sol, "capped")]:
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Create allocation matrix
        matrix = []
        for i in inst.I:
            row = []
            for r in inst.R:
                flow = sol.y.get((i, r), 0.0)
                row.append(flow)
            matrix.append(row)
        
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', interpolation='nearest')
        
        # Set ticks
        ax.set_xticks(range(len(inst.R)))
        ax.set_yticks(range(len(inst.I)))
        ax.set_xticklabels(inst.R, rotation=45, ha='right')
        ax.set_yticklabels(inst.I)
        
        # Add text annotations for significant flows
        max_flow = max(max(row) for row in matrix) if matrix else 1
        for i_idx in range(len(inst.I)):
            for r_idx in range(len(inst.R)):
                flow = matrix[i_idx][r_idx]
                if flow > 0.1:  # Only show significant flows
                    text = ax.text(r_idx, i_idx, f'{flow:.1f}', 
                                 ha="center", va="center", 
                                 color="black" if flow < max_flow * 0.5 else "white",
                                 fontsize=7)
        
        ax.set_xlabel('Regions', fontsize=11)
        ax.set_ylabel('Sites', fontsize=11)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Allocation Flow', rotation=270, labelpad=15)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/fig_heatmap_{suffix}.png", dpi=150, bbox_inches='tight')
        plt.close()


def plot_cumulative_impact_curves(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """
    Plot separate cumulative impact curves for CO2 and water.
    """
    # Sort allocations by impact (for cumulative visualization)
    baseline_flows = [(baseline_sol.y.get((i, r), 0), inst.e_co2[i], inst.w[i]) 
                      for i in inst.I for r in inst.R 
                      if baseline_sol.y.get((i, r), 0) > 0.01]
    capped_flows = [(capped_sol.y.get((i, r), 0), inst.e_co2[i], inst.w[i]) 
                    for i in inst.I for r in inst.R 
                    if capped_sol.y.get((i, r), 0) > 0.01]
    
    # Sort by impact per unit (descending)
    baseline_flows.sort(key=lambda x: x[1], reverse=True)
    capped_flows.sort(key=lambda x: x[1], reverse=True)
    
    # Calculate cumulative
    total_demand = sum(inst.d.values())
    
    def compute_cumulative(flows):
        cum_demand = []
        cum_co2 = []
        cum_water = []
        current_demand = 0
        current_co2 = 0
        current_water = 0
        
        for flow, e_co2, w in flows:
            current_demand += flow
            current_co2 += flow * e_co2
            current_water += flow * w
            cum_demand.append(current_demand / total_demand * 100)
            cum_co2.append(current_co2)
            cum_water.append(current_water)
        
        return cum_demand, cum_co2, cum_water
    
    baseline_demand, baseline_co2, baseline_water = compute_cumulative(baseline_flows)
    capped_demand, capped_co2, capped_water = compute_cumulative(capped_flows)
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Cumulative CO2
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(baseline_demand, baseline_co2, 'b-', linewidth=2, label='Baseline', alpha=0.7)
    ax.plot(capped_demand, capped_co2, 'r--', linewidth=2, label='Sustainability-aware', alpha=0.7)
    ax.set_xlabel('Cumulative Demand (%)', fontsize=11)
    ax.set_ylabel('Cumulative CO₂ (kgCO₂e)', fontsize=11)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cumulative_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Cumulative Water
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(baseline_demand, baseline_water, 'b-', linewidth=2, label='Baseline', alpha=0.7)
    ax.plot(capped_demand, capped_water, 'r--', linewidth=2, label='Sustainability-aware', alpha=0.7)
    ax.set_xlabel('Cumulative Demand (%)', fontsize=11)
    ax.set_ylabel('Cumulative Water (liters)', fontsize=11)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cumulative_water.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_pareto_dual_axis(
    scalarized_results: List[Tuple[float, float, float, float, float, float]],
    output_dir: str,
) -> None:
    """
    Plot Pareto curves with dual y-axes: CO₂/Water on left, Cost on right.
    """
    if not scalarized_results:
        return
    
    # Extract data
    costs = [r[3] for r in scalarized_results if r[3] is not None and not np.isnan(r[3])]
    co2s = [r[4] for r in scalarized_results if r[4] is not None and not np.isnan(r[4])]
    waters = [r[5] for r in scalarized_results if r[5] is not None and not np.isnan(r[5])]
    
    if not costs:
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # CO₂ vs Cost with dual axes
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    
    # Sort by CO2 for better visualization
    sorted_data = sorted(zip(co2s, costs), key=lambda x: x[0])
    co2s_sorted, costs_sorted = zip(*sorted_data) if sorted_data else ([], [])
    
    line1 = ax1.plot(co2s_sorted, costs_sorted, 'b-o', linewidth=2, markersize=6, label='Cost', alpha=0.7)
    ax1.set_xlabel('Total CO₂ (kgCO₂e)', fontsize=11)
    ax1.set_ylabel('Total Cost', fontsize=11, color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.grid(True, alpha=0.3)
    
    # CO2 on right axis
    line2 = ax2.plot(co2s_sorted, co2s_sorted, 'r--', linewidth=2, label='CO₂', alpha=0.7)
    ax2.set_ylabel('Total CO₂ (kgCO₂e)', fontsize=11, color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_pareto_co2_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water vs Cost with dual axes
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    
    # Sort by water for better visualization
    sorted_data = sorted(zip(waters, costs), key=lambda x: x[0])
    waters_sorted, costs_sorted = zip(*sorted_data) if sorted_data else ([], [])
    
    line1 = ax1.plot(waters_sorted, costs_sorted, 'b-o', linewidth=2, markersize=6, label='Cost', alpha=0.7)
    ax1.set_xlabel('Total Water (liters)', fontsize=11)
    ax1.set_ylabel('Total Cost', fontsize=11, color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.grid(True, alpha=0.3)
    
    # Water on right axis
    line2 = ax2.plot(waters_sorted, waters_sorted, 'g--', linewidth=2, label='Water', alpha=0.7)
    ax2.set_ylabel('Total Water (liters)', fontsize=11, color='g')
    ax2.tick_params(axis='y', labelcolor='g')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_pareto_water_cost.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_objective_breakdown_stacked(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """
    Plot stacked bar chart showing objective function breakdown by terms.
    One bar for baseline and one for capped model.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Calculate baseline objective breakdown
    baseline_fixed = sum((inst.F[i] + inst.O[i]) * baseline_sol.x.get(i, 0) for i in inst.I)
    baseline_latency = inst.phi * (baseline_sol.total_latency_proxy or 0)
    baseline_co2_term = 0  # No penalty in baseline
    baseline_water_term = 0  # No penalty in baseline
    
    # Calculate capped objective breakdown (same structure, no penalties in objective)
    capped_fixed = sum((inst.F[i] + inst.O[i]) * capped_sol.x.get(i, 0) for i in inst.I)
    capped_latency = inst.phi * (capped_sol.total_latency_proxy or 0)
    capped_co2_term = 0  # Constraints, not in objective
    capped_water_term = 0  # Constraints, not in objective
    
    # Prepare data
    labels = ["Baseline", "Capped"]
    fixed_costs = [baseline_fixed, capped_fixed]
    latency_costs = [baseline_latency, capped_latency]
    co2_costs = [baseline_co2_term, capped_co2_term]
    water_costs = [baseline_water_term, capped_water_term]
    
    x = np.arange(len(labels))
    width = 0.6
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    p1 = ax.bar(x, fixed_costs, width, label='Fixed + Operating Cost', color='blue', alpha=0.7)
    p2 = ax.bar(x, latency_costs, width, bottom=fixed_costs, label='Latency Proxy', color='orange', alpha=0.7)
    p3 = ax.bar(x, co2_costs, width, bottom=np.array(fixed_costs) + np.array(latency_costs), 
                label='CO₂ Penalty', color='red', alpha=0.7)
    p4 = ax.bar(x, water_costs, width, 
                bottom=np.array(fixed_costs) + np.array(latency_costs) + np.array(co2_costs),
                label='Water Penalty', color='cyan', alpha=0.7)
    
    ax.set_ylabel('Objective Value', fontsize=11)
    ax.set_xlabel('Model Variant', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_objective_breakdown.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_site_utilization(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """Plot site capacity utilization for baseline and capped models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    sites = sorted(inst.I)
    baseline_util = []
    capped_util = []
    
    for i in sites:
        baseline_flow = sum(baseline_sol.y.get((i, r), 0) for r in inst.R)
        capped_flow = sum(capped_sol.y.get((i, r), 0) for r in inst.R)
        baseline_util.append((baseline_flow / inst.C[i] * 100) if inst.C[i] > 0 else 0)
        capped_util.append((capped_flow / inst.C[i] * 100) if inst.C[i] > 0 else 0)
    
    x = np.arange(len(sites))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, baseline_util, width, label='Baseline', color='blue', alpha=0.7)
    ax.bar(x + width/2, capped_util, width, label='Capped', color='red', alpha=0.7)
    
    ax.set_ylabel('Capacity Utilization (%)', fontsize=11)
    ax.set_xlabel('Site', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(sites)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.axhline(y=100, color='r', linestyle='--', alpha=0.5, label='Full Capacity')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_utilization.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_impact_per_region(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """Plot CO₂ and water impact per region for baseline vs capped."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    regions = sorted(inst.R)
    baseline_co2_per_region = []
    capped_co2_per_region = []
    baseline_water_per_region = []
    capped_water_per_region = []
    
    for r in regions:
        baseline_co2 = sum(baseline_sol.y.get((i, r), 0) * inst.e_co2[i] for i in inst.I)
        capped_co2 = sum(capped_sol.y.get((i, r), 0) * inst.e_co2[i] for i in inst.I)
        baseline_water = sum(baseline_sol.y.get((i, r), 0) * inst.w[i] for i in inst.I)
        capped_water = sum(capped_sol.y.get((i, r), 0) * inst.w[i] for i in inst.I)
        
        baseline_co2_per_region.append(baseline_co2)
        capped_co2_per_region.append(capped_co2)
        baseline_water_per_region.append(baseline_water)
        capped_water_per_region.append(capped_water)
    
    x = np.arange(len(regions))
    width = 0.35
    
    # CO2 per region
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, baseline_co2_per_region, width, label='Baseline', color='blue', alpha=0.7)
    ax.bar(x + width/2, capped_co2_per_region, width, label='Capped', color='red', alpha=0.7)
    ax.set_ylabel('CO₂ (kgCO₂e)', fontsize=11)
    ax.set_xlabel('Region', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(regions)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_co2_per_region.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water per region
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, baseline_water_per_region, width, label='Baseline', color='blue', alpha=0.7)
    ax.bar(x + width/2, capped_water_per_region, width, label='Capped', color='red', alpha=0.7)
    ax.set_ylabel('Water (liters)', fontsize=11)
    ax.set_xlabel('Region', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(regions)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_water_per_region.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_cost_breakdown_by_site(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """Plot cost breakdown by site (fixed + operating) for opened sites."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    baseline_sites = [i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5]
    capped_sites = [i for i in inst.I if capped_sol.x.get(i, 0) > 0.5]
    
    all_sites = sorted(set(baseline_sites + capped_sites))
    
    baseline_costs = [(inst.F[i] + inst.O[i]) if i in baseline_sites else 0 for i in all_sites]
    capped_costs = [(inst.F[i] + inst.O[i]) if i in capped_sites else 0 for i in all_sites]
    
    x = np.arange(len(all_sites))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, baseline_costs, width, label='Baseline', color='blue', alpha=0.7)
    ax.bar(x + width/2, capped_costs, width, label='Capped', color='red', alpha=0.7)
    
    ax.set_ylabel('Site Cost (Fixed + Operating)', fontsize=11)
    ax.set_xlabel('Site', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(all_sites)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cost_by_site.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_site_selection_comparison(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """Plot which sites are selected in baseline vs capped models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    baseline_selected = set(i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5)
    capped_selected = set(i for i in inst.I if capped_sol.x.get(i, 0) > 0.5)
    
    # Create matrix: rows = sites, cols = models
    sites = sorted(inst.I)
    models = ["Baseline", "Capped"]
    
    matrix = []
    for i in sites:
        row = [
            1 if i in baseline_selected else 0,
            1 if i in capped_selected else 0
        ]
        matrix.append(row)
    
    fig, ax = plt.subplots(figsize=(6, 8))
    im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    
    ax.set_xticks(range(len(models)))
    ax.set_yticks(range(len(sites)))
    ax.set_xticklabels(models)
    ax.set_yticklabels(sites)
    
    for i in range(len(sites)):
        for j in range(len(models)):
            text = ax.text(j, i, matrix[i][j], ha="center", va="center", color="black", fontsize=10)
    
    ax.set_xlabel('Model', fontsize=11)
    ax.set_ylabel('Site', fontsize=11)
    
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Selected (1) / Not Selected (0)', rotation=270, labelpad=20)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_selection_matrix.png", dpi=150, bbox_inches='tight')
    plt.close()
