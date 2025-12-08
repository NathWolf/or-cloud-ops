# Numerical-analysis models (baseline / capped-impact / scalarized) in gurobipy
# ------------------------------------------------------------
# Model matches your formulation:
#   min  Σ_i (F_i + O_i) x_i  +  φ Σ_{r} Σ_{i in A_r} c_{ir} y_{ir}
#   s.t. Σ_{i in A_r} y_{ir} = d_r                ∀r
#        Σ_{r} y_{ir} <= C_i x_i                 ∀i
#        y_{ir} >= 0, x_i ∈ {0,1}
# Sustainability variants:
#   (1) usage-based caps: Σ e_i y_{ir} <= Γ_CO2 ; Σ w_i y_{ir} <= Γ_W
#   (2) scalarized objective: add λC Σ e_i y_{ir} + λW Σ w_i y_{ir}

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple, Optional, Any
import math
import random

import gurobipy as gp
from gurobipy import GRB


Site = str
Region = str
Arc = Tuple[Site, Region]


@dataclass(frozen=True)
class CFLPInstance:
    I: List[Site]
    R: List[Region]

    # Costs and capacity
    F: Dict[Site, float]          # fixed (or annualized) open cost
    O: Dict[Site, float]          # operating cost if opened (same basis as objective)
    C: Dict[Site, float]          # capacity

    # Demand
    d: Dict[Region, float]

    # Latency / distance and eligibility
    c: Dict[Arc, float]           # latency/distance (defined for all i,r)
    Lmax: Dict[Region, float]     # eligibility threshold per region

    # Sustainability factors (per unit served)
    e_co2: Dict[Site, float]      # kgCO2e per unit served (or consistent unit)
    w: Dict[Site, float]          # water per unit served (or consistent unit)

    # Objective parameter
    phi: float = 0.0              # latency penalty weight (0 removes proxy cost)

    def eligible_arcs(self) -> List[Arc]:
        arcs: List[Arc] = []
        for r in self.R:
            for i in self.I:
                if self.c[(i, r)] <= self.Lmax[r]:
                    arcs.append((i, r))
        return arcs

    def eligibility_sets(self) -> Dict[Region, List[Site]]:
        A: Dict[Region, List[Site]] = {r: [] for r in self.R}
        for r in self.R:
            for i in self.I:
                if self.c[(i, r)] <= self.Lmax[r]:
                    A[r].append(i)
        return A

    def validate(self) -> None:
        # Check required keys exist
        for i in self.I:
            if i not in self.F or i not in self.O or i not in self.C:
                raise ValueError(f"Missing F/O/C for site {i}")
            if i not in self.e_co2 or i not in self.w:
                raise ValueError(f"Missing e_co2/w for site {i}")
        for r in self.R:
            if r not in self.d or r not in self.Lmax:
                raise ValueError(f"Missing d/Lmax for region {r}")
        for i in self.I:
            for r in self.R:
                if (i, r) not in self.c:
                    raise ValueError(f"Missing c[(i,r)] for {(i,r)}")

        # Ensure each region has at least one eligible site
        A = self.eligibility_sets()
        infeasible = [r for r in self.R if len(A[r]) == 0]
        if infeasible:
            raise ValueError(f"Regions with empty eligibility set A_r: {infeasible}")


@dataclass
class CFLPSolution:
    status: int
    obj: Optional[float]
    x: Dict[Site, float]
    y: Dict[Arc, float]
    total_cost: Optional[float]
    total_latency_proxy: Optional[float]
    total_co2: Optional[float]
    total_water: Optional[float]


def build_baseline_model(
    inst: CFLPInstance,
    *,
    model_name: str = "cflp_baseline",
    output_flag: int = 0,
) -> Tuple[gp.Model, gp.tupledict, gp.tupledict]:
    """
    Builds the baseline CFLP model:
      min Σ (F+O)x + φ Σ c y
      s.t. demand, capacity, bounds
    Returns (model, x_vars, y_vars).
    """
    inst.validate()
    A = inst.eligibility_sets()
    arcs = inst.eligible_arcs()

    m = gp.Model(model_name)
    m.Params.OutputFlag = output_flag

    # Variables
    x = m.addVars(inst.I, vtype=GRB.BINARY, name="x")
    y = m.addVars(arcs, lb=0.0, vtype=GRB.CONTINUOUS, name="y")

    # Objective
    fixed_and_oper = gp.quicksum((inst.F[i] + inst.O[i]) * x[i] for i in inst.I)
    latency_proxy = gp.quicksum(inst.c[(i, r)] * y[(i, r)] for (i, r) in arcs)
    m.setObjective(fixed_and_oper + inst.phi * latency_proxy, GRB.MINIMIZE)

    # Demand satisfaction
    for r in inst.R:
        m.addConstr(gp.quicksum(y[(i, r)] for i in A[r]) == inst.d[r], name=f"demand[{r}]")

    # Capacity constraints
    for i in inst.I:
        m.addConstr(gp.quicksum(y[(i, r)] for r in inst.R if (i, r) in y) <= inst.C[i] * x[i],
                    name=f"cap[{i}]")

    return m, x, y


