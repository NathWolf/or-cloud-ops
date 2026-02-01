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

    # Costs and capacity (required fields first)
    F: Dict[Site, float]          # fixed (or annualized) open cost
    O: Dict[Site, float]          # operating cost if opened (same basis as objective)
    C: Dict[Site, float]          # capacity
    c: Dict[Arc, float]           # latency/distance (defined for all i,r)
    e_co2: Dict[Site, float]      # kgCO2e per unit served (or consistent unit)
    w: Dict[Site, float]          # water per unit served (or consistent unit)

    # Optional fields (must come after required fields)
    P: Optional[Dict[Site, float]] = None  # power envelope (MW) per site
    d: Optional[Dict[Region, float]] = None  # total demand (for backward compatibility)
    d_inf: Optional[Dict[Region, float]] = None  # inference demand (latency-sensitive)
    d_train: Optional[Dict[Region, float]] = None  # training demand (flexible/batch)
    Lmax: Optional[Dict[Region, float]] = None  # eligibility threshold per region (for backward compatibility)
    Lmax_inf: Optional[Dict[Region, float]] = None  # tight eligibility for inference
    Lmax_train: Optional[Dict[Region, float]] = None  # loose eligibility for training
    phi: float = 0.0              # latency penalty weight (0 removes proxy cost)

    def eligible_arcs(self, demand_type: str = "inf") -> List[Arc]:
        """Get eligible arcs for a demand type. demand_type can be 'inf', 'train', or 'all'."""
        arcs: List[Arc] = []
        for r in self.R:
            for i in self.I:
                if demand_type == "inf" and self.Lmax_inf:
                    if self.c[(i, r)] <= self.Lmax_inf[r]:
                        arcs.append((i, r))
                elif demand_type == "train" and self.Lmax_train:
                    if self.c[(i, r)] <= self.Lmax_train[r]:
                        arcs.append((i, r))
                elif demand_type == "all" and self.Lmax:
                    if self.c[(i, r)] <= self.Lmax[r]:
                        arcs.append((i, r))
        return arcs

    def eligibility_sets(self, demand_type: str = "inf") -> Dict[Region, List[Site]]:
        """Get eligibility sets for a demand type. demand_type can be 'inf', 'train', or 'all'."""
        A: Dict[Region, List[Site]] = {r: [] for r in self.R}
        for r in self.R:
            for i in self.I:
                if demand_type == "inf" and self.Lmax_inf:
                    if self.c[(i, r)] <= self.Lmax_inf[r]:
                        A[r].append(i)
                elif demand_type == "train" and self.Lmax_train:
                    if self.c[(i, r)] <= self.Lmax_train[r]:
                        A[r].append(i)
                elif demand_type == "all" and self.Lmax:
                    if self.c[(i, r)] <= self.Lmax[r]:
                        A[r].append(i)
        return A
    
    def has_split_demand(self) -> bool:
        """Check if instance uses split demand (inference/training)."""
        return self.d_inf is not None and self.d_train is not None
    
    def get_total_demand(self) -> Dict[Region, float]:
        """Get total demand per region (either from d or d_inf + d_train)."""
        if self.d is not None:
            return self.d
        elif self.d_inf is not None and self.d_train is not None:
            return {r: self.d_inf.get(r, 0) + self.d_train.get(r, 0) for r in self.R}
        else:
            raise ValueError("No demand data available")

    def validate(self) -> None:
        # Check required keys exist
        for i in self.I:
            if i not in self.F or i not in self.O or i not in self.C:
                raise ValueError(f"Missing F/O/C for site {i}")
            if i not in self.e_co2 or i not in self.w:
                raise ValueError(f"Missing e_co2/w for site {i}")
        
        # Check demand (either single or split)
        if not self.has_split_demand():
            if self.d is None:
                raise ValueError("Must provide either d or (d_inf, d_train)")
            for r in self.R:
                if r not in self.d:
                    raise ValueError(f"Missing d for region {r}")
        else:
            for r in self.R:
                if r not in self.d_inf or r not in self.d_train:
                    raise ValueError(f"Missing d_inf or d_train for region {r}")
        
        # Check eligibility thresholds
        if not self.has_split_demand():
            if self.Lmax is None:
                raise ValueError("Must provide Lmax when using single demand")
            for r in self.R:
                if r not in self.Lmax:
                    raise ValueError(f"Missing Lmax for region {r}")
        else:
            if self.Lmax_inf is None or self.Lmax_train is None:
                raise ValueError("Must provide Lmax_inf and Lmax_train when using split demand")
            for r in self.R:
                if r not in self.Lmax_inf or r not in self.Lmax_train:
                    raise ValueError(f"Missing Lmax_inf or Lmax_train for region {r}")
        
        for i in self.I:
            for r in self.R:
                if (i, r) not in self.c:
                    raise ValueError(f"Missing c[(i,r)] for {(i,r)}")

        # Ensure each region has at least one eligible site
        if self.has_split_demand():
            A_inf = self.eligibility_sets("inf")
            A_train = self.eligibility_sets("train")
            infeasible_inf = [r for r in self.R if len(A_inf[r]) == 0]
            infeasible_train = [r for r in self.R if len(A_train[r]) == 0]
            if infeasible_inf:
                raise ValueError(f"Regions with empty inference eligibility set: {infeasible_inf}")
            if infeasible_train:
                raise ValueError(f"Regions with empty training eligibility set: {infeasible_train}")
        else:
            A = self.eligibility_sets("all")
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
    existing_sites: Optional[List[Site]] = None,
) -> Tuple[gp.Model, gp.tupledict, gp.tupledict, Optional[gp.tupledict]]:
    """
    Builds the baseline CFLP model:
      min Σ (F+O)x + φ Σ c y
      s.t. demand, capacity, bounds
      + optionally: x[i] = 1 for existing_sites
    
    Supports both single demand and split demand (inference/training).
    Returns (model, x_vars, y_vars, y_train_vars).
    If split demand, y_vars is for inference flows, y_train_vars for training flows.
    If single demand, y_train_vars is None.
    """
    inst.validate()
    
    m = gp.Model(model_name)
    m.Params.OutputFlag = output_flag

    # Variables
    x = m.addVars(inst.I, vtype=GRB.BINARY, name="x")
    
    if inst.has_split_demand():
        # Split demand: separate flows for inference and training
        A_inf = inst.eligibility_sets("inf")
        A_train = inst.eligibility_sets("train")
        arcs_inf = inst.eligible_arcs("inf")
        arcs_train = inst.eligible_arcs("train")
        
        y_inf = m.addVars(arcs_inf, lb=0.0, vtype=GRB.CONTINUOUS, name="y_inf")
        y_train = m.addVars(arcs_train, lb=0.0, vtype=GRB.CONTINUOUS, name="y_train")
        
        # Fix certain sites to be always open
        if existing_sites:
            for i in existing_sites:
                if i in inst.I:
                    m.addConstr(x[i] == 1, name=f"fix_site[{i}]")
        
        # Objective (latency proxy only for inference flows)
        fixed_and_oper = gp.quicksum((inst.F[i] + inst.O[i]) * x[i] for i in inst.I)
        latency_proxy = gp.quicksum(inst.c[(i, r)] * y_inf[(i, r)] for (i, r) in arcs_inf)
        m.setObjective(fixed_and_oper + inst.phi * latency_proxy, GRB.MINIMIZE)
        
        # Demand satisfaction (separate for inference and training)
        for r in inst.R:
            m.addConstr(gp.quicksum(y_inf[(i, r)] for i in A_inf[r] if (i, r) in y_inf) == inst.d_inf[r], 
                       name=f"demand_inf[{r}]")
            m.addConstr(gp.quicksum(y_train[(i, r)] for i in A_train[r] if (i, r) in y_train) == inst.d_train[r], 
                       name=f"demand_train[{r}]")
        
        # Capacity constraints (total flows)
        for i in inst.I:
            total_flow = gp.quicksum(y_inf[(i, r)] for r in inst.R if (i, r) in y_inf)
            total_flow += gp.quicksum(y_train[(i, r)] for r in inst.R if (i, r) in y_train)
            m.addConstr(total_flow <= inst.C[i] * x[i], name=f"cap[{i}]")
        
        return m, x, y_inf, y_train
    else:
        # Single demand (backward compatibility)
        A = inst.eligibility_sets("all")
        arcs = inst.eligible_arcs("all")
        y = m.addVars(arcs, lb=0.0, vtype=GRB.CONTINUOUS, name="y")
        
        # Fix certain sites to be always open
        if existing_sites:
            for i in existing_sites:
                if i in inst.I:
                    m.addConstr(x[i] == 1, name=f"fix_site[{i}]")
        
        # Objective
        fixed_and_oper = gp.quicksum((inst.F[i] + inst.O[i]) * x[i] for i in inst.I)
        latency_proxy = gp.quicksum(inst.c[(i, r)] * y[(i, r)] for (i, r) in arcs)
        m.setObjective(fixed_and_oper + inst.phi * latency_proxy, GRB.MINIMIZE)
        
        # Demand satisfaction
        for r in inst.R:
            m.addConstr(gp.quicksum(y[(i, r)] for i in A[r] if (i, r) in y) == inst.d[r], name=f"demand[{r}]")
        
        # Capacity constraints
        for i in inst.I:
            m.addConstr(gp.quicksum(y[(i, r)] for r in inst.R if (i, r) in y) <= inst.C[i] * x[i],
                        name=f"cap[{i}]")
        
        return m, x, y, None


