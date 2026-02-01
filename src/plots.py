"""Plotting functions for CFLP visualization."""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from src.models.cflp import CFLPInstance, CFLPSolution, Arc, build_baseline_model, add_usage_caps, set_scalarized_objective
from src.utils import get_site_label_mapping, EXISTING_SITES
import gurobipy as gp

# Configure matplotlib for LaTeX-style fonts (serif fonts without LaTeX)
matplotlib.rcParams['font.family'] = 'serif'
matplotlib.rcParams['font.serif'] = ['Computer Modern Roman', 'Times New Roman', 'DejaVu Serif', 'serif']
matplotlib.rcParams['mathtext.fontset'] = 'cm'  # Computer Modern for math
matplotlib.rcParams['mathtext.default'] = 'regular'
matplotlib.rcParams['font.size'] = 28
matplotlib.rcParams['text.usetex'] = False  # Don't use LaTeX, use mathtext instead
matplotlib.rcParams['axes.labelsize'] = 30
matplotlib.rcParams['axes.titlesize'] = 30
matplotlib.rcParams['xtick.labelsize'] = 28
matplotlib.rcParams['ytick.labelsize'] = 28
matplotlib.rcParams['legend.fontsize'] = 28
matplotlib.rcParams['figure.titlesize'] = 32

# Consistent color scheme for model variants
COLOR_BASELINE = 'blue'
COLOR_CAPPED = 'red'
COLOR_SCALARIZED = 'green'
COLOR_BASELINE_DARK = 'darkblue'
COLOR_CAPPED_DARK = 'darkred'
COLOR_SCALARIZED_DARK = 'darkgreen'