def add_usage_caps(
    m: gp.Model,
    inst: CFLPInstance,
    y: gp.tupledict,
    *,
    gamma_co2: float,
    gamma_w: float,
) -> Dict[str, gp.Constr]:
    """
    Adds usage-based sustainability caps:
      Σ e_i y_{ir} <= Γ_CO2
      Σ w_i y_{ir} <= Γ_W
    """
    arcs: Iterable[Arc] = y.keys()

    co2_expr = gp.quicksum(inst.e_co2[i] * y[(i, r)] for (i, r) in arcs)
    w_expr = gp.quicksum(inst.w[i] * y[(i, r)] for (i, r) in arcs)

    c1 = m.addConstr(co2_expr <= gamma_co2, name="cap_co2")
    c2 = m.addConstr(w_expr <= gamma_w, name="cap_water")
    return {"cap_co2": c1, "cap_water": c2}


def set_scalarized_objective(
    m: gp.Model,
    inst: CFLPInstance,
    x: gp.tupledict,
    y: gp.tupledict,
    *,
    lambda_c: float,
    lambda_w: float,
) -> None:
    """
    Replaces objective with the scalarized version:
      Σ (F+O)x + φ Σ c y + λC Σ e y + λW Σ w y
    """
    arcs: Iterable[Arc] = y.keys()

    fixed_and_oper = gp.quicksum((inst.F[i] + inst.O[i]) * x[i] for i in inst.I)
    latency_proxy = gp.quicksum(inst.c[(i, r)] * y[(i, r)] for (i, r) in arcs)
    co2_term = gp.quicksum(inst.e_co2[i] * y[(i, r)] for (i, r) in arcs)
    w_term = gp.quicksum(inst.w[i] * y[(i, r)] for (i, r) in arcs)

    m.setObjective(
        fixed_and_oper + inst.phi * latency_proxy + lambda_c * co2_term + lambda_w * w_term,
        GRB.MINIMIZE,
    )


def solve_and_extract(
    m: gp.Model,
    inst: CFLPInstance,
    x: gp.tupledict,
    y: gp.tupledict,
    *,
    time_limit_s: Optional[float] = None,
    mip_gap: Optional[float] = None,
) -> CFLPSolution:
    if time_limit_s is not None:
        m.Params.TimeLimit = time_limit_s
    if mip_gap is not None:
        m.Params.MIPGap = mip_gap

    m.optimize()

    status = m.Status
    if status not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
        return CFLPSolution(
            status=status,
            obj=None,
            x={i: 0.0 for i in inst.I},
            y={(i, r): 0.0 for (i, r) in y.keys()},
            total_cost=None,
            total_latency_proxy=None,
            total_co2=None,
            total_water=None,
        )

    x_sol = {i: float(x[i].X) for i in inst.I}
    y_sol = {(i, r): float(y[(i, r)].X) for (i, r) in y.keys()}

    # KPI breakdown (computed from solution)
    total_cost = sum((inst.F[i] + inst.O[i]) * x_sol[i] for i in inst.I)
    total_latency_proxy = sum(inst.c[(i, r)] * y_sol[(i, r)] for (i, r) in y_sol)
    total_co2 = sum(inst.e_co2[i] * y_sol[(i, r)] for (i, r) in y_sol)
    total_water = sum(inst.w[i] * y_sol[(i, r)] for (i, r) in y_sol)

    return CFLPSolution(
        status=status,
        obj=float(m.ObjVal),
        x=x_sol,
        y=y_sol,
        total_cost=total_cost,
        total_latency_proxy=total_latency_proxy,
        total_co2=total_co2,
        total_water=total_water,
    )


# -----------------------------
# Convenience wrappers for the 3 model variants
# -----------------------------
def solve_baseline(
    inst: CFLPInstance,
    *,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
) -> CFLPSolution:
    m, x, y = build_baseline_model(inst, model_name="baseline", output_flag=output_flag)
    return solve_and_extract(m, inst, x, y, time_limit_s=time_limit_s)


def solve_capped_impact(
    inst: CFLPInstance,
    *,
    gamma_co2: float,
    gamma_w: float,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
) -> CFLPSolution:
    m, x, y = build_baseline_model(inst, model_name="capped_impact", output_flag=output_flag)
    add_usage_caps(m, inst, y, gamma_co2=gamma_co2, gamma_w=gamma_w)
    return solve_and_extract(m, inst, x, y, time_limit_s=time_limit_s)