def add_usage_caps(
    m: gp.Model,
    inst: CFLPInstance,
    y: gp.tupledict,
    y_train: Optional[gp.tupledict] = None,
    *,
    gamma_co2: float,
    gamma_w: float,
) -> Dict[str, gp.Constr]:
    """
    Adds usage-based sustainability caps:
      Σ e_i (y_{ir} + y_train_{ir}) <= Γ_CO2
      Σ w_i (y_{ir} + y_train_{ir}) <= Γ_W
    
    If y_train is None, only uses y (single demand case).
    """
    arcs: Iterable[Arc] = y.keys()
    
    # CO2 expression (inference flows)
    co2_expr = gp.quicksum(inst.e_co2[i] * y[(i, r)] for (i, r) in arcs)
    # Add training flows if present
    if y_train is not None:
        arcs_train: Iterable[Arc] = y_train.keys()
        co2_expr += gp.quicksum(inst.e_co2[i] * y_train[(i, r)] for (i, r) in arcs_train)
    
    # Water expression (inference flows)
    w_expr = gp.quicksum(inst.w[i] * y[(i, r)] for (i, r) in arcs)
    # Add training flows if present
    if y_train is not None:
        arcs_train: Iterable[Arc] = y_train.keys()
        w_expr += gp.quicksum(inst.w[i] * y_train[(i, r)] for (i, r) in arcs_train)

    c1 = m.addConstr(co2_expr <= gamma_co2, name="cap_co2")
    c2 = m.addConstr(w_expr <= gamma_w, name="cap_water")
    return {"cap_co2": c1, "cap_water": c2}


