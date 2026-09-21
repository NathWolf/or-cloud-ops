"""Hierarchical strategic-operational cloud planning model.

The model is a two-stage MILP. First-stage decisions choose sites,
committed capacity, and workload-specific interconnection eligibility.
Second-stage recourse assigns workload demand by site, region, time period,
workload type, and scenario.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Any
from pathlib import Path
import csv
import math
import random

import gurobipy as gp
from gurobipy import GRB


Site = str
Region = str
Period = str
Workload = str
Scenario = str

LinkKey = Tuple[Site, Region, Workload]
FlowKey = Tuple[Site, Region, Period, Workload, Scenario]
DemandKey = Tuple[Region, Period, Workload, Scenario]
FactorKey = Tuple[Site, Period, Scenario]


WORKLOAD_INFERENCE = "inf"
WORKLOAD_TRAINING = "train"


@dataclass(frozen=True)
class HierarchicalCloudInstance:
    I: List[Site]
    R: List[Region]
    T: List[Period]
    K: List[Workload]
    Omega: List[Scenario]
    prob: Dict[Scenario, float]
    fixed_cost: Dict[Site, float]
    capacity_cost: Dict[Site, float]
    max_capacity: Dict[Site, float]
    interconnect_cost: Dict[LinkKey, float]
    variable_cost: Dict[FactorKey, float]
    latency: Dict[Tuple[Site, Region], float]
    demand: Dict[DemandKey, float]
    eligible: Dict[LinkKey, bool]
    e_location: Dict[FactorKey, float]
    e_market: Dict[FactorKey, float]
    water: Dict[FactorKey, float]
    existing_sites: List[Site]
    latency_weight: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def active_links(self) -> List[LinkKey]:
        return [
            (i, r, k)
            for i in self.I
            for r in self.R
            for k in self.K
            if self.eligible.get((i, r, k), False)
        ]

    def active_flows(self) -> List[FlowKey]:
        return [
            (i, r, t, k, omega)
            for (i, r, k) in self.active_links()
            for t in self.T
            for omega in self.Omega
        ]

    def validate(self) -> None:
        prob_sum = sum(self.prob.values())
        if not math.isclose(prob_sum, 1.0, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError(f"Scenario probabilities must sum to 1, got {prob_sum}")

        for i in self.I:
            for data, name in [
                (self.fixed_cost, "fixed_cost"),
                (self.capacity_cost, "capacity_cost"),
                (self.max_capacity, "max_capacity"),
            ]:
                if i not in data:
                    raise ValueError(f"Missing {name}[{i}]")

        for omega in self.Omega:
            if omega not in self.prob:
                raise ValueError(f"Missing probability for scenario {omega}")

        for i in self.I:
            for r in self.R:
                if (i, r) not in self.latency:
                    raise ValueError(f"Missing latency for {(i, r)}")
                for k in self.K:
                    if (i, r, k) not in self.eligible:
                        raise ValueError(f"Missing eligibility for {(i, r, k)}")
                    if self.eligible[(i, r, k)] and (i, r, k) not in self.interconnect_cost:
                        raise ValueError(f"Missing interconnect cost for {(i, r, k)}")

        for r in self.R:
            for k in self.K:
                if not any(self.eligible.get((i, r, k), False) for i in self.I):
                    raise ValueError(f"No eligible site for region/workload {(r, k)}")

        for r in self.R:
            for t in self.T:
                for k in self.K:
                    for omega in self.Omega:
                        key = (r, t, k, omega)
                        if key not in self.demand:
                            raise ValueError(f"Missing demand for {key}")

        for i in self.I:
            for t in self.T:
                for omega in self.Omega:
                    key = (i, t, omega)
                    for data, name in [
                        (self.variable_cost, "variable_cost"),
                        (self.e_location, "e_location"),
                        (self.e_market, "e_market"),
                        (self.water, "water"),
                    ]:
                        if key not in data:
                            raise ValueError(f"Missing {name} for {key}")


@dataclass
class HierarchicalCloudSolution:
    status: int
    obj: Optional[float]
    x: Dict[Site, float]
    capacity: Dict[Site, float]
    g: Dict[LinkKey, float]
    y: Dict[FlowKey, float]
    total_first_stage_cost: Optional[float]
    expected_operating_cost: Optional[float]
    expected_latency_proxy: Optional[float]
    expected_co2: Optional[float]
    expected_water: Optional[float]
    period_co2: Dict[Period, float]
    period_water: Dict[Period, float]
    scenario_co2: Dict[Scenario, float]
    scenario_water: Dict[Scenario, float]
    params: Dict[str, Any]


def _factor(
    inst: HierarchicalCloudInstance,
    source: Dict[FactorKey, float],
    i: Site,
    t: Period,
    omega: Scenario,
    *,
    annual: bool,
) -> float:
    if not annual:
        return source[(i, t, omega)]
    return sum(source[(i, tt, omega)] for tt in inst.T) / len(inst.T)


def emission_factor(
    inst: HierarchicalCloudInstance,
    i: Site,
    t: Period,
    omega: Scenario,
    accounting_mode: str,
) -> float:
    """Return the CO2 factor under an accounting convention."""
    mode = accounting_mode.lower()
    if mode not in {
        "location_time",
        "location_annual",
        "market_time",
        "market_annual",
    }:
        raise ValueError(f"Unknown accounting_mode: {accounting_mode}")
    source = inst.e_market if mode.startswith("market") else inst.e_location
    annual = mode.endswith("annual")
    return _factor(inst, source, i, t, omega, annual=annual)


def water_factor(
    inst: HierarchicalCloudInstance,
    i: Site,
    t: Period,
    omega: Scenario,
) -> float:
    return inst.water[(i, t, omega)]


def _prob(inst: HierarchicalCloudInstance, omega: Scenario) -> float:
    return inst.prob[omega]


def build_hierarchical_model(
    inst: HierarchicalCloudInstance,
    *,
    model_name: str = "hierarchical_cloud",
    output_flag: int = 0,
    accounting_mode: str = "location_time",
    gamma_co2: Optional[float] = None,
    gamma_w_by_period: Optional[Dict[Period, float]] = None,
    lambda_c: float = 0.0,
    lambda_w: float = 0.0,
    interconnect_cost_multiplier: float = 1.0,
) -> Tuple[gp.Model, gp.tupledict, gp.tupledict, gp.tupledict, gp.tupledict, Dict[str, Any]]:
    """Build the two-stage strategic-operational MILP."""
    inst.validate()

    links = inst.active_links()
    flows = inst.active_flows()

    m = gp.Model(model_name)
    m.Params.OutputFlag = output_flag
    m.Params.Threads = 1
    m.Params.Seed = 11
    m.Params.DualReductions = 0

    x = m.addVars(inst.I, vtype=GRB.BINARY, name="x")
    cap = m.addVars(inst.I, lb=0.0, vtype=GRB.CONTINUOUS, name="K")
    g = m.addVars(links, vtype=GRB.BINARY, name="g")
    y = m.addVars(flows, lb=0.0, vtype=GRB.CONTINUOUS, name="y")

    constraints: Dict[str, Any] = {}

    for i in inst.existing_sites:
        if i in inst.I:
            m.addConstr(x[i] == 1, name=f"existing_site[{i}]")

    for i in inst.I:
        m.addConstr(cap[i] <= inst.max_capacity[i] * x[i], name=f"capacity_commit[{i}]")

    for (i, r, k) in links:
        m.addConstr(g[(i, r, k)] <= x[i], name=f"link_requires_site[{i},{r},{k}]")

    for r in inst.R:
        for t in inst.T:
            for k in inst.K:
                for omega in inst.Omega:
                    eligible_sites = [
                        i for i in inst.I if inst.eligible.get((i, r, k), False)
                    ]
                    m.addConstr(
                        gp.quicksum(y[(i, r, t, k, omega)] for i in eligible_sites)
                        == inst.demand[(r, t, k, omega)],
                        name=f"demand[{r},{t},{k},{omega}]",
                    )

    for (i, r, k) in links:
        for t in inst.T:
            for omega in inst.Omega:
                m.addConstr(
                    y[(i, r, t, k, omega)] <= inst.demand[(r, t, k, omega)] * g[(i, r, k)],
                    name=f"flow_requires_link[{i},{r},{t},{k},{omega}]",
                )

    for i in inst.I:
        for t in inst.T:
            for omega in inst.Omega:
                m.addConstr(
                    gp.quicksum(
                        y[(i, r, t, k, omega)]
                        for r in inst.R
                        for k in inst.K
                        if inst.eligible.get((i, r, k), False)
                    )
                    <= cap[i],
                    name=f"operating_capacity[{i},{t},{omega}]",
                )

    first_stage_cost = (
        gp.quicksum(inst.fixed_cost[i] * x[i] + inst.capacity_cost[i] * cap[i] for i in inst.I)
        + interconnect_cost_multiplier
        * gp.quicksum(inst.interconnect_cost[(i, r, k)] * g[(i, r, k)] for (i, r, k) in links)
    )
    expected_operating_cost = gp.quicksum(
        _prob(inst, omega)
        * inst.variable_cost[(i, t, omega)]
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )
    expected_latency_proxy = gp.quicksum(
        _prob(inst, omega)
        * inst.latency_weight
        * inst.latency[(i, r)]
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
        if k == WORKLOAD_INFERENCE
    )
    expected_co2 = gp.quicksum(
        _prob(inst, omega)
        * emission_factor(inst, i, t, omega, accounting_mode)
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )
    expected_water = gp.quicksum(
        _prob(inst, omega)
        * water_factor(inst, i, t, omega)
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )

    if gamma_co2 is not None:
        constraints["carbon_cap"] = m.addConstr(expected_co2 <= gamma_co2, name="carbon_cap")

    water_caps = {}
    if gamma_w_by_period is not None:
        for t in inst.T:
            if t not in gamma_w_by_period:
                raise ValueError(f"Missing water cap for period {t}")
            water_expr_t = gp.quicksum(
                _prob(inst, omega)
                * water_factor(inst, i, t, omega)
                * y[(i, r, t, k, omega)]
                for (i, r, tt, k, omega) in flows
                if tt == t
            )
            water_caps[t] = m.addConstr(water_expr_t <= gamma_w_by_period[t], name=f"water_cap[{t}]")
    constraints["water_caps"] = water_caps

    m.setObjective(
        first_stage_cost
        + expected_operating_cost
        + expected_latency_proxy
        + lambda_c * expected_co2
        + lambda_w * expected_water,
        GRB.MINIMIZE,
    )

    expressions = {
        "first_stage_cost": first_stage_cost,
        "expected_operating_cost": expected_operating_cost,
        "expected_latency_proxy": expected_latency_proxy,
        "expected_co2": expected_co2,
        "expected_water": expected_water,
    }
    constraints["expressions"] = expressions
    return m, x, cap, g, y, constraints


def solve_and_extract(
    inst: HierarchicalCloudInstance,
    m: gp.Model,
    x: gp.tupledict,
    cap: gp.tupledict,
    g: gp.tupledict,
    y: gp.tupledict,
    *,
    accounting_mode: str,
    params: Optional[Dict[str, Any]] = None,
    time_limit_s: Optional[float] = None,
    mip_gap: Optional[float] = None,
) -> HierarchicalCloudSolution:
    if time_limit_s is not None:
        m.Params.TimeLimit = time_limit_s
    if mip_gap is not None:
        m.Params.MIPGap = mip_gap

    m.optimize()
    status = m.Status
    params = dict(params or {})
    params["accounting_mode"] = accounting_mode
    params.update(runtime_s=float(m.Runtime), num_variables=m.NumVars,
                  num_constraints=m.NumConstrs, solution_count=m.SolCount,
                  objective_bound=float(m.ObjBound) if m.IsMIP else None,
                  mip_gap=float(m.MIPGap) if m.IsMIP and m.SolCount else None)

    if m.SolCount == 0:
        return HierarchicalCloudSolution(
            status=status,
            obj=None,
            x={i: 0.0 for i in inst.I},
            capacity={i: 0.0 for i in inst.I},
            g={link: 0.0 for link in inst.active_links()},
            y={flow: 0.0 for flow in inst.active_flows()},
            total_first_stage_cost=None,
            expected_operating_cost=None,
            expected_latency_proxy=None,
            expected_co2=None,
            expected_water=None,
            period_co2={t: 0.0 for t in inst.T},
            period_water={t: 0.0 for t in inst.T},
            scenario_co2={omega: 0.0 for omega in inst.Omega},
            scenario_water={omega: 0.0 for omega in inst.Omega},
            params=params,
        )

    x_sol = {i: float(x[i].X) for i in inst.I}
    cap_sol = {i: float(cap[i].X) for i in inst.I}
    g_sol = {link: float(g[link].X) for link in inst.active_links()}
    y_sol = {flow: float(y[flow].X) for flow in inst.active_flows()}

    total_first_stage_cost = sum(
        inst.fixed_cost[i] * x_sol[i] + inst.capacity_cost[i] * cap_sol[i] for i in inst.I
    )
    interconnect_multiplier = float(params.get("interconnect_cost_multiplier", 1.0))
    total_first_stage_cost += interconnect_multiplier * sum(
        inst.interconnect_cost[link] * g_sol[link] for link in inst.active_links()
    )

    expected_operating_cost = sum(
        _prob(inst, omega) * inst.variable_cost[(i, t, omega)] * value
        for (i, r, t, k, omega), value in y_sol.items()
    )
    expected_latency_proxy = sum(
        _prob(inst, omega) * inst.latency_weight * inst.latency[(i, r)] * value
        for (i, r, t, k, omega), value in y_sol.items()
        if k == WORKLOAD_INFERENCE
    )
    expected_co2 = sum(
        _prob(inst, omega)
        * emission_factor(inst, i, t, omega, accounting_mode)
        * value
        for (i, r, t, k, omega), value in y_sol.items()
    )
    expected_water = sum(
        _prob(inst, omega) * water_factor(inst, i, t, omega) * value
        for (i, r, t, k, omega), value in y_sol.items()
    )

    period_co2 = {
        t: sum(
            _prob(inst, omega)
            * emission_factor(inst, i, t, omega, accounting_mode)
            * value
            for (i, r, tt, k, omega), value in y_sol.items()
            if tt == t
        )
        for t in inst.T
    }
    period_water = {
        t: sum(
            _prob(inst, omega) * water_factor(inst, i, t, omega) * value
            for (i, r, tt, k, omega), value in y_sol.items()
            if tt == t
        )
        for t in inst.T
    }
    scenario_co2 = {
        omega: sum(
            emission_factor(inst, i, t, omega, accounting_mode) * value
            for (i, r, t, k, ww), value in y_sol.items()
            if ww == omega
        )
        for omega in inst.Omega
    }
    scenario_water = {
        omega: sum(
            water_factor(inst, i, t, omega) * value
            for (i, r, t, k, ww), value in y_sol.items()
            if ww == omega
        )
        for omega in inst.Omega
    }

    return HierarchicalCloudSolution(
        status=status,
        obj=float(m.ObjVal),
        x=x_sol,
        capacity=cap_sol,
        g=g_sol,
        y=y_sol,
        total_first_stage_cost=total_first_stage_cost,
        expected_operating_cost=expected_operating_cost,
        expected_latency_proxy=expected_latency_proxy,
        expected_co2=expected_co2,
        expected_water=expected_water,
        period_co2=period_co2,
        period_water=period_water,
        scenario_co2=scenario_co2,
        scenario_water=scenario_water,
        params=params,
    )


def solve_hierarchical_baseline(
    inst: HierarchicalCloudInstance,
    *,
    accounting_mode: str = "location_time",
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    mip_gap: Optional[float] = None,
    interconnect_cost_multiplier: float = 1.0,
) -> HierarchicalCloudSolution:
    m, x, cap, g, y, _ = build_hierarchical_model(
        inst,
        model_name="hierarchical_baseline",
        accounting_mode=accounting_mode,
        output_flag=output_flag,
        interconnect_cost_multiplier=interconnect_cost_multiplier,
    )
    return solve_and_extract(
        inst,
        m,
        x,
        cap,
        g,
        y,
        accounting_mode=accounting_mode,
        time_limit_s=time_limit_s,
        mip_gap=mip_gap,
        params={
            "variant": "baseline",
            "interconnect_cost_multiplier": interconnect_cost_multiplier,
        },
    )


def solve_hierarchical_capped(
    inst: HierarchicalCloudInstance,
    *,
    gamma_co2: Optional[float] = None,
    gamma_w_by_period: Optional[Dict[Period, float]] = None,
    accounting_mode: str = "location_time",
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    mip_gap: Optional[float] = None,
    interconnect_cost_multiplier: float = 1.0,
) -> HierarchicalCloudSolution:
    m, x, cap, g, y, _ = build_hierarchical_model(
        inst,
        model_name="hierarchical_capped",
        accounting_mode=accounting_mode,
        gamma_co2=gamma_co2,
        gamma_w_by_period=gamma_w_by_period,
        output_flag=output_flag,
        interconnect_cost_multiplier=interconnect_cost_multiplier,
    )
    return solve_and_extract(
        inst,
        m,
        x,
        cap,
        g,
        y,
        accounting_mode=accounting_mode,
        time_limit_s=time_limit_s,
        mip_gap=mip_gap,
        params={
            "variant": "capped",
            "gamma_co2": gamma_co2,
            "gamma_w_by_period": gamma_w_by_period,
            "interconnect_cost_multiplier": interconnect_cost_multiplier,
        },
    )


def solve_hierarchical_priced(
    inst: HierarchicalCloudInstance,
    *,
    lambda_c: float,
    lambda_w: float,
    accounting_mode: str = "location_time",
    output_flag: int = 0,
    time_limit_s: Optional[float] = None,
    mip_gap: Optional[float] = None,
    interconnect_cost_multiplier: float = 1.0,
) -> HierarchicalCloudSolution:
    m, x, cap, g, y, _ = build_hierarchical_model(
        inst,
        model_name="hierarchical_priced",
        accounting_mode=accounting_mode,
        lambda_c=lambda_c,
        lambda_w=lambda_w,
        output_flag=output_flag,
        interconnect_cost_multiplier=interconnect_cost_multiplier,
    )
    return solve_and_extract(
        inst,
        m,
        x,
        cap,
        g,
        y,
        accounting_mode=accounting_mode,
        time_limit_s=time_limit_s,
        mip_gap=mip_gap,
        params={
            "variant": "priced",
            "lambda_c": lambda_c,
            "lambda_w": lambda_w,
            "interconnect_cost_multiplier": interconnect_cost_multiplier,
        },
    )


def solve_fixed_plan_recourse_lp_for_duals(
    inst: HierarchicalCloudInstance,
    plan: HierarchicalCloudSolution,
    *,
    gamma_co2: Optional[float],
    gamma_w_by_period: Optional[Dict[Period, float]],
    accounting_mode: str = "location_time",
    output_flag: int = 0,
) -> Dict[str, Any]:
    """Solve a continuous recourse LP under fixed integer/capacity decisions.

    Gurobi does not provide meaningful MILP duals. This LP fixes the upstream
    plan and reports local shadow prices for the downstream allocation problem.
    For a minimization model with <= caps, we return -Pi so a positive value
    means the objective increases when the cap is tightened by one unit.
    """
    inst.validate()
    active_links = [link for link, value in plan.g.items() if value > 0.5]
    active_link_set = set(active_links)
    flows = [
        (i, r, t, k, omega)
        for (i, r, k) in active_links
        for t in inst.T
        for omega in inst.Omega
    ]

    m = gp.Model("fixed_plan_recourse_lp")
    m.Params.OutputFlag = output_flag
    m.Params.Threads = 1
    y = m.addVars(flows, lb=0.0, vtype=GRB.CONTINUOUS, name="y")

    for r in inst.R:
        for t in inst.T:
            for k in inst.K:
                for omega in inst.Omega:
                    eligible_sites = [
                        i for i in inst.I if (i, r, k) in active_link_set
                    ]
                    m.addConstr(
                        gp.quicksum(y[(i, r, t, k, omega)] for i in eligible_sites)
                        == inst.demand[(r, t, k, omega)],
                        name=f"demand[{r},{t},{k},{omega}]",
                    )

    for i in inst.I:
        for t in inst.T:
            for omega in inst.Omega:
                m.addConstr(
                    gp.quicksum(
                        y[(i, r, t, k, omega)]
                        for r in inst.R
                        for k in inst.K
                        if (i, r, k) in active_link_set
                    )
                    <= plan.capacity.get(i, 0.0),
                    name=f"fixed_capacity[{i},{t},{omega}]",
                )

    expected_operating_cost = gp.quicksum(
        _prob(inst, omega)
        * inst.variable_cost[(i, t, omega)]
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )
    expected_latency_proxy = gp.quicksum(
        _prob(inst, omega)
        * inst.latency_weight
        * inst.latency[(i, r)]
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
        if k == WORKLOAD_INFERENCE
    )
    expected_co2 = gp.quicksum(
        _prob(inst, omega)
        * emission_factor(inst, i, t, omega, accounting_mode)
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )
    expected_water = gp.quicksum(
        _prob(inst, omega)
        * water_factor(inst, i, t, omega)
        * y[(i, r, t, k, omega)]
        for (i, r, t, k, omega) in flows
    )

    carbon_constr = None
    if gamma_co2 is not None:
        carbon_constr = m.addConstr(expected_co2 <= gamma_co2, name="carbon_cap")

    water_constrs = {}
    if gamma_w_by_period is not None:
        for t in inst.T:
            expr_t = gp.quicksum(
                _prob(inst, omega)
                * water_factor(inst, i, t, omega)
                * y[(i, r, t, k, omega)]
                for (i, r, tt, k, omega) in flows
                if tt == t
            )
            water_constrs[t] = m.addConstr(expr_t <= gamma_w_by_period[t], name=f"water_cap[{t}]")

    m.setObjective(expected_operating_cost + expected_latency_proxy, GRB.MINIMIZE)
    m.optimize()

    result: Dict[str, Any] = {
        "status": m.Status,
        "obj": float(m.ObjVal) if m.Status == GRB.OPTIMAL else None,
        "carbon_shadow_price": None,
        "carbon_slack": None,
        "water_shadow_prices": {},
        "water_slacks": {},
        "expected_co2": None,
        "expected_water": None,
        "period_water": {},
    }
    if m.Status != GRB.OPTIMAL:
        return result

    result["expected_co2"] = float(expected_co2.getValue())
    result["expected_water"] = float(expected_water.getValue())
    if carbon_constr is not None:
        result["carbon_shadow_price"] = float(-carbon_constr.Pi)
        result["carbon_slack"] = float(carbon_constr.Slack)
    for t, constr in water_constrs.items():
        result["water_shadow_prices"][t] = float(-constr.Pi)
        result["water_slacks"][t] = float(constr.Slack)
        result["period_water"][t] = gamma_w_by_period[t] - float(constr.Slack)
    return result


def make_synthetic_hierarchical_instance(
    *,
    seed: int = 11,
    quick: bool = False,
) -> HierarchicalCloudInstance:
    """Create a deterministic synthetic stress-test instance.

    The values are not empirical. They are constructed to create trade-offs
    between cheap incumbent capacity and cleaner expansion/interconnection
    choices under time-varying carbon and water factors.
    """
    rng = random.Random(seed)

    n_existing = 3 if quick else 4
    n_new = 3 if quick else 4
    n_regions = 4 if quick else 6
    I = [f"C{i + 1}" for i in range(n_existing)] + [f"S{i + 1}" for i in range(n_new)]
    R = [f"R{j + 1}" for j in range(n_regions)]
    T = ["winter", "summer"] if quick else ["winter", "spring", "summer", "autumn"]
    K = [WORKLOAD_INFERENCE, WORKLOAD_TRAINING]
    Omega = ["base"] if quick else ["low", "base", "high"]
    prob = {"base": 1.0} if quick else {"low": 0.25, "base": 0.50, "high": 0.25}

    site_xy = {i: (rng.random(), rng.random()) for i in I}
    region_xy = {r: (rng.random(), rng.random()) for r in R}

    def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    latency = {(i, r): dist(site_xy[i], region_xy[r]) for i in I for r in R}

    eligible: Dict[LinkKey, bool] = {}
    for r in R:
        ordered_sites = sorted(I, key=lambda i: latency[(i, r)])
        inf_count = max(3, int(math.ceil(0.55 * len(I))))
        train_count = max(inf_count, int(math.ceil(0.85 * len(I))))
        inf_sites = set(ordered_sites[:inf_count])
        train_sites = set(ordered_sites[:train_count])
        for i in I:
            eligible[(i, r, WORKLOAD_INFERENCE)] = i in inf_sites
            eligible[(i, r, WORKLOAD_TRAINING)] = i in train_sites

    fixed_cost: Dict[Site, float] = {}
    capacity_cost: Dict[Site, float] = {}
    max_capacity: Dict[Site, float] = {}
    base_e: Dict[Site, float] = {}
    base_w: Dict[Site, float] = {}
    market_multiplier: Dict[Site, float] = {}

    for idx, i in enumerate(I):
        if i.startswith("C"):
            fixed_cost[i] = 0.0
            capacity_cost[i] = 5.4 + 0.45 * idx
            max_capacity[i] = 105.0 + 8.0 * (idx % 2)
            base_e[i] = [0.76, 0.68, 0.56, 0.48][idx % 4]
            base_w[i] = [0.26, 0.33, 0.54, 0.43][idx % 4]
            market_multiplier[i] = [0.78, 0.88, 0.70, 0.82][idx % 4]
        else:
            j = int(i[1:]) - 1
            fixed_cost[i] = 240.0 + 35.0 * j
            capacity_cost[i] = 8.8 + 0.55 * j
            max_capacity[i] = 128.0 + 9.0 * (j % 2)
            base_e[i] = [0.24, 0.18, 0.31, 0.27][j % 4]
            base_w[i] = [0.49, 0.22, 0.35, 0.19][j % 4]
            market_multiplier[i] = [0.42, 0.35, 0.58, 0.45][j % 4]

    interconnect_cost: Dict[LinkKey, float] = {}
    for i in I:
        for r in R:
            for k in K:
                if eligible[(i, r, k)]:
                    workload_mult = 1.25 if k == WORKLOAD_INFERENCE else 0.75
                    interconnect_cost[(i, r, k)] = (
                        18.0 + 24.0 * latency[(i, r)]
                    ) * workload_mult

    scenario_multiplier = {"low": 0.90, "base": 1.0, "high": 1.16}
    seasonal_demand = {"winter": 1.00, "spring": 1.04, "summer": 1.12, "autumn": 0.98}
    seasonal_grid = {"winter": 1.08, "spring": 0.92, "summer": 1.18, "autumn": 0.96}
    seasonal_water = {"winter": 0.82, "spring": 0.96, "summer": 1.32, "autumn": 1.00}

    if quick:
        scenario_multiplier = {"base": 1.0}

    region_base = {r: 44.0 + 6.0 * idx + rng.uniform(-3.0, 3.0) for idx, r in enumerate(R)}
    inference_share = {r: 0.32 + 0.04 * (idx % 3) for idx, r in enumerate(R)}

    demand: Dict[DemandKey, float] = {}
    for r in R:
        for t in T:
            for omega in Omega:
                total = region_base[r] * seasonal_demand[t] * scenario_multiplier[omega]
                demand[(r, t, WORKLOAD_INFERENCE, omega)] = total * inference_share[r]
                demand[(r, t, WORKLOAD_TRAINING, omega)] = total * (1.0 - inference_share[r])

    variable_cost: Dict[FactorKey, float] = {}
    e_location: Dict[FactorKey, float] = {}
    e_market: Dict[FactorKey, float] = {}
    water: Dict[FactorKey, float] = {}
    for i in I:
        for t in T:
            for omega in Omega:
                dirty_scenario = 1.0 + (scenario_multiplier[omega] - 1.0) * 0.35
                variable_cost[(i, t, omega)] = 1.1 + 0.08 * I.index(i) + 0.15 * seasonal_demand[t]
                e_location[(i, t, omega)] = base_e[i] * seasonal_grid[t] * dirty_scenario
                e_market[(i, t, omega)] = max(0.04, e_location[(i, t, omega)] * market_multiplier[i])
                water[(i, t, omega)] = base_w[i] * seasonal_water[t] * (1.0 + 0.10 * (omega == "high"))

    return HierarchicalCloudInstance(
        I=I,
        R=R,
        T=T,
        K=K,
        Omega=Omega,
        prob=prob,
        fixed_cost=fixed_cost,
        capacity_cost=capacity_cost,
        max_capacity=max_capacity,
        interconnect_cost=interconnect_cost,
        variable_cost=variable_cost,
        latency=latency,
        demand=demand,
        eligible=eligible,
        e_location=e_location,
        e_market=e_market,
        water=water,
        existing_sites=[i for i in I if i.startswith("C")],
        latency_weight=5.0,
        metadata={"calibration_status": "legacy_synthetic"},
    )


def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    h = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * radius_km * math.asin(math.sqrt(h))


def make_public_calibrated_hierarchical_instance(
    *,
    seed: int = 11,
    quick: bool = False,
    calibration_status: str = "public_proxy",
    carbon_data_path: Optional[str] = None,
) -> HierarchicalCloudInstance:
    """Create a European planning instance with optional public carbon inputs.

    A supplied carbon_data_path loads national annual generation factors.
    Geography and eligibility use representative cities and distance screening.
    Seasonality, water, demand, cost, capacity and interconnection remain
    constructed assumptions, even when the annual carbon factors are public.
    """
    rng = random.Random(seed)

    site_info = {
        "C1": {"country": "France", "city": "Paris", "lat": 48.8566, "lon": 2.3522},
        "C2": {"country": "Germany", "city": "Frankfurt", "lat": 50.1109, "lon": 8.6821},
        "C3": {"country": "Netherlands", "city": "Amsterdam", "lat": 52.3676, "lon": 4.9041},
        "C4": {"country": "Ireland", "city": "Dublin", "lat": 53.3498, "lon": -6.2603},
        "S1": {"country": "Sweden", "city": "Stockholm", "lat": 59.3293, "lon": 18.0686},
        "S2": {"country": "Poland", "city": "Warsaw", "lat": 52.2297, "lon": 21.0122},
        "S3": {"country": "Spain", "city": "Madrid", "lat": 40.4168, "lon": -3.7038},
        "S4": {"country": "Finland", "city": "Helsinki", "lat": 60.1699, "lon": 24.9384},
    }
    region_info = {
        "R1": {"city": "Paris", "lat": 48.8566, "lon": 2.3522},
        "R2": {"city": "Frankfurt", "lat": 50.1109, "lon": 8.6821},
        "R3": {"city": "Amsterdam", "lat": 52.3676, "lon": 4.9041},
        "R4": {"city": "Dublin", "lat": 53.3498, "lon": -6.2603},
        "R5": {"city": "Madrid", "lat": 40.4168, "lon": -3.7038},
        "R6": {"city": "Stockholm", "lat": 59.3293, "lon": 18.0686},
    }

    I = ["C1", "C2", "C3", "C4", "S1", "S2", "S3", "S4"]
    R = ["R1", "R2", "R3", "R4", "R5", "R6"]
    if quick:
        I = ["C1", "C2", "C3", "S1", "S3"]
        R = ["R1", "R2", "R3", "R5"]
    T = ["winter", "summer"] if quick else ["winter", "spring", "summer", "autumn"]
    K = [WORKLOAD_INFERENCE, WORKLOAD_TRAINING]
    Omega = ["base"] if quick else ["low", "base", "high"]
    prob = {"base": 1.0} if quick else {"low": 0.25, "base": 0.50, "high": 0.25}

    distance_km = {
        (i, r): _haversine_km(
            (site_info[i]["lat"], site_info[i]["lon"]),
            (region_info[r]["lat"], region_info[r]["lon"]),
        )
        for i in I
        for r in R
    }
    latency = {(i, r): distance_km[(i, r)] / 1000.0 for i in I for r in R}

    eligible: Dict[LinkKey, bool] = {}
    for i in I:
        for r in R:
            d = distance_km[(i, r)]
            eligible[(i, r, WORKLOAD_INFERENCE)] = d <= 900.0
            eligible[(i, r, WORKLOAD_TRAINING)] = d <= 2200.0

    fixed_cost = {
        "C1": 0.0,
        "C2": 0.0,
        "C3": 0.0,
        "C4": 0.0,
        "S1": 270.0,
        "S2": 230.0,
        "S3": 255.0,
        "S4": 285.0,
    }
    capacity_cost = {
        "C1": 5.8,
        "C2": 6.1,
        "C3": 6.0,
        "C4": 6.4,
        "S1": 8.9,
        "S2": 8.1,
        "S3": 8.5,
        "S4": 9.2,
    }
    max_capacity = {
        "C1": 108.0,
        "C2": 116.0,
        "C3": 112.0,
        "C4": 104.0,
        "S1": 132.0,
        "S2": 126.0,
        "S3": 128.0,
        "S4": 134.0,
    }
    proxy_e = {
        "C1": 0.36,
        "C2": 0.62,
        "C3": 0.53,
        "C4": 0.46,
        "S1": 0.18,
        "S2": 0.74,
        "S3": 0.34,
        "S4": 0.20,
    }
    proxy_w = {
        "C1": 0.31,
        "C2": 0.36,
        "C3": 0.50,
        "C4": 0.42,
        "S1": 0.23,
        "S2": 0.40,
        "S3": 0.58,
        "S4": 0.21,
    }
    # Only label data as calibrated after verified values have actually been read.
    carbon_rows = {}
    if carbon_data_path is not None:
        with Path(carbon_data_path).open(newline="") as stream:
            carbon_rows = {row["country"]: row for row in csv.DictReader(stream)}
        for i in I:
            row = carbon_rows[site_info[i]["country"]]
            if row["unit"] != "gCO2/kWh" or int(row["year"]) != 2024:
                raise ValueError("Expected Ember 2024 carbon intensity in gCO2/kWh")
            proxy_e[i] = float(row["value"]) / 1000.0
        calibration_status = "public_carbon_with_synthetic_operations"
    elif calibration_status != "public_proxy":
        raise ValueError("Public calibration requires carbon_data_path")
    market_multiplier = {
        "C1": 0.74,
        "C2": 0.78,
        "C3": 0.76,
        "C4": 0.72,
        "S1": 0.42,
        "S2": 0.70,
        "S3": 0.55,
        "S4": 0.40,
    }
    if quick:
        fixed_cost = {i: fixed_cost[i] for i in I}
        capacity_cost = {i: capacity_cost[i] for i in I}
        max_capacity = {i: max_capacity[i] for i in I}

    interconnect_cost: Dict[LinkKey, float] = {}
    for i in I:
        for r in R:
            for k in K:
                if eligible[(i, r, k)]:
                    workload_mult = 1.25 if k == WORKLOAD_INFERENCE else 0.72
                    interconnect_cost[(i, r, k)] = (14.0 + 0.030 * distance_km[(i, r)]) * workload_mult

    scenario_multiplier = {"low": 0.90, "base": 1.0, "high": 1.16}
    if quick:
        scenario_multiplier = {"base": 1.0}
    seasonal_demand = {"winter": 1.00, "spring": 1.04, "summer": 1.12, "autumn": 0.98}
    seasonal_grid = {"winter": 1.10, "spring": 0.91, "summer": 1.16, "autumn": 0.96}
    # Equal-duration representative periods: the base-scenario mean must
    # reproduce the source annual factor, not inflate it by 3.25 percent.
    grid_mean = sum(seasonal_grid[t] for t in T) / len(T)
    seasonal_grid = {t: seasonal_grid[t] / grid_mean for t in T}
    seasonal_water = {"winter": 0.84, "spring": 0.96, "summer": 1.34, "autumn": 1.00}

    region_base = {"R1": 48.0, "R2": 54.0, "R3": 50.0, "R4": 42.0, "R5": 58.0, "R6": 46.0}
    inference_share = {"R1": 0.38, "R2": 0.36, "R3": 0.34, "R4": 0.32, "R5": 0.37, "R6": 0.35}
    if quick:
        region_base = {r: region_base[r] for r in R}
        inference_share = {r: inference_share[r] for r in R}

    demand: Dict[DemandKey, float] = {}
    for r in R:
        for t in T:
            for omega in Omega:
                noise = 1.0 + rng.uniform(-0.015, 0.015)
                total = region_base[r] * seasonal_demand[t] * scenario_multiplier[omega] * noise
                demand[(r, t, WORKLOAD_INFERENCE, omega)] = total * inference_share[r]
                demand[(r, t, WORKLOAD_TRAINING, omega)] = total * (1.0 - inference_share[r])

    variable_cost: Dict[FactorKey, float] = {}
    e_location: Dict[FactorKey, float] = {}
    e_market: Dict[FactorKey, float] = {}
    water: Dict[FactorKey, float] = {}
    for i in I:
        for t in T:
            for omega in Omega:
                scenario_grid = 1.0 + (scenario_multiplier[omega] - 1.0) * 0.35
                variable_cost[(i, t, omega)] = 1.00 + 0.05 * I.index(i) + 0.00018 * min(
                    distance_km[(i, r)] for r in R
                )
                e_location[(i, t, omega)] = proxy_e[i] * seasonal_grid[t] * scenario_grid
                e_market[(i, t, omega)] = e_location[(i, t, omega)] * market_multiplier[i]
                water[(i, t, omega)] = proxy_w[i] * seasonal_water[t] * (1.0 + 0.10 * (omega == "high"))

    metadata = {
        "calibration_status": calibration_status,
        "carbon_source_rows": carbon_rows,
        "carbon_boundary": "Electricity-generation lifecycle intensity; not a Scope 2 inventory",
        "service_unit": "Normalized compute bundle assumed to use 1 kWh facility electricity",
        "basis": "public_carbon_with_synthetic_operations" if carbon_rows else "public_proxy",
        "site_info": {i: site_info[i] for i in I},
        "region_info": {r: region_info[r] for r in R},
        "eligibility_threshold_km": {
            WORKLOAD_INFERENCE: 900.0,
            WORKLOAD_TRAINING: 2200.0,
        },
        "proxy_note": (
            "Geography uses representative city locations. Annual carbon factors "
            "are source-derived only when carbon_source_rows is nonempty. "
            "Seasonality, procurement discounts, water, demand, cost, capacity "
            "and interconnection values are constructed assumptions."
        ),
    }

    return HierarchicalCloudInstance(
        I=I,
        R=R,
        T=T,
        K=K,
        Omega=Omega,
        prob=prob,
        fixed_cost=fixed_cost,
        capacity_cost=capacity_cost,
        max_capacity=max_capacity,
        interconnect_cost=interconnect_cost,
        variable_cost=variable_cost,
        latency=latency,
        demand=demand,
        eligible=eligible,
        e_location=e_location,
        e_market=e_market,
        water=water,
        existing_sites=[i for i in I if i.startswith("C")],
        latency_weight=5.0,
        metadata=metadata,
    )


def _join_key(key: Iterable[str]) -> str:
    return "|".join(key)


def _split_key(key: str) -> Tuple[str, ...]:
    return tuple(key.split("|"))


def instance_to_dict(inst: HierarchicalCloudInstance) -> Dict[str, Any]:
    return {
        "I": inst.I,
        "R": inst.R,
        "T": inst.T,
        "K": inst.K,
        "Omega": inst.Omega,
        "prob": inst.prob,
        "fixed_cost": inst.fixed_cost,
        "capacity_cost": inst.capacity_cost,
        "max_capacity": inst.max_capacity,
        "interconnect_cost": {_join_key(k): v for k, v in inst.interconnect_cost.items()},
        "variable_cost": {_join_key(k): v for k, v in inst.variable_cost.items()},
        "latency": {_join_key(k): v for k, v in inst.latency.items()},
        "demand": {_join_key(k): v for k, v in inst.demand.items()},
        "eligible": {_join_key(k): v for k, v in inst.eligible.items()},
        "e_location": {_join_key(k): v for k, v in inst.e_location.items()},
        "e_market": {_join_key(k): v for k, v in inst.e_market.items()},
        "water": {_join_key(k): v for k, v in inst.water.items()},
        "existing_sites": inst.existing_sites,
        "latency_weight": inst.latency_weight,
        "metadata": inst.metadata,
    }


def instance_from_dict(data: Dict[str, Any]) -> HierarchicalCloudInstance:
    return HierarchicalCloudInstance(
        I=data["I"],
        R=data["R"],
        T=data["T"],
        K=data["K"],
        Omega=data["Omega"],
        prob={k: float(v) for k, v in data["prob"].items()},
        fixed_cost={k: float(v) for k, v in data["fixed_cost"].items()},
        capacity_cost={k: float(v) for k, v in data["capacity_cost"].items()},
        max_capacity={k: float(v) for k, v in data["max_capacity"].items()},
        interconnect_cost={_split_key(k): float(v) for k, v in data["interconnect_cost"].items()},
        variable_cost={_split_key(k): float(v) for k, v in data["variable_cost"].items()},
        latency={_split_key(k): float(v) for k, v in data["latency"].items()},
        demand={_split_key(k): float(v) for k, v in data["demand"].items()},
        eligible={_split_key(k): bool(v) for k, v in data["eligible"].items()},
        e_location={_split_key(k): float(v) for k, v in data["e_location"].items()},
        e_market={_split_key(k): float(v) for k, v in data["e_market"].items()},
        water={_split_key(k): float(v) for k, v in data["water"].items()},
        existing_sites=data["existing_sites"],
        latency_weight=float(data.get("latency_weight", 0.0)),
        metadata=data.get("metadata", {}),
    )


def solution_to_dict(sol: HierarchicalCloudSolution) -> Dict[str, Any]:
    return {
        "status": sol.status,
        "obj": sol.obj,
        "x": sol.x,
        "capacity": sol.capacity,
        "g": {_join_key(k): v for k, v in sol.g.items() if abs(v) > 1e-9},
        "y": {_join_key(k): v for k, v in sol.y.items() if abs(v) > 1e-9},
        "total_first_stage_cost": sol.total_first_stage_cost,
        "expected_operating_cost": sol.expected_operating_cost,
        "expected_latency_proxy": sol.expected_latency_proxy,
        "expected_co2": sol.expected_co2,
        "expected_water": sol.expected_water,
        "period_co2": sol.period_co2,
        "period_water": sol.period_water,
        "scenario_co2": sol.scenario_co2,
        "scenario_water": sol.scenario_water,
        "params": sol.params,
    }


def solution_from_dict(data: Dict[str, Any], inst: HierarchicalCloudInstance) -> HierarchicalCloudSolution:
    g = {link: 0.0 for link in inst.active_links()}
    for key, value in data.get("g", {}).items():
        g[_split_key(key)] = float(value)
    y = {flow: 0.0 for flow in inst.active_flows()}
    for key, value in data.get("y", {}).items():
        y[_split_key(key)] = float(value)
    return HierarchicalCloudSolution(
        status=int(data["status"]),
        obj=data.get("obj"),
        x={k: float(v) for k, v in data.get("x", {}).items()},
        capacity={k: float(v) for k, v in data.get("capacity", {}).items()},
        g=g,
        y=y,
        total_first_stage_cost=data.get("total_first_stage_cost"),
        expected_operating_cost=data.get("expected_operating_cost"),
        expected_latency_proxy=data.get("expected_latency_proxy"),
        expected_co2=data.get("expected_co2"),
        expected_water=data.get("expected_water"),
        period_co2={k: float(v) for k, v in data.get("period_co2", {}).items()},
        period_water={k: float(v) for k, v in data.get("period_water", {}).items()},
        scenario_co2={k: float(v) for k, v in data.get("scenario_co2", {}).items()},
        scenario_water={k: float(v) for k, v in data.get("scenario_water", {}).items()},
        params=data.get("params", {}),
    )