def solve_scalarized(
    inst: CFLPInstance,
    *,
    lambda_c: float,
    lambda_w: float,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
) -> CFLPSolution:
    m, x, y = build_baseline_model(inst, model_name="scalarized", output_flag=output_flag)
    set_scalarized_objective(m, inst, x, y, lambda_c=lambda_c, lambda_w=lambda_w)
    return solve_and_extract(m, inst, x, y, time_limit_s=time_limit_s)


def pareto_scan_scalarized(
    inst: CFLPInstance,
    lambda_grid: List[Tuple[float, float]],
    *,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
) -> List[Tuple[float, float, float, float]]:
    """
    Runs scalarized model over a grid of (lambda_c, lambda_w).
    Returns list of tuples:
      (obj, total_cost, total_co2, total_water)
    """
    results = []
    for (lc, lw) in lambda_grid:
        sol = solve_scalarized(inst, lambda_c=lc, lambda_w=lw, output_flag=output_flag, time_limit_s=time_limit_s)
        results.append((sol.obj if sol.obj is not None else float("nan"),
                        sol.total_cost if sol.total_cost is not None else float("nan"),
                        sol.total_co2 if sol.total_co2 is not None else float("nan"),
                        sol.total_water if sol.total_water is not None else float("nan")))
    return results


# -----------------------------
# Toy instance generator (optional, but useful for your Numerical analysis section)
# -----------------------------
def make_toy_instance(
    *,
    n_sites: int = 10,
    n_regions: int = 8,
    seed: int = 1,
    phi: float = 0.0,
) -> CFLPInstance:
    """
    Generates a small synthetic instance:
      - random 2D coordinates for sites and regions
      - c_{ir} = Euclidean distance (acts as latency proxy)
      - eligibility via Lmax[r] chosen so each region has multiple eligible sites
      - random costs/capacities/demands and sustainability factors
    """
    rng = random.Random(seed)

    I = [f"S{i+1}" for i in range(n_sites)]
    R = [f"R{j+1}" for j in range(n_regions)]

    site_xy = {i: (rng.random(), rng.random()) for i in I}
    reg_xy = {r: (rng.random(), rng.random()) for r in R}

    def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    c: Dict[Arc, float] = {(i, r): dist(site_xy[i], reg_xy[r]) for i in I for r in R}

    # Demands (units) and capacities
    d = {r: rng.uniform(40, 90) for r in R}
    total_demand = sum(d.values())
    # Ensure total capacity is at least 1.2x total demand (with some margin)
    # Distribute capacity across sites with some variation
    avg_capacity_per_site = total_demand * 1.2 / n_sites
    C = {i: rng.uniform(0.8, 1.4) * avg_capacity_per_site for i in I}

    # Costs (scaled)
    F = {i: rng.uniform(200, 500) for i in I}
    O = {i: rng.uniform(50, 150) for i in I}

    # Sustainability factors per unit served (site-specific)
    # (interpretation: lower is better; you can tie these to "grid mix" scenarios if desired)
    e_co2 = {i: rng.uniform(0.2, 0.9) for i in I}
    w = {i: rng.uniform(0.1, 0.6) for i in I}

    # Eligibility thresholds: choose Lmax[r] as a quantile of distances so each region has eligible sites
    Lmax = {}
    for r in R:
        dists = sorted(c[(i, r)] for i in I)
        # pick threshold around the 60th percentile (ensures several eligible sites)
        idx = max(1, int(0.6 * (len(dists) - 1)))
        Lmax[r] = dists[idx]

    inst = CFLPInstance(I=I, R=R, F=F, O=O, C=C, d=d, c=c, Lmax=Lmax, e_co2=e_co2, w=w, phi=phi)
    inst.validate()
    return inst


# -----------------------------
# Example usage (optional)
# -----------------------------
if __name__ == "__main__":
    inst = make_toy_instance(n_sites=10, n_regions=8, seed=3, phi=10.0)

    # Baseline
    sol0 = solve_baseline(inst, output_flag=1)
    print("Baseline:", sol0.obj, sol0.total_cost, sol0.total_co2, sol0.total_water)

    # Capped-impact (caps chosen relative to baseline)
    gamma_co2 = 0.85 * (sol0.total_co2 or 0.0)
    gamma_w = 0.85 * (sol0.total_water or 0.0)
    sol1 = solve_capped_impact(inst, gamma_co2=gamma_co2, gamma_w=gamma_w, output_flag=1)
    print("Capped:", sol1.obj, sol1.total_cost, sol1.total_co2, sol1.total_water)

    # Scalarized scan
    grid = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0), (50.0, 50.0)]
    pts = pareto_scan_scalarized(inst, grid, output_flag=0)
    for (lc_lw, p) in zip(grid, pts):
        print("lambda", lc_lw, "->", p)