def set_scalarized_objective(
    m: gp.Model,
    inst: CFLPInstance,
    x: gp.tupledict,
    y: gp.tupledict,
    y_train: Optional[gp.tupledict] = None,
    *,
    lambda_c: float,
    lambda_w: float,
) -> None:
    """
    Replaces objective with the scalarized version:
      Σ (F+O)x + φ Σ c y_inf + λC Σ e (y_inf + y_train) + λW Σ w (y_inf + y_train)
    
    If y_train is None, only uses y (single demand case).
    """
    arcs: Iterable[Arc] = y.keys()

    fixed_and_oper = gp.quicksum((inst.F[i] + inst.O[i]) * x[i] for i in inst.I)
    # Latency proxy only for inference flows
    latency_proxy = gp.quicksum(inst.c[(i, r)] * y[(i, r)] for (i, r) in arcs)
    
    # CO2 and water terms include both inference and training flows
    co2_term = gp.quicksum(inst.e_co2[i] * y[(i, r)] for (i, r) in arcs)
    w_term = gp.quicksum(inst.w[i] * y[(i, r)] for (i, r) in arcs)
    
    if y_train is not None:
        arcs_train: Iterable[Arc] = y_train.keys()
        co2_term += gp.quicksum(inst.e_co2[i] * y_train[(i, r)] for (i, r) in arcs_train)
        w_term += gp.quicksum(inst.w[i] * y_train[(i, r)] for (i, r) in arcs_train)

    m.setObjective(
        fixed_and_oper + inst.phi * latency_proxy + lambda_c * co2_term + lambda_w * w_term,
        GRB.MINIMIZE,
    )