# Color for existing sites (C sites) - use orange/purple to distinguish from model variants
COLOR_EXISTING_SITE = 'orange'
COLOR_EXISTING_SITE_DARK = 'darkorange'


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
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Plot all sites (closed)
    for i, (x, y) in site_xy.items():
        label = site_to_label.get(i, i)
        is_existing = i in EXISTING_SITES
        marker = 'o' if is_existing else 's'
        color = COLOR_EXISTING_SITE if is_existing else 'lightgray'
        edge_color = COLOR_EXISTING_SITE_DARK if is_existing else 'black'
        ax.scatter(x, y, c=color, s=200, marker=marker, edgecolors=edge_color, linewidth=1, 
                  label='Site (closed)' if i == inst.I[0] else '')
    
    # Plot opened sites
    opened_sites = [i for i in inst.I if sol.x.get(i, 0) > 0.5]
    for i in opened_sites:
        x, y = site_xy[i]
        label = site_to_label.get(i, i)
        is_existing = i in EXISTING_SITES
        marker = 'o' if is_existing else 's'
        color = COLOR_EXISTING_SITE if is_existing else 'green'
        edge_color = COLOR_EXISTING_SITE_DARK if is_existing else 'darkgreen'
        ax.scatter(x, y, c=color, s=400, marker=marker, edgecolors=edge_color, linewidth=2, 
                  label='Site (opened)' if i == opened_sites[0] else '')
        ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold')
    
    # Plot regions
    for r, (x, y) in reg_xy.items():
        ax.scatter(x, y, c='blue', s=200, label='Region' if r == inst.R[0] else "", alpha=0.6, edgecolors='black')
        ax.text(x + 0.02, y + 0.02, r, ha='left', va='bottom', fontsize=26)
    
    # Draw allocation flows (only for significant flows)
    for (i, r), flow in sol.y.items():
        if flow > 0.01 and i in site_xy and r in reg_xy:
            x1, y1 = site_xy[i]
            x2, y2 = reg_xy[r]
            ax.plot([x1, x2], [y1, y2], 'k--', alpha=0.2, linewidth=0.5)
    
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
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
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Create binary matrix
    matrix = []
    site_labels = []
    for i in inst.I:
        row = []
        for r in inst.R:
            row.append(1 if i in A[r] else 0)
        matrix.append(row)
        site_labels.append(site_to_label.get(i, i))
    
    fig, ax = plt.subplots(figsize=(16, 10))
    im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    
    # Set ticks
    ax.set_xticks(range(len(inst.R)))
    ax.set_yticks(range(len(inst.I)))
    ax.set_xticklabels(inst.R, rotation=45, ha='right')
    ax.set_yticklabels(site_labels)
    
    # Add text annotations
    for i in range(len(inst.I)):
        for r in range(len(inst.R)):
            text = ax.text(r, i, matrix[i][r], ha="center", va="center", color="black", fontsize=26)
    
    ax.set_xlabel('Regions', fontsize=30)
    ax.set_ylabel('Sites', fontsize=30)
    
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
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(co2s, costs, c=range(len(costs)), cmap='viridis', s=200, alpha=0.7, edgecolors='black')
    ax.set_xlabel(r'Total CO$_2$ (kgCO$_2$e)')
    ax.set_ylabel('Total Cost')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Solution Index')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_tradeoff_cost_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Cost vs Water
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(waters, costs, c=range(len(costs)), cmap='viridis', s=200, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Total Water (liters)')
    ax.set_ylabel('Total Cost')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Solution Index')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_tradeoff_cost_water.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_pareto_fronts(
    pareto_co2: List[Tuple[float, float, float, float]],
    pareto_water: List[Tuple[float, float, float, float]],
    baseline_cost: Optional[float] = None,
    baseline_co2: Optional[float] = None,
    baseline_water: Optional[float] = None,
    capped_cost: Optional[float] = None,
    capped_co2: Optional[float] = None,
    capped_water: Optional[float] = None,
    output_dir: str = "results/figures",
) -> None:
    """
    Plot Pareto fronts with baseline and capped solutions marked.
    
    Args:
        pareto_co2: List of (obj, cost, co2, water) for Cost vs CO2 Pareto front
        pareto_water: List of (obj, cost, co2, water) for Cost vs Water Pareto front
        baseline_cost, baseline_co2, baseline_water: Baseline solution values
        capped_cost, capped_co2, capped_water: Capped solution values
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Cost vs CO2 Pareto front
    if pareto_co2:
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Plot all scalarized points (light gray)
        costs_all = [r[1] for r in pareto_co2]
        co2s_all = [r[2] for r in pareto_co2]
        ax.scatter(co2s_all, costs_all, c='lightgray', s=100, alpha=0.5, label='All solutions')
        
        # Highlight Pareto front
        costs_pareto = [r[1] for r in pareto_co2]
        co2s_pareto = [r[2] for r in pareto_co2]
        ax.plot(co2s_pareto, costs_pareto, 'b-o', linewidth=3, markersize=12, label='Pareto front', alpha=0.8)
        
        # Mark baseline
        if baseline_cost is not None and baseline_co2 is not None:
            ax.scatter(baseline_co2, baseline_cost, c=COLOR_BASELINE, s=400, marker='s', 
                      edgecolors='black', linewidth=2, label='Baseline', zorder=10)
        
        # Mark capped
        if capped_cost is not None and capped_co2 is not None:
            ax.scatter(capped_co2, capped_cost, c=COLOR_CAPPED, s=400, marker='^', 
                      edgecolors='black', linewidth=2, label='Capped (90%)', zorder=10)
        
        ax.set_xlabel(r'Total CO$_2$ (kgCO$_2$e)')
        ax.set_ylabel('Total Cost')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/fig_pareto_co2_cost.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    # Cost vs Water Pareto front
    if pareto_water:
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Plot all scalarized points (light gray)
        costs_all = [r[1] for r in pareto_water]
        waters_all = [r[3] for r in pareto_water]
        ax.scatter(waters_all, costs_all, c='lightgray', s=100, alpha=0.5, label='All solutions')
        
        # Highlight Pareto front
        costs_pareto = [r[1] for r in pareto_water]
        waters_pareto = [r[3] for r in pareto_water]
        ax.plot(waters_pareto, costs_pareto, 'b-o', linewidth=3, markersize=12, label='Pareto front', alpha=0.8)
        
        # Mark baseline
        if baseline_cost is not None and baseline_water is not None:
            ax.scatter(baseline_water, baseline_cost, c=COLOR_BASELINE, s=400, marker='s', 
                      edgecolors='black', linewidth=2, label='Baseline', zorder=10)
        
        # Mark capped
        if capped_cost is not None and capped_water is not None:
            ax.scatter(capped_water, capped_cost, c=COLOR_CAPPED, s=400, marker='^', 
                      edgecolors='black', linewidth=2, label='Capped (90%)', zorder=10)
        
        ax.set_xlabel('Total Water (liters)')
        ax.set_ylabel('Total Cost')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/fig_pareto_water_cost.png", dpi=150, bbox_inches='tight')
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
    width = 0.7
    
    # Normalize for comparison (show as percentage of baseline)
    baseline_cost = costs[0] if costs[0] > 0 else 1
    baseline_co2 = co2s[0] if co2s[0] > 0 else 1
    baseline_water = waters[0] if waters[0] > 0 else 1
    
    costs_norm = [c / baseline_cost * 100 for c in costs]
    co2s_norm = [c / baseline_co2 * 100 for c in co2s]
    waters_norm = [w / baseline_water * 100 for w in waters]
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Cost bar chart
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.bar(x, costs_norm, width, label='Cost', color='blue', alpha=0.7)
    ax.set_ylabel('Cost (% of Baseline)')
    ax.set_xticks(x)
    ax.set_xticklabels(variants)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_kpi_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # CO2 bar chart
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.bar(x, co2s_norm, width, label=r'CO$_2$', color='red', alpha=0.7)
    ax.set_ylabel(r'CO$_2$ (% of Baseline)')
    ax.set_xticks(x)
    ax.set_xticklabels(variants)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_kpi_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water bar chart
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.bar(x, waters_norm, width, label='Water', color='cyan', alpha=0.7)
    ax.set_ylabel('Water (% of Baseline)')
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
    """Plot all possible site locations: existing sites (C) as orange circles, potential sites (S) as grey squares."""
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        label = site_to_label.get(i, i)
        is_fixed = i in EXISTING_SITES
        
        if is_fixed:
            # Existing sites: orange circles
            ax.scatter(x, y, c=COLOR_EXISTING_SITE, s=300, marker='o', edgecolors=COLOR_EXISTING_SITE_DARK, linewidth=1.5, alpha=0.7)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        else:
            # Potential sites: grey squares
            ax.scatter(x, y, c='green', s=200, marker='s', edgecolors='black', linewidth=1.5, zorder=3)
            ax.text(x, y, label, ha='center', va='center', fontsize=28, fontweight='bold', color='white')
    
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
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
    """Plot baseline selected sites in blue, existing sites (C) in orange circles, others in grey."""
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Get opened sites
    opened_sites = [i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5]
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        label = site_to_label.get(i, i)
        is_fixed = i in EXISTING_SITES
        is_opened = i in opened_sites
        
        if is_fixed:
            # Existing sites: always show as orange circles
            ax.scatter(x, y, c=COLOR_EXISTING_SITE, s=2000, marker='o', edgecolors=COLOR_EXISTING_SITE_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        elif is_opened:
            # Selected potential sites: baseline color squares
            ax.scatter(x, y, c=COLOR_BASELINE, s=2000, marker='s', edgecolors=COLOR_BASELINE_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        else:
            # Unselected potential sites in grey squares
            ax.scatter(x, y, c='grey', s=1500, marker='s', edgecolors='black', linewidth=1, alpha=0.5)
            ax.text(x, y, label, ha='center', va='center', fontsize=24, color='white', alpha=0.7)
    
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)
    ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
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
    """Plot capped model selected sites in red, existing sites (C) in orange circles, others in grey."""
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Get opened sites
    opened_sites = [i for i in inst.I if capped_sol.x.get(i, 0) > 0.5]
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        label = site_to_label.get(i, i)
        is_fixed = i in EXISTING_SITES
        is_opened = i in opened_sites
        
        if is_fixed:
            # Existing sites: always show as orange circles
            ax.scatter(x, y, c=COLOR_EXISTING_SITE, s=2000, marker='o', edgecolors=COLOR_EXISTING_SITE_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        elif is_opened:
            # Selected potential sites: capped color squares
            ax.scatter(x, y, c=COLOR_CAPPED, s=2000, marker='s', edgecolors=COLOR_CAPPED_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        else:
            # Unselected potential sites in grey squares
            ax.scatter(x, y, c='grey', s=1500, marker='s', edgecolors='black', linewidth=1, alpha=0.5)
            ax.text(x, y, label, ha='center', va='center', fontsize=24, color='white', alpha=0.7)
    
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)
    ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_scalarized_selections(
    inst: CFLPInstance,
    scalarized_sol: CFLPSolution,
    site_xy: Dict[str, Tuple[float, float]],
    lambda_c: float,
    lambda_w: float,
    output_path: str,
) -> None:
    """Plot scalarized model selected sites in green, existing sites (C) in orange circles, others in grey."""
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Get opened sites
    opened_sites = [i for i in inst.I if scalarized_sol.x.get(i, 0) > 0.5]
    
    # Plot all sites
    for i, (x, y) in site_xy.items():
        label = site_to_label.get(i, i)
        is_fixed = i in EXISTING_SITES
        is_opened = i in opened_sites
        
        if is_fixed:
            # Existing sites: always show as orange circles
            ax.scatter(x, y, c=COLOR_EXISTING_SITE, s=2000, marker='o', edgecolors=COLOR_EXISTING_SITE_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        elif is_opened:
            # Selected potential sites: scalarized color squares
            ax.scatter(x, y, c=COLOR_SCALARIZED, s=2000, marker='s', edgecolors=COLOR_SCALARIZED_DARK, linewidth=2, alpha=0.8)
            ax.text(x, y, label, ha='center', va='center', fontsize=26, fontweight='bold', color='white')
        else:
            # Unselected potential sites in grey squares
            ax.scatter(x, y, c='grey', s=1500, marker='s', edgecolors='black', linewidth=1, alpha=0.5)
            ax.text(x, y, label, ha='center', va='center', fontsize=24, color='white', alpha=0.7)
    
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)
    ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
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
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.plot(cap_pcts, costs, 'o-', color='blue', linewidth=2, markersize=8)
    ax.set_xlabel(r'CO$_2$ Cap (% of Baseline)')
    ax.set_ylabel('Total Cost')
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()  # Show tightening from right to left
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_sensitivity_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Number of sites vs cap percentage
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.plot(cap_pcts, num_sites, 's-', color='red', linewidth=2, markersize=8)
    ax.set_xlabel(r'CO$_2$ Cap (% of Baseline)')
    ax.set_ylabel('Number of Sites Opened')
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
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    site_labels = [site_to_label.get(i, i) for i in inst.I]
    
    for sol, suffix in [(baseline_sol, "baseline"), (capped_sol, "capped")]:
        fig, ax = plt.subplots(figsize=(14, 12))
        
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
        ax.set_yticklabels(site_labels)
        
        # Add text annotations for significant flows
        max_flow = max(max(row) for row in matrix) if matrix else 1
        for i_idx in range(len(inst.I)):
            for r_idx in range(len(inst.R)):
                flow = matrix[i_idx][r_idx]
                if flow > 0.1:  # Only show significant flows
                    text = ax.text(r_idx, i_idx, f'{flow:.1f}', 
                                 ha="center", va="center", 
                                 color="black" if flow < max_flow * 0.5 else "white",
                                 fontsize=26)
        
        ax.set_xlabel('Regions')
        ax.set_ylabel('Sites')
        
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
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.plot(baseline_demand, baseline_co2, color=COLOR_BASELINE, linestyle='-', linewidth=2, label='Baseline', alpha=0.7)
    ax.plot(capped_demand, capped_co2, color=COLOR_CAPPED, linestyle='--', linewidth=2, label='Sustainability-aware', alpha=0.7)
    ax.set_xlabel('Cumulative Demand (%)')
    ax.set_ylabel(r'Cumulative CO$_2$ (kgCO$_2$e)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cumulative_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Cumulative Water
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.plot(baseline_demand, baseline_water, color=COLOR_BASELINE, linestyle='-', linewidth=2, label='Baseline', alpha=0.7)
    ax.plot(capped_demand, capped_water, color=COLOR_CAPPED, linestyle='--', linewidth=2, label='Sustainability-aware', alpha=0.7)
    ax.set_xlabel('Cumulative Demand (%)')
    ax.set_ylabel('Cumulative Water (liters)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cumulative_water.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_pareto_dual_axis(
    scalarized_results: List[Tuple[float, float, float, float, float, float]],
    lambda_grid: List[Tuple[float, float]],
    output_dir: str,
) -> None:
    """
    Plot Pareto curves with dual y-axes: Cost and impact vs lambda values.
    - CO₂ plot: x-axis = λ_c (with λ_w = 0), y-axes = Cost and CO₂
    - Water plot: x-axis = λ_w (with λ_c = 0), y-axes = Cost and Water
    """
    if not scalarized_results or not lambda_grid:
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert lambda_grid to tuples if needed (handle list format from JSON)
    lambda_tuples = []
    for lg in lambda_grid:
        if isinstance(lg, list):
            lambda_tuples.append((lg[0], lg[1]))
        else:
            lambda_tuples.append(lg)
    
    # Filter for CO₂ plot: λ_w = 0, vary λ_c
    co2_data = []
    for (lc, lw), result in zip(lambda_tuples, scalarized_results):
        # Handle both tuple and list formats for results
        if isinstance(result, list):
            obj, cost, co2, water = result[2], result[3], result[4], result[5]
        else:
            obj, cost, co2, water = result[2], result[3], result[4], result[5]
        if abs(lw) < 1e-6 and cost is not None and not np.isnan(cost) and co2 is not None and not np.isnan(co2):
            co2_data.append((lc, cost, co2))
    
    if co2_data:
        # Sort by lambda_c
        co2_data.sort(key=lambda x: x[0])
        lambda_c_vals, costs_co2, co2_vals = zip(*co2_data)
        
        fig, ax1 = plt.subplots(figsize=(14, 10))
        ax2 = ax1.twinx()
        
        line1 = ax1.plot(lambda_c_vals, costs_co2, 'b-o', linewidth=2, markersize=6, label='Cost', alpha=0.7)
        ax1.set_xlabel(r'$\lambda_c$ (CO$_2$ penalty weight)')
        ax1.set_ylabel('Total Cost', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True, alpha=0.3)
        
        line2 = ax2.plot(lambda_c_vals, co2_vals, 'r--', linewidth=2, markersize=6, label=r'CO$_2$', alpha=0.7)
        ax2.set_ylabel(r'Total CO$_2$ (kgCO$_2$e)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/fig_pareto_co2_cost.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    # Filter for Water plot: λ_c = 0, vary λ_w
    water_data = []
    for (lc, lw), result in zip(lambda_tuples, scalarized_results):
        # result is (lambda_c, lambda_w, obj, cost, co2, water)
        obj, cost, co2, water = result[2], result[3], result[4], result[5]
        if abs(lc) < 1e-6 and cost is not None and not np.isnan(cost) and water is not None and not np.isnan(water):
            water_data.append((lw, cost, water))
    
    if water_data:
        # Sort by lambda_w
        water_data.sort(key=lambda x: x[0])
        lambda_w_vals, costs_water, water_vals = zip(*water_data)
        
        fig, ax1 = plt.subplots(figsize=(14, 10))
        ax2 = ax1.twinx()
        
        line1 = ax1.plot(lambda_w_vals, costs_water, 'b-o', linewidth=2, markersize=6, label='Cost', alpha=0.7)
        ax1.set_xlabel(r'$\lambda_w$ (Water penalty weight)')
        ax1.set_ylabel('Total Cost', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True, alpha=0.3)
        
        line2 = ax2.plot(lambda_w_vals, water_vals, 'g--', linewidth=2, markersize=6, label='Water', alpha=0.7)
        ax2.set_ylabel('Total Water (liters)', color='g')
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
    width = 0.5
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    p1 = ax.bar(x, fixed_costs, width, label='Fixed + Operating Cost', color='blue', alpha=0.7)
    p2 = ax.bar(x, latency_costs, width, bottom=fixed_costs, label='Latency Proxy', color='orange', alpha=0.7)
    p3 = ax.bar(x, co2_costs, width, bottom=np.array(fixed_costs) + np.array(latency_costs), 
                label=r'CO$_2$ Penalty', color='red', alpha=0.7)
    p4 = ax.bar(x, water_costs, width, 
                bottom=np.array(fixed_costs) + np.array(latency_costs) + np.array(co2_costs),
                label='Water Penalty', color='cyan', alpha=0.7)
    
    ax.set_ylabel('Objective Value')
    ax.set_xlabel('Model Variant')
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
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot site capacity utilization for baseline, capped, and scalarized models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    sites = sorted(inst.I)
    site_labels = [site_to_label.get(i, i) for i in sites]
    baseline_util = []
    capped_util = []
    scalarized_util = []
    
    for i in sites:
        baseline_flow = sum(baseline_sol.y.get((i, r), 0) for r in inst.R)
        capped_flow = sum(capped_sol.y.get((i, r), 0) for r in inst.R)
        baseline_util.append((baseline_flow / inst.C[i] * 100) if inst.C[i] > 0 else 0)
        capped_util.append((capped_flow / inst.C[i] * 100) if inst.C[i] > 0 else 0)
        
        if scalarized_sol:
            scalarized_flow = sum(scalarized_sol.y.get((i, r), 0) for r in inst.R)
            scalarized_util.append((scalarized_flow / inst.C[i] * 100) if inst.C[i] > 0 else 0)
        else:
            scalarized_util.append(0)
    
    x = np.arange(len(sites))
    width = 0.3
    
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.bar(x - width, baseline_util, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_util, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_util, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    
    ax.set_ylabel('Capacity Utilization (%)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(site_labels, rotation=45, ha='right')
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True)
    ax.grid(True, alpha=0.3, axis='y')
    ax.axhline(y=100, color='r', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_utilization.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_impact_per_region(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot CO₂ and water impact per region for baseline, capped, and scalarized models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    regions = sorted(inst.R)
    baseline_co2_per_region = []
    capped_co2_per_region = []
    scalarized_co2_per_region = []
    baseline_water_per_region = []
    capped_water_per_region = []
    scalarized_water_per_region = []
    
    for r in regions:
        baseline_co2 = sum(baseline_sol.y.get((i, r), 0) * inst.e_co2[i] for i in inst.I)
        capped_co2 = sum(capped_sol.y.get((i, r), 0) * inst.e_co2[i] for i in inst.I)
        baseline_water = sum(baseline_sol.y.get((i, r), 0) * inst.w[i] for i in inst.I)
        capped_water = sum(capped_sol.y.get((i, r), 0) * inst.w[i] for i in inst.I)
        
        baseline_co2_per_region.append(baseline_co2)
        capped_co2_per_region.append(capped_co2)
        baseline_water_per_region.append(baseline_water)
        capped_water_per_region.append(capped_water)
        
        if scalarized_sol:
            scalarized_co2 = sum(scalarized_sol.y.get((i, r), 0) * inst.e_co2[i] for i in inst.I)
            scalarized_water = sum(scalarized_sol.y.get((i, r), 0) * inst.w[i] for i in inst.I)
            scalarized_co2_per_region.append(scalarized_co2)
            scalarized_water_per_region.append(scalarized_water)
        else:
            scalarized_co2_per_region.append(0)
            scalarized_water_per_region.append(0)
    
    x = np.arange(len(regions))
    width = 0.3
    
    # CO2 per region
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.bar(x - width, baseline_co2_per_region, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_co2_per_region, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_co2_per_region, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    ax.set_ylabel(r'CO$_2$ (kgCO$_2$e)')
    ax.set_xlabel('Region')
    ax.set_xticks(x)
    ax.set_xticklabels(regions, rotation=45, ha='right')
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_co2_per_region.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water per region
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.bar(x - width, baseline_water_per_region, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_water_per_region, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_water_per_region, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    ax.set_ylabel('Water (liters)')
    ax.set_xlabel('Region')
    ax.set_xticks(x)
    ax.set_xticklabels(regions, rotation=45, ha='right')
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_water_per_region.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_impact_per_site(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot CO₂ and water impact per site for baseline, capped, and scalarized models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Sort sites: C sites first (C1-C5), then S sites (S1-S5)
    def sort_key(site):
        label = site_to_label.get(site, site)
        if label.startswith('C'):
            return (0, int(label[1:]))  # C sites first, sorted by number
        else:
            return (1, int(label[1:]))  # S sites second, sorted by number
    
    sites = sorted(inst.I, key=sort_key)
    site_labels = [site_to_label.get(i, i) for i in sites]
    baseline_co2_per_site = []
    capped_co2_per_site = []
    scalarized_co2_per_site = []
    baseline_water_per_site = []
    capped_water_per_site = []
    scalarized_water_per_site = []
    
    for i in sites:
        baseline_co2 = sum(baseline_sol.y.get((i, r), 0) * inst.e_co2[i] for r in inst.R)
        capped_co2 = sum(capped_sol.y.get((i, r), 0) * inst.e_co2[i] for r in inst.R)
        baseline_water = sum(baseline_sol.y.get((i, r), 0) * inst.w[i] for r in inst.R)
        capped_water = sum(capped_sol.y.get((i, r), 0) * inst.w[i] for r in inst.R)
        
        baseline_co2_per_site.append(baseline_co2)
        capped_co2_per_site.append(capped_co2)
        baseline_water_per_site.append(baseline_water)
        capped_water_per_site.append(capped_water)
        
        if scalarized_sol:
            scalarized_co2 = sum(scalarized_sol.y.get((i, r), 0) * inst.e_co2[i] for r in inst.R)
            scalarized_water = sum(scalarized_sol.y.get((i, r), 0) * inst.w[i] for r in inst.R)
            scalarized_co2_per_site.append(scalarized_co2)
            scalarized_water_per_site.append(scalarized_water)
        else:
            scalarized_co2_per_site.append(0)
            scalarized_water_per_site.append(0)
    
    x = np.arange(len(sites))
    width = 0.3
    
    # CO2 per site
    fig, ax = plt.subplots(figsize=(20, 10))
    ax.bar(x - width, baseline_co2_per_site, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_co2_per_site, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_co2_per_site, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    
    # Calculate max Y value for scaling
    max_val = max(max(baseline_co2_per_site), max(capped_co2_per_site))
    if scalarized_sol:
        max_val = max(max_val, max(scalarized_co2_per_site))
    ax.set_ylim(0, max_val * 1.05)
    
    ax.set_ylabel(r'CO$_2$ (kgCO$_2$e)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(site_labels, rotation=45, ha='right')
    ax.legend(loc='upper right', prop={'size': 21})
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_co2_per_site.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Water per site
    fig, ax = plt.subplots(figsize=(20, 10))
    ax.bar(x - width, baseline_water_per_site, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_water_per_site, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_water_per_site, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    
    # Calculate max Y value for scaling
    max_val = max(max(baseline_water_per_site), max(capped_water_per_site))
    if scalarized_sol:
        max_val = max(max_val, max(scalarized_water_per_site))
    ax.set_ylim(0, max_val * 1.05)
    
    ax.set_ylabel('Water (liters)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(site_labels, rotation=45, ha='right')
    ax.legend(loc='upper right', prop={'size': 21})
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_water_per_site.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_cost_breakdown_by_site(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot cost breakdown by site (fixed + operating) for opened sites."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    baseline_sites = [i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5]
    capped_sites = [i for i in inst.I if capped_sol.x.get(i, 0) > 0.5]
    scalarized_sites = [i for i in inst.I if scalarized_sol and scalarized_sol.x.get(i, 0) > 0.5] if scalarized_sol else []
    
    all_sites = sorted(set(baseline_sites + capped_sites + scalarized_sites))
    all_site_labels = [site_to_label.get(i, i) for i in all_sites]
    
    baseline_costs = [(inst.F[i] + inst.O[i]) if i in baseline_sites else 0 for i in all_sites]
    capped_costs = [(inst.F[i] + inst.O[i]) if i in capped_sites else 0 for i in all_sites]
    scalarized_costs = [(inst.F[i] + inst.O[i]) if i in scalarized_sites else 0 for i in all_sites] if scalarized_sol else [0] * len(all_sites)
    
    x = np.arange(len(all_sites))
    width = 0.3
    
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.bar(x - width, baseline_costs, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_costs, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    if scalarized_sol:
        ax.bar(x + width, scalarized_costs, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    
    ax.set_ylabel('Site Cost (Fixed + Operating)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(all_site_labels, rotation=45, ha='right')
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_cost_by_site.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_site_flows(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    scalarized_sol: Optional[CFLPSolution],
    output_dir: str,
) -> None:
    """Plot allocated flow per site for baseline, capped, and scalarized models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Sort sites: C sites first (C1-C5), then S sites (S1-S5)
    def sort_key(site):
        label = site_to_label.get(site, site)
        if label.startswith('C'):
            return (0, int(label[1:]))  # C sites first, sorted by number
        else:
            return (1, int(label[1:]))  # S sites second, sorted by number
    
    sites = sorted(inst.I, key=sort_key)
    site_labels = [site_to_label.get(i, i) for i in sites]
    baseline_flows = []
    capped_flows = []
    scalarized_flows = []
    
    for i in sites:
        baseline_flow = sum(baseline_sol.y.get((i, r), 0) for r in inst.R)
        capped_flow = sum(capped_sol.y.get((i, r), 0) for r in inst.R)
        baseline_flows.append(baseline_flow)
        capped_flows.append(capped_flow)
        
        if scalarized_sol is not None:
            scalarized_flow = sum(scalarized_sol.y.get((i, r), 0) for r in inst.R)
            scalarized_flows.append(scalarized_flow)
        else:
            scalarized_flows.append(0)
    
    x = np.arange(len(sites))
    width = 0.3
    
    fig, ax = plt.subplots(figsize=(20, 10))
    ax.bar(x - width, baseline_flows, width, label='Baseline', color=COLOR_BASELINE, alpha=0.7)
    ax.bar(x, capped_flows, width, label='Capped', color=COLOR_CAPPED, alpha=0.7)
    # Always show scalarized bar - check if we have data
    has_scalarized_data = scalarized_sol is not None and any(f > 0 for f in scalarized_flows)
    if has_scalarized_data:
        ax.bar(x + width, scalarized_flows, width, label='Scalarized (50,50)', color=COLOR_SCALARIZED, alpha=0.7)
    else:
        # Debug: print if scalarized_sol is None or has no data
        if scalarized_sol is None:
            print("WARNING: scalarized_sol is None in plot_site_flows")
        elif not any(f > 0 for f in scalarized_flows):
            print(f"WARNING: scalarized_flows are all zero: {scalarized_flows}")
    
    # Calculate max Y value for scaling
    max_val = max(max(baseline_flows), max(capped_flows))
    if has_scalarized_data:
        max_val = max(max_val, max(scalarized_flows))
    ax.set_ylim(0, max_val * 1.05)
    
    ax.set_ylabel('Allocated Flow (units)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(site_labels, rotation=45, ha='right')
    # Move legend to upper right inside the plot with smaller font
    ax.legend(loc='upper right', prop={'size': 21})
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_flows.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_site_selection_comparison(
    inst: CFLPInstance,
    baseline_sol: CFLPSolution,
    capped_sol: CFLPSolution,
    output_dir: str,
) -> None:
    """Plot which sites are selected in baseline vs capped models."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    baseline_selected = set(i for i in inst.I if baseline_sol.x.get(i, 0) > 0.5)
    capped_selected = set(i for i in inst.I if capped_sol.x.get(i, 0) > 0.5)
    
    # Create matrix: rows = sites, cols = models
    sites = sorted(inst.I)
    site_labels = [site_to_label.get(i, i) for i in sites]
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
    ax.set_yticklabels(site_labels)
    
    for i in range(len(sites)):
        for j in range(len(models)):
            text = ax.text(j, i, matrix[i][j], ha="center", va="center", color="black", fontsize=34)
    
    ax.set_xlabel('Model')
    ax.set_ylabel('Site')
    
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Selected (1) / Not Selected (0)', rotation=270, labelpad=20)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_selection_matrix.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_lambda_heatmaps(
    scalarized_results: List,
    lambda_grid: List,
    output_dir: str,
) -> None:
    """
    Plot heatmaps with lambda values as axes, showing different metrics.
    Creates separate heatmaps for: cost, CO₂, water, objective value.
    """
    if not scalarized_results or not lambda_grid:
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert lambda_grid to tuples
    lambda_tuples = []
    for lg in lambda_grid:
        if isinstance(lg, list):
            lambda_tuples.append((lg[0], lg[1]))
        else:
            lambda_tuples.append(lg)
    
    # Get unique lambda values
    lambda_c_values = sorted(set(lc for lc, lw in lambda_tuples))
    lambda_w_values = sorted(set(lw for lc, lw in lambda_tuples))
    
    # Create dictionaries for quick lookup
    data_dict = {}
    for (lc, lw), result in zip(lambda_tuples, scalarized_results):
        if isinstance(result, list):
            obj, cost, co2, water = result[2], result[3], result[4], result[5]
        else:
            obj, cost, co2, water = result[2], result[3], result[4], result[5]
        data_dict[(lc, lw)] = {
            'obj': obj,
            'cost': cost,
            'co2': co2,
            'water': water
        }
    
    # Create matrices for each metric
    def create_matrix(metric_name):
        matrix = []
        for lc in lambda_c_values:
            row = []
            for lw in lambda_w_values:
                key = (lc, lw)
                if key in data_dict:
                    val = data_dict[key][metric_name]
                    row.append(val if val is not None and not np.isnan(val) else np.nan)
                else:
                    row.append(np.nan)
            matrix.append(row)
        return matrix
    
    cost_matrix = create_matrix('cost')
    co2_matrix = create_matrix('co2')
    water_matrix = create_matrix('water')
    obj_matrix = create_matrix('obj')
    
    # Plot Cost heatmap
    fig, ax = plt.subplots(figsize=(16, 12))
    im = ax.imshow(cost_matrix, cmap='YlOrRd', aspect='auto', interpolation='nearest', vmin=3000, vmax=4500)
    ax.set_xticks(range(len(lambda_w_values)))
    ax.set_yticks(range(len(lambda_c_values)))
    ax.set_xticklabels([f'{lw:.0f}' for lw in lambda_w_values])
    ax.set_yticklabels([f'{lc:.0f}' for lc in lambda_c_values])
    ax.set_xlabel(r'$\lambda_w$ (Water penalty weight)')
    ax.set_ylabel(r'$\lambda_c$ (CO$_2$ penalty weight)')
    cbar = plt.colorbar(im, ax=ax, ticks=[3000, 3300, 3600, 3900, 4200, 4500])
    cbar.set_label('Total Cost', rotation=270, labelpad=20)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_cost.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Plot CO₂ heatmap
    fig, ax = plt.subplots(figsize=(16, 12))
    im = ax.imshow(co2_matrix, cmap='Reds', aspect='auto', interpolation='nearest')
    ax.set_xticks(range(len(lambda_w_values)))
    ax.set_yticks(range(len(lambda_c_values)))
    ax.set_xticklabels([f'{lw:.0f}' for lw in lambda_w_values])
    ax.set_yticklabels([f'{lc:.0f}' for lc in lambda_c_values])
    ax.set_xlabel(r'$\lambda_w$ (Water penalty weight)')
    ax.set_ylabel(r'$\lambda_c$ (CO$_2$ penalty weight)')
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(r'Total CO$_2$ (kgCO$_2$e)', rotation=270, labelpad=20)
    # Add text annotations
    for i in range(len(lambda_c_values)):
        for j in range(len(lambda_w_values)):
            val = co2_matrix[i][j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.1f}', ha="center", va="center", 
                       color="white" if val > np.nanmax(co2_matrix) * 0.6 else "black", fontsize=20)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_co2.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Plot Water heatmap
    fig, ax = plt.subplots(figsize=(16, 12))
    im = ax.imshow(water_matrix, cmap='Blues', aspect='auto', interpolation='nearest')
    ax.set_xticks(range(len(lambda_w_values)))
    ax.set_yticks(range(len(lambda_c_values)))
    ax.set_xticklabels([f'{lw:.0f}' for lw in lambda_w_values])
    ax.set_yticklabels([f'{lc:.0f}' for lc in lambda_c_values])
    ax.set_xlabel(r'$\lambda_w$ (Water penalty weight)')
    ax.set_ylabel(r'$\lambda_c$ (CO$_2$ penalty weight)')
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Total Water (liters)', rotation=270, labelpad=20)
    # Add text annotations
    for i in range(len(lambda_c_values)):
        for j in range(len(lambda_w_values)):
            val = water_matrix[i][j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.1f}', ha="center", va="center", 
                       color="white" if val > np.nanmax(water_matrix) * 0.6 else "black", fontsize=20)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_water.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Plot Objective value heatmap
    fig, ax = plt.subplots(figsize=(16, 12))
    im = ax.imshow(obj_matrix, cmap='viridis', aspect='auto', interpolation='nearest')
    ax.set_xticks(range(len(lambda_w_values)))
    ax.set_yticks(range(len(lambda_c_values)))
    ax.set_xticklabels([f'{lw:.0f}' for lw in lambda_w_values])
    ax.set_yticklabels([f'{lc:.0f}' for lc in lambda_c_values])
    ax.set_xlabel(r'$\lambda_w$ (Water penalty weight)')
    ax.set_ylabel(r'$\lambda_c$ (CO$_2$ penalty weight)')
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Objective Value', rotation=270, labelpad=20)
    # Add text annotations
    for i in range(len(lambda_c_values)):
        for j in range(len(lambda_w_values)):
            val = obj_matrix[i][j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.0f}', ha="center", va="center", 
                       color="white" if val > np.nanmax(obj_matrix) * 0.6 else "black", fontsize=20)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_objective.png", dpi=150, bbox_inches='tight')
    plt.close()
# New plotting functions for figure-first numerical section (continued from above)
# Note: These functions use imports from the top of this file


def extract_site_flows_by_class(
    inst: CFLPInstance,
    sol_dict: dict,
    existing_sites: List[str],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Extract per-site flows split by inference and training by re-solving the model.
    
    Args:
        inst: CFLPInstance
        sol_dict: Solution dictionary with 'x' (opened sites) and 'y' (merged flows)
        existing_sites: List of existing sites that are forced open
    
    Returns:
        (site_flows_inf, site_flows_train) - dictionaries mapping site to flow
    """
    # Rebuild the model to extract separate flows
    # Determine which variant based on solution keys
    has_caps = 'gamma_co2' in sol_dict
    
    m, x, y_inf, y_train = build_baseline_model(inst, output_flag=0, existing_sites=existing_sites)
    
    # Fix opened sites
    opened_sites = [s for s, v in sol_dict['x'].items() if v > 0.5]
    for site in opened_sites:
        if site in inst.I:
            m.addConstr(x[site] == 1, name=f"fix_opened[{site}]")
    
    # Add caps if needed
    if has_caps:
        add_usage_caps(m, inst, y_inf, y_train, 
                      gamma_co2=sol_dict.get('gamma_co2', 1e6),
                      gamma_w=sol_dict.get('gamma_w', 1e6))
    
    # Set scalarized objective if needed (check if lambda values exist)
    if 'lambda_c' in sol_dict or 'lambda_w' in sol_dict:
        lambda_c = sol_dict.get('lambda_c', 0)
        lambda_w = sol_dict.get('lambda_w', 0)
        set_scalarized_objective(m, inst, x, y_inf, y_train, lambda_c=lambda_c, lambda_w=lambda_w)
    
    m.optimize()
    
    site_flows_inf = {}
    site_flows_train = {}
    
    if m.Status == 2:  # Optimal
        for site in inst.I:
            inf_total = sum(y_inf[(site, r)].X for r in inst.R if (site, r) in y_inf)
            train_total = sum(y_train[(site, r)].X for r in inst.R if (site, r) in y_train)
            site_flows_inf[site] = inf_total
            site_flows_train[site] = train_total
    
    return site_flows_inf, site_flows_train


def plot_site_flows_stacked_inf_train(
    inst: CFLPInstance,
    baseline_sol_dict: dict,
    capped_sol_dict: dict,
    scalarized_sol_dict: Optional[dict],
    output_dir: str = "results/figures",
) -> None:
    """
    Plot stacked bar chart showing per-site flows split into inference vs training.
    
    This plot makes clear which workload class provides flexibility under sustainability constraints.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract flows by class for each variant
    baseline_inf, baseline_train = extract_site_flows_by_class(inst, baseline_sol_dict, EXISTING_SITES)
    capped_inf, capped_train = extract_site_flows_by_class(inst, capped_sol_dict, EXISTING_SITES)
    
    scalarized_inf = {}
    scalarized_train = {}
    if scalarized_sol_dict:
        scalarized_inf, scalarized_train = extract_site_flows_by_class(inst, scalarized_sol_dict, EXISTING_SITES)
    
    # Get site label mapping
    site_to_label, _ = get_site_label_mapping(inst)
    
    # Sort sites: existing (C) first, then potential (S)
    def sort_key(site):
        label = site_to_label.get(site, site)
        if label.startswith('C'):
            return (0, int(label[1:]))
        else:
            return (1, int(label[1:]))
    
    sites = sorted(inst.I, key=sort_key)
    site_labels = [site_to_label.get(i, i) for i in sites]
    
    # Prepare data for stacked bars
    baseline_inf_vals = [baseline_inf.get(s, 0) for s in sites]
    baseline_train_vals = [baseline_train.get(s, 0) for s in sites]
    capped_inf_vals = [capped_inf.get(s, 0) for s in sites]
    capped_train_vals = [capped_train.get(s, 0) for s in sites]
    scalarized_inf_vals = [scalarized_inf.get(s, 0) for s in sites] if scalarized_inf else None
    scalarized_train_vals = [scalarized_train.get(s, 0) for s in sites] if scalarized_train else None
    
    x = np.arange(len(sites))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Baseline stacked bars
    p1 = ax.bar(x - width, baseline_inf_vals, width, label='Baseline (Inference)', 
                color=COLOR_BASELINE, alpha=0.8)
    p2 = ax.bar(x - width, baseline_train_vals, width, bottom=baseline_inf_vals, 
                label='Baseline (Training)', color=COLOR_BASELINE, alpha=0.5, hatch='///')
    
    # Capped stacked bars
    p3 = ax.bar(x, capped_inf_vals, width, label='Capped 80% (Inference)', 
                color=COLOR_CAPPED, alpha=0.8)
    p4 = ax.bar(x, capped_train_vals, width, bottom=capped_inf_vals, 
                label='Capped 80% (Training)', color=COLOR_CAPPED, alpha=0.5, hatch='///')
    
    # Scalarized stacked bars (if available)
    if scalarized_inf_vals and scalarized_train_vals:
        p5 = ax.bar(x + width, scalarized_inf_vals, width, label='Scalarized 50,50 (Inference)', 
                    color=COLOR_SCALARIZED, alpha=0.8)
        p6 = ax.bar(x + width, scalarized_train_vals, width, bottom=scalarized_inf_vals, 
                    label='Scalarized 50,50 (Training)', color=COLOR_SCALARIZED, alpha=0.5, hatch='///')
    
    # Mark existing sites
    for i, site in enumerate(sites):
        if site in EXISTING_SITES:
            ax.axvline(i, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
    
    ax.set_ylabel('Allocated Flow (units)')
    ax.set_xlabel('Site')
    ax.set_xticks(x)
    ax.set_xticklabels(site_labels, rotation=45, ha='right')
    ax.legend(loc='upper left', ncol=2)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_site_flows_stacked_inf_train.png", dpi=150, bbox_inches='tight')
    plt.close()


def plot_plan_id_heatmap(
    scalarized_results: List[Tuple[float, float, float, float, float, float]],
    lambda_grid: List[Tuple[float, float]],
    output_dir: str = "results/figures",
) -> None:
    """
    Plot heatmap showing plan ID (unique set of opened potential sites) over (lambda_C, lambda_W) grid.
    
    This shows decision stability: each color corresponds to a distinct expansion plan.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract unique plans (sets of opened potential sites)
    # We need to re-solve to get which potential sites are opened
    # For now, use a hash based on cost/co2/water to identify similar plans
    # In practice, you'd want to store the actual opened sites for each lambda combination
    
    # Group results by plan signature (rounded cost, co2, water)
    plan_signatures = {}
    plan_ids = {}
    
    for idx, (lc, lw, obj, cost, co2, water) in enumerate(scalarized_results):
        # Create signature from rounded values
        sig = (round(cost, -1), round(co2, 0), round(water, 0))
        if sig not in plan_signatures:
            plan_signatures[sig] = len(plan_signatures)
        plan_ids[idx] = plan_signatures[sig]
    
    # Create matrix
    lambda_c_vals = sorted(set(lc for lc, lw in lambda_grid))
    lambda_w_vals = sorted(set(lw for lc, lw in lambda_grid))
    
    plan_matrix = np.zeros((len(lambda_c_vals), len(lambda_w_vals)))
    
    for idx, (lc, lw) in enumerate(lambda_grid):
        i = lambda_c_vals.index(lc)
        j = lambda_w_vals.index(lw)
        plan_matrix[i, j] = plan_ids[idx]
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Use discrete colormap
    num_plans = len(plan_signatures)
    cmap = plt.cm.get_cmap('tab20', num_plans)
    
    im = ax.imshow(plan_matrix, cmap=cmap, aspect='auto', interpolation='nearest')
    
    # Set ticks
    ax.set_xticks(range(len(lambda_w_vals)))
    ax.set_yticks(range(len(lambda_c_vals)))
    ax.set_xticklabels([int(lw) for lw in lambda_w_vals])
    ax.set_yticklabels([int(lc) for lc in lambda_c_vals])
    
    ax.set_xlabel(r'$\lambda_W$ (Water penalty weight)', fontsize=30)
    ax.set_ylabel(r'$\lambda_C$ (CO$_2$ penalty weight)', fontsize=30)
    ax.set_title('Decision Stability: Plan ID over $(\lambda_C, \lambda_W)$ Grid', fontsize=32)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, ticks=range(num_plans))
    cbar.set_label('Plan ID', rotation=270, labelpad=15)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_plan_id.png", dpi=150, bbox_inches='tight')
    plt.close()

