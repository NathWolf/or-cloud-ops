"""Analysis functions for CFLP solutions: binding constraints, Pareto fronts, stability."""
from typing import Dict, List, Tuple, Optional, Set
import numpy as np
from dataclasses import dataclass

from src.models.cflp import CFLPInstance, CFLPSolution


@dataclass
class BindingConstraints:
    """Binding constraints analysis for a solution."""
    co2_slack: float
    water_slack: float
    capacity_slack: Dict[str, float]  # per site
    co2_utilization: float  # percentage of cap used
    water_utilization: float  # percentage of cap used
    num_binding_capacity: int  # number of sites at capacity
    num_regions_near_boundary: int  # regions with assignments near eligibility boundary


def compute_binding_constraints(
    inst: CFLPInstance,
    sol: CFLPSolution,
    gamma_co2: Optional[float] = None,
    gamma_w: Optional[float] = None,
) -> BindingConstraints:
    """
    Compute binding constraints and slack for a solution.
    
    If gamma_co2/gamma_w are provided, computes slack relative to caps.
    Otherwise, computes capacity slack only.
    """
    # Capacity slack per site
    capacity_slack = {}
    num_binding_capacity = 0
    for i in inst.I:
        total_flow = sum(sol.y.get((i, r), 0.0) for r in inst.R)
        slack = inst.C[i] * sol.x.get(i, 0.0) - total_flow
        capacity_slack[i] = slack
        if slack < 1e-6 and sol.x.get(i, 0.0) > 0.5:  # Binding and site is open
            num_binding_capacity += 1
    
    # CO2 and water slack (if caps provided)
    co2_slack = None
    water_slack = None
    co2_utilization = None
    water_utilization = None
    
    if gamma_co2 is not None:
        total_co2 = sol.total_co2 or 0.0
        co2_slack = gamma_co2 - total_co2
        co2_utilization = (total_co2 / gamma_co2 * 100) if gamma_co2 > 0 else 0.0
    
    if gamma_w is not None:
        total_water = sol.total_water or 0.0
        water_slack = gamma_w - total_water
        water_utilization = (total_water / gamma_w * 100) if gamma_w > 0 else 0.0
    
    # Count regions near eligibility boundary (simplified: check if using farthest eligible site)
    num_regions_near_boundary = 0
    if inst.has_split_demand():
        A_inf = inst.eligibility_sets("inf")
        A_train = inst.eligibility_sets("train")
        for r in inst.R:
            # Check inference flows
            inf_flows = [(i, sol.y.get((i, r), 0.0)) for i in A_inf[r] if (i, r) in sol.y]
            if inf_flows:
                max_dist = max(inst.c[(i, r)] for i, flow in inf_flows if flow > 1e-6)
                threshold = inst.Lmax_inf[r]
                if max_dist >= threshold * 0.9:  # Within 10% of boundary
                    num_regions_near_boundary += 1
            # Check training flows
            train_flows = [(i, sol.y.get((i, r), 0.0)) for i in A_train[r] if (i, r) in sol.y]
            if train_flows:
                max_dist = max(inst.c[(i, r)] for i, flow in train_flows if flow > 1e-6)
                threshold = inst.Lmax_train[r]
                if max_dist >= threshold * 0.9:  # Within 10% of boundary
                    num_regions_near_boundary += 1
    
    return BindingConstraints(
        co2_slack=co2_slack,
        water_slack=water_slack,
        capacity_slack=capacity_slack,
        co2_utilization=co2_utilization,
        water_utilization=water_utilization,
        num_binding_capacity=num_binding_capacity,
        num_regions_near_boundary=num_regions_near_boundary,
    )