def solve_and_extract(
    m: gp.Model,
    inst: CFLPInstance,
    x: gp.tupledict,
    y: gp.tupledict,
    y_train: Optional[gp.tupledict] = None,
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
        y_sol = {(i, r): 0.0 for (i, r) in y.keys()}
        if y_train is not None:
            # Merge training flows into y_sol for backward compatibility
            for (i, r) in y_train.keys():
                y_sol[(i, r)] = 0.0
        return CFLPSolution(
            status=status,
            obj=None,
            x={i: 0.0 for i in inst.I},
            y=y_sol,
            total_cost=None,
            total_latency_proxy=None,
            total_co2=None,
            total_water=None,
        )

    x_sol = {i: float(x[i].X) for i in inst.I}
    y_sol = {(i, r): float(y[(i, r)].X) for (i, r) in y.keys()}
    
    # Merge training flows into y_sol if present (for backward compatibility)
    if y_train is not None:
        for (i, r) in y_train.keys():
            if (i, r) in y_sol:
                y_sol[(i, r)] += float(y_train[(i, r)].X)
            else:
                y_sol[(i, r)] = float(y_train[(i, r)].X)

    # KPI breakdown (computed from solution)
    total_cost = sum((inst.F[i] + inst.O[i]) * x_sol[i] for i in inst.I)
    # Latency proxy only for inference flows (y, not y_train)
    total_latency_proxy = sum(inst.c[(i, r)] * float(y[(i, r)].X) for (i, r) in y.keys())
    # CO2 and water include both inference and training flows
    total_co2 = sum(inst.e_co2[i] * float(y[(i, r)].X) for (i, r) in y.keys())
    total_water = sum(inst.w[i] * float(y[(i, r)].X) for (i, r) in y.keys())
    if y_train is not None:
        total_co2 += sum(inst.e_co2[i] * float(y_train[(i, r)].X) for (i, r) in y_train.keys())
        total_water += sum(inst.w[i] * float(y_train[(i, r)].X) for (i, r) in y_train.keys())

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
    existing_sites: Optional[List[Site]] = None,
) -> CFLPSolution:
    m, x, y, y_train = build_baseline_model(inst, model_name="baseline", output_flag=output_flag, existing_sites=existing_sites)
    return solve_and_extract(m, inst, x, y, y_train, time_limit_s=time_limit_s)


def solve_capped_impact(
    inst: CFLPInstance,
    *,
    gamma_co2: float,
    gamma_w: float,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    existing_sites: Optional[List[Site]] = None,
) -> CFLPSolution:
    m, x, y, y_train = build_baseline_model(inst, model_name="capped_impact", output_flag=output_flag, existing_sites=existing_sites)
    add_usage_caps(m, inst, y, y_train, gamma_co2=gamma_co2, gamma_w=gamma_w)
    return solve_and_extract(m, inst, x, y, y_train, time_limit_s=time_limit_s)


def solve_scalarized(
    inst: CFLPInstance,
    *,
    lambda_c: float,
    lambda_w: float,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    existing_sites: Optional[List[Site]] = None,
) -> CFLPSolution:
    m, x, y, y_train = build_baseline_model(inst, model_name="scalarized", output_flag=output_flag, existing_sites=existing_sites)
    set_scalarized_objective(m, inst, x, y, y_train, lambda_c=lambda_c, lambda_w=lambda_w)
    return solve_and_extract(m, inst, x, y, y_train, time_limit_s=time_limit_s)


