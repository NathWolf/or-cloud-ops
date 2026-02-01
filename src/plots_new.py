"""New plotting functions for figure-first numerical section."""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from src.models.cflp import CFLPInstance, CFLPSolution, build_baseline_model, add_usage_caps, set_scalarized_objective
from src.utils import EXISTING_SITES, get_site_label_mapping
import gurobipy as gp

import matplotlib
# Import color constants from plots.py
from src.plots import COLOR_BASELINE, COLOR_CAPPED, COLOR_SCALARIZED, COLOR_EXISTING_SITE

# Ensure consistent font sizes
matplotlib.rcParams['font.size'] = 28
matplotlib.rcParams['axes.labelsize'] = 30
matplotlib.rcParams['axes.titlesize'] = 30
matplotlib.rcParams['xtick.labelsize'] = 28
matplotlib.rcParams['ytick.labelsize'] = 28
matplotlib.rcParams['legend.fontsize'] = 28
matplotlib.rcParams['figure.titlesize'] = 32


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
    has_caps = 'gamma_co2' in sol_dict and sol_dict.get('gamma_co2') is not None
    
    m, x, y_inf, y_train = build_baseline_model(inst, output_flag=0, existing_sites=existing_sites)
    
    # Fix opened sites
    opened_sites = [s for s, v in sol_dict['x'].items() if v > 0.5]
    for site in opened_sites:
        if site in inst.I:
            m.addConstr(x[site] == 1, name=f"fix_opened[{site}]")
    
    # Add caps if needed (only if gamma_co2 is actually provided)
    if has_caps:
        gamma_co2 = sol_dict.get('gamma_co2')
        gamma_w = sol_dict.get('gamma_w', 1e6)
        if gamma_co2 is not None:
            add_usage_caps(m, inst, y_inf, y_train, 
                          gamma_co2=gamma_co2,
                          gamma_w=gamma_w)
    
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
    Improved version: split into 3 subplots (one per model variant) for better readability.
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
    width = 0.8  # Wider bars for single-variant plots
    
    # Helper function to plot stacked bars for one variant
    def plot_variant(inf_vals, train_vals, color, variant_name, filename):
        """Plot stacked bars for one model variant and save as separate figure."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Inference bars (bottom)
        p1 = ax.bar(x, inf_vals, width, label='Inference', 
                    color=color, alpha=0.85, edgecolor='black', linewidth=0.5)
        # Training bars (stacked on top)
        p2 = ax.bar(x, train_vals, width, bottom=inf_vals, 
                    label='Training', color=color, alpha=0.5, hatch='///', 
                    edgecolor='black', linewidth=0.5)
        
        ax.set_ylabel('Allocated Flow (units)')
        ax.set_xlabel('Site')
        ax.set_xticks(x)
        ax.set_xticklabels(site_labels, rotation=45, ha='right')
        ax.legend(loc='upper right', prop={'size': 21})
        ax.grid(True, alpha=0.3, axis='y', zorder=0)
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/{filename}", dpi=150, bbox_inches='tight')
        plt.close()
    
    # Plot Baseline as separate figure
    plot_variant(baseline_inf_vals, baseline_train_vals, COLOR_BASELINE, 
                'Baseline', 'fig_site_flows_stacked_inf_train_baseline.png')
    
    # Plot Capped 80% as separate figure
    plot_variant(capped_inf_vals, capped_train_vals, COLOR_CAPPED, 
                'Capped 80%', 'fig_site_flows_stacked_inf_train_capped80.png')
    
    # Plot Scalarized 50,50 as separate figure (if available)
    if scalarized_inf_vals and scalarized_train_vals:
        plot_variant(scalarized_inf_vals, scalarized_train_vals, COLOR_SCALARIZED, 
                    'Scalarized (50,50)', 'fig_site_flows_stacked_inf_train_scalarized.png')
    
    # Also keep the combined version for backward compatibility
    n_plots = 3 if scalarized_inf_vals and scalarized_train_vals else 2
    fig, axes = plt.subplots(1, n_plots, figsize=(20, 8), sharey=True)
    if n_plots == 2:
        ax1, ax2 = axes
        ax3 = None
    else:
        ax1, ax2, ax3 = axes
    
    def plot_variant_combined(ax, inf_vals, train_vals, color):
        """Plot stacked bars for combined figure."""
        p1 = ax.bar(x, inf_vals, width, label='Inference', 
                    color=color, alpha=0.85, edgecolor='black', linewidth=0.5)
        p2 = ax.bar(x, train_vals, width, bottom=inf_vals, 
                    label='Training', color=color, alpha=0.5, hatch='///', 
                    edgecolor='black', linewidth=0.5)
        ax.set_ylabel('Allocated Flow (units)')
        ax.set_xlabel('Site')
        ax.set_xticks(x)
        ax.set_xticklabels(site_labels, rotation=45, ha='right')
        ax.legend(loc='upper right', prop={'size': 21})
        ax.grid(True, alpha=0.3, axis='y', zorder=0)
        ax.set_ylim(0, 105)
    
    plot_variant_combined(ax1, baseline_inf_vals, baseline_train_vals, COLOR_BASELINE)
    plot_variant_combined(ax2, capped_inf_vals, capped_train_vals, COLOR_CAPPED)
    if ax3 is not None and scalarized_inf_vals and scalarized_train_vals:
        plot_variant_combined(ax3, scalarized_inf_vals, scalarized_train_vals, COLOR_SCALARIZED)
    
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
    
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # Use discrete colormap
    num_plans = len(plan_signatures)
    cmap = plt.cm.get_cmap('tab20', num_plans)
    
    im = ax.imshow(plan_matrix, cmap=cmap, aspect='auto', interpolation='nearest')
    
    # Set ticks
    ax.set_xticks(range(len(lambda_w_vals)))
    ax.set_yticks(range(len(lambda_c_vals)))
    ax.set_xticklabels([int(lw) for lw in lambda_w_vals])
    ax.set_yticklabels([int(lc) for lc in lambda_c_vals])
    
    ax.set_xlabel(r'$\lambda_W$ (Water penalty weight)')
    ax.set_ylabel(r'$\lambda_C$ (CO$_2$ penalty weight)')
    ax.set_title('Decision Stability: Plan ID over $(\lambda_C, \lambda_W)$ Grid')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, ticks=range(num_plans))
    cbar.set_label('Plan ID', rotation=270, labelpad=15)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/fig_heatmap_plan_id.png", dpi=150, bbox_inches='tight')
    plt.close()