def extract_pareto_front(
    results: List[Tuple[float, float, float, float]],
    objective1_idx: int = 1,  # cost
    objective2_idx: int = 2,  # co2 or water
) -> List[Tuple[float, float, float, float]]:
    """
    Extract nondominated (Pareto) points from scalarized results.
    
    Args:
        results: List of (obj, cost, co2, water) tuples
        objective1_idx: Index of first objective (default: 1 for cost)
        objective2_idx: Index of second objective (default: 2 for co2)
    
    Returns:
        List of nondominated points (same format as input)
    """
    if not results:
        return []
    
    # Filter out invalid results
    valid_results = [
        r for r in results
        if r[objective1_idx] is not None and not np.isnan(r[objective1_idx])
        and r[objective2_idx] is not None and not np.isnan(r[objective2_idx])
    ]
    
    if not valid_results:
        return []
    
    # Find nondominated points (minimize both objectives)
    pareto = []
    for i, point_i in enumerate(valid_results):
        is_dominated = False
        for j, point_j in enumerate(valid_results):
            if i == j:
                continue
            # Check if point_j dominates point_i
            obj1_i = point_i[objective1_idx]
            obj2_i = point_i[objective2_idx]
            obj1_j = point_j[objective1_idx]
            obj2_j = point_j[objective2_idx]
            
            # point_j dominates if it's better or equal in both objectives and strictly better in at least one
            if (obj1_j <= obj1_i and obj2_j <= obj2_i) and (obj1_j < obj1_i or obj2_j < obj2_i):
                is_dominated = True
                break
        
        if not is_dominated:
            pareto.append(point_i)
    
    # Sort by first objective for easier visualization
    pareto.sort(key=lambda x: x[objective1_idx])
    return pareto


def compute_decision_stability(
    inst: CFLPInstance,
    lambda_grid: List[Tuple[float, float]],
    solutions: List[CFLPSolution],
) -> Dict[Tuple[int, ...], Dict[str, any]]:
    """
    Compute decision stability: identify unique plans (site sets) and their lambda regions.
    
    Args:
        inst: Instance
        lambda_grid: List of (lambda_c, lambda_w) tuples
        solutions: List of solutions corresponding to lambda_grid
    
    Returns:
        Dictionary mapping plan signature (tuple of opened site indices) to:
        - sites: set of opened sites
        - lambda_region: list of (lambda_c, lambda_w) where this plan is optimal
        - first_threshold: first lambda value where plan changes from baseline
    """
    # Extract opened sites for each solution
    plan_signatures = {}
    for (lc, lw), sol in zip(lambda_grid, solutions):
        opened_sites = tuple(sorted(i for i in inst.I if sol.x.get(i, 0.0) > 0.5))
        if opened_sites not in plan_signatures:
            plan_signatures[opened_sites] = {
                "sites": set(opened_sites),
                "lambda_region": [],
            }
        plan_signatures[opened_sites]["lambda_region"].append((lc, lw))
    
    # Find baseline plan (lambda = (0, 0))
    baseline_plan = None
    for (lc, lw), sol in zip(lambda_grid, solutions):
        if abs(lc) < 1e-6 and abs(lw) < 1e-6:
            baseline_plan = tuple(sorted(i for i in inst.I if sol.x.get(i, 0.0) > 0.5))
            break
    
    # Find first threshold where plan changes from baseline
    for sig, info in plan_signatures.items():
        if sig == baseline_plan:
            info["first_threshold"] = None  # Baseline plan
        else:
            # Find minimum lambda_c + lambda_w where this plan appears
            min_lambda = float('inf')
            for lc, lw in info["lambda_region"]:
                total_lambda = lc + lw
                if total_lambda < min_lambda:
                    min_lambda = total_lambda
            info["first_threshold"] = min_lambda if min_lambda != float('inf') else None
    
    return plan_signatures


def compute_kpis(
    inst: CFLPInstance,
    sol: CFLPSolution,
    existing_sites: Optional[List[str]] = None,
) -> Dict[str, any]:
    """
    Compute KPIs including new ones: # new sites opened, max utilization.
    
    Args:
        inst: Instance
        sol: Solution
        existing_sites: List of existing sites (always open)
    
    Returns:
        Dictionary with KPIs
    """
    opened_sites = [i for i in inst.I if sol.x.get(i, 0.0) > 0.5]
    num_opened = len(opened_sites)
    
    # Number of new sites (excluding existing sites)
    if existing_sites:
        new_sites = [i for i in opened_sites if i not in existing_sites]
        num_new_sites = len(new_sites)
    else:
        num_new_sites = num_opened
    
    # Max utilization
    max_utilization = 0.0
    for i in inst.I:
        if sol.x.get(i, 0.0) > 0.5:
            total_flow = sum(sol.y.get((i, r), 0.0) for r in inst.R)
            if inst.C[i] > 0:
                utilization = (total_flow / inst.C[i]) * 100
                max_utilization = max(max_utilization, utilization)
    
    return {
        "num_opened_sites": num_opened,
        "num_new_sites": num_new_sites,
        "max_utilization": max_utilization,
        "total_cost": sol.total_cost,
        "total_co2": sol.total_co2,
        "total_water": sol.total_water,
        "total_latency_proxy": sol.total_latency_proxy,
    }