def pareto_scan_scalarized(
    inst: CFLPInstance,
    lambda_grid: List[Tuple[float, float]],
    *,
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    existing_sites: Optional[List[Site]] = None,
) -> List[Tuple[float, float, float, float]]:
    """
    Runs scalarized model over a grid of (lambda_c, lambda_w).
    Returns list of tuples:
      (obj, total_cost, total_co2, total_water)
    """
    results = []
    for (lc, lw) in lambda_grid:
        sol = solve_scalarized(inst, lambda_c=lc, lambda_w=lw, output_flag=output_flag, time_limit_s=time_limit_s, existing_sites=existing_sites)
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
    use_split_demand: bool = True,
) -> CFLPInstance:
    """
    Generates a small synthetic instance:
      - random 2D coordinates for sites and regions
      - c_{ir} = Euclidean distance (acts as latency proxy)
      - eligibility via Lmax[r] chosen so each region has multiple eligible sites
      - random costs/capacities/demands and sustainability factors
    
    If use_split_demand=True (default), generates split demand (inference/training)
    with two eligibility sets (tight for inference, loose for training).
    """
    rng = random.Random(seed)

    # Generate sites: C1-C5 for fixed (existing) sites, S1-S5 for potential (expansion) sites
    # For n_sites=10: 5 fixed (C1-C5) + 5 potential (S1-S5)
    n_fixed = n_sites // 2  # Half are existing sites
    n_potential = n_sites - n_fixed  # Rest are potential sites
    I = [f"C{i+1}" for i in range(n_fixed)] + [f"S{i+1}" for i in range(n_potential)]
    R = [f"R{j+1}" for j in range(n_regions)]

    site_xy = {i: (rng.random(), rng.random()) for i in I}
    reg_xy = {r: (rng.random(), rng.random()) for r in R}

    def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    c: Dict[Arc, float] = {(i, r): dist(site_xy[i], reg_xy[r]) for i in I for r in R}

    # Demands (units) and capacities
    if use_split_demand:
        # Split demand: choose fraction p_r in [0.2, 0.6] for inference
        d_inf = {}
        d_train = {}
        for r in R:
            total_d_r = rng.uniform(40, 90)
            p_r = rng.uniform(0.2, 0.6)
            d_inf[r] = p_r * total_d_r
            d_train[r] = (1 - p_r) * total_d_r
        total_demand = sum(d_inf.values()) + sum(d_train.values())
    else:
        d = {r: rng.uniform(40, 90) for r in R}
        total_demand = sum(d.values())
    
    # Ensure total capacity is at least 1.2x total demand (with some margin)
    # Distribute capacity across sites with some variation
    avg_capacity_per_site = total_demand * 1.2 / n_sites
    C = {i: rng.uniform(0.8, 1.4) * avg_capacity_per_site for i in I}
    
    # Power envelope: set P_i = C_i / alpha_i where alpha_i is conversion factor
    # Use a reasonable conversion factor (e.g., 0.5-1.0 MW per unit capacity)
    alpha = {i: rng.uniform(0.5, 1.0) for i in I}
    P = {i: C[i] / alpha[i] for i in I}

    # Costs (scaled)
    F = {i: rng.uniform(200, 500) for i in I}
    O = {i: rng.uniform(50, 150) for i in I}

    # Sustainability factors per unit served (site-specific)
    # (interpretation: lower is better; you can tie these to "grid mix" scenarios if desired)
    e_co2 = {i: rng.uniform(0.2, 0.9) for i in I}
    w = {i: rng.uniform(0.1, 0.6) for i in I}

    # Eligibility thresholds
    if use_split_demand:
        # Tight eligibility for inference (30-40% of sites)
        Lmax_inf = {}
        for r in R:
            dists = sorted(c[(i, r)] for i in I)
            # pick threshold around the 30-40th percentile (tight)
            pct = rng.uniform(0.3, 0.4)
            idx = max(1, int(pct * (len(dists) - 1)))
            Lmax_inf[r] = dists[idx]
        
        # Loose eligibility for training (60-80% of sites)
        Lmax_train = {}
        for r in R:
            dists = sorted(c[(i, r)] for i in I)
            # pick threshold around the 60-80th percentile (loose)
            pct = rng.uniform(0.6, 0.8)
            idx = max(1, int(pct * (len(dists) - 1)))
            Lmax_train[r] = dists[idx]
        
        inst = CFLPInstance(
            I=I, R=R, F=F, O=O, C=C, P=P,
            d_inf=d_inf, d_train=d_train,
            c=c, Lmax_inf=Lmax_inf, Lmax_train=Lmax_train,
            e_co2=e_co2, w=w, phi=phi
        )
    else:
        # Single eligibility threshold (backward compatibility)
        Lmax = {}
        for r in R:
            dists = sorted(c[(i, r)] for i in I)
            # pick threshold around the 60th percentile (ensures several eligible sites)
            idx = max(1, int(0.6 * (len(dists) - 1)))
            Lmax[r] = dists[idx]
        
        inst = CFLPInstance(
            I=I, R=R, F=F, O=O, C=C, P=P,
            d=d, c=c, Lmax=Lmax,
            e_co2=e_co2, w=w, phi=phi
        )
    
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
