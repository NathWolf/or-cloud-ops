"""Analysis helpers for hierarchical cloud-planning experiments."""

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from src.models.hierarchical import (
    HierarchicalCloudInstance,
    HierarchicalCloudSolution,
    Period,
    Workload,
    WORKLOAD_INFERENCE,
    WORKLOAD_TRAINING,
)


OPTIMAL_STATUS = 2


def economic_cost(sol: HierarchicalCloudSolution) -> Optional[float]:
    """Return economic objective components, excluding internal-price penalties."""
    if (
        sol.total_first_stage_cost is None
        or sol.expected_operating_cost is None
        or sol.expected_latency_proxy is None
    ):
        return None
    return (
        sol.total_first_stage_cost
        + sol.expected_operating_cost
        + sol.expected_latency_proxy
    )


def opened_sites(sol: HierarchicalCloudSolution) -> List[str]:
    return sorted(site for site, value in sol.x.items() if value > 0.5)


def active_links(sol: HierarchicalCloudSolution) -> List[Tuple[str, str, str]]:
    return sorted(link for link, value in sol.g.items() if value > 0.5)


def total_demand(inst: HierarchicalCloudInstance) -> float:
    return sum(inst.prob[omega] * value for (r, t, k, omega), value in inst.demand.items())


def data_construction_rows(inst: HierarchicalCloudInstance) -> List[Dict[str, Any]]:
    status = inst.metadata.get("calibration_status", "public_proxy")
    geography = "European city planning-zone proxy"
    if status == "legacy_synthetic":
        geography = "legacy synthetic labels"
    return [
        {
            "parameter_group": "Candidate sites and demand regions",
            "public_proxy_basis": geography,
            "proxy_or_transformation": "Coded as anonymized site and demand-region identifiers",
            "role_in_model": "Defines site set I, region set R, and geography for eligibility",
        },
        {
            "parameter_group": "Demand by region and workload",
            "public_proxy_basis": "Scaled planning proxy",
            "proxy_or_transformation": "Fixed-seed demand by region, workload, period, and scenario",
            "role_in_model": "Right-hand side of downstream allocation constraints",
        },
        {
            "parameter_group": "Capacity envelope",
            "public_proxy_basis": "Scaled engineering proxy",
            "proxy_or_transformation": "Normalized site capacity and capacity-cost values",
            "role_in_model": "First-stage committed capacity and downstream capacity limits",
        },
        {
            "parameter_group": "Electricity/carbon factors",
            "public_proxy_basis": "Ember 2024 national annual factors" if inst.metadata.get("carbon_source_rows") else "Constructed carbon assumptions",
            "proxy_or_transformation": "Divide gCO2/kWh by 1000; assume 1 kWh per service unit; synthetic seasonal/scenario multipliers. Lifecycle generation boundary, not Scope 2.",
            "role_in_model": "Expected CO2 accounting and carbon-cap constraints",
        },
        {
            "parameter_group": "Water-stress and seasonal water limits",
            "public_proxy_basis": "Constructed direct-water assumptions",
            "proxy_or_transformation": "Assumed litres per normalized unit and seasonal multipliers; no measured water values or basin permits are claimed",
            "role_in_model": "Expected direct-water accounting and seasonal water limits",
        },
        {
            "parameter_group": "Distance/latency eligibility",
            "public_proxy_basis": "Great-circle distance proxy",
            "proxy_or_transformation": "Inference links <= 900 km; training links <= 2200 km",
            "role_in_model": "Candidate eligibility envelope for link-activation variables",
        },
        {
            "parameter_group": "Interconnection activation cost",
            "public_proxy_basis": "Scaled planning proxy",
            "proxy_or_transformation": "Relative link activation cost based on distance and workload class",
            "role_in_model": "First-stage cost for activating eligible links",
        },
        {
            "parameter_group": "Accounting convention",
            "public_proxy_basis": "Scaled accounting proxy",
            "proxy_or_transformation": "Unadjusted generation factors and hypothetical procurement discounts; not certified Scope 2 accounting",
            "role_in_model": "Defines which carbon factors are constrained or priced",
        },
        {
            "parameter_group": "Internal prices",
            "public_proxy_basis": "Governance parameter grid",
            "proxy_or_transformation": "Experimental carbon and water price grid",
            "role_in_model": "Scalarized governance comparison, not compliance guarantee",
        },
    ]


def solution_kpi_row(
    inst: HierarchicalCloudInstance,
    label: str,
    sol: HierarchicalCloudSolution,
    *,
    gamma_co2: Optional[float] = None,
    gamma_w_by_period: Optional[Dict[Period, float]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    demand = total_demand(inst)
    eco_cost = economic_cost(sol)
    row: Dict[str, Any] = {
        "label": label,
        "status": sol.status,
        "objective": sol.obj,
        "economic_cost": eco_cost,
        "first_stage_cost": sol.total_first_stage_cost,
        "operating_cost": sol.expected_operating_cost,
        "latency_proxy": sol.expected_latency_proxy,
        "expected_co2": sol.expected_co2,
        "expected_water": sol.expected_water,
        "co2_intensity": (sol.expected_co2 / demand) if sol.expected_co2 is not None and demand else None,
        "water_intensity": (sol.expected_water / demand) if sol.expected_water is not None and demand else None,
        "opened_sites": ",".join(opened_sites(sol)),
        "num_opened_sites": len(opened_sites(sol)),
        "active_links": len(active_links(sol)),
        "committed_capacity": sum(sol.capacity.values()),
        "accounting_mode": sol.params.get("accounting_mode"),
        "variant": sol.params.get("variant"),
        "gamma_co2": gamma_co2,
        "co2_slack": (gamma_co2 - sol.expected_co2) if gamma_co2 is not None and sol.expected_co2 is not None else None,
        "lambda_c": sol.params.get("lambda_c"),
        "lambda_w": sol.params.get("lambda_w"),
        "interconnect_cost_multiplier": sol.params.get("interconnect_cost_multiplier"),
    }
    if gamma_w_by_period:
        for period, cap in gamma_w_by_period.items():
            used = sol.period_water.get(period)
            row[f"water_cap_{period}"] = cap
            row[f"water_used_{period}"] = used
            row[f"water_slack_{period}"] = cap - used if used is not None else None
        row["binding_water_periods"] = ",".join(
            period
            for period, cap in gamma_w_by_period.items()
            if sol.period_water.get(period) is not None
            and abs(cap - sol.period_water[period]) <= 1e-5
        )
    else:
        row["binding_water_periods"] = ""
    if extra:
        row.update(extra)
    return row


def _water_target_met(sol: HierarchicalCloudSolution, gamma_w_by_period: Dict[Period, float]) -> bool:
    return all(
        sol.period_water.get(period) is not None
        and sol.period_water[period] <= cap + 1e-5
        for period, cap in gamma_w_by_period.items()
    )


def planning_regime_comparison_rows(
    baseline: HierarchicalCloudSolution,
    hard_envelope: HierarchicalCloudSolution,
    internal_price: HierarchicalCloudSolution,
    *,
    gamma_co2: float,
    gamma_w_by_period: Dict[Period, float],
    internal_price_label: str,
) -> List[Dict[str, Any]]:
    def row(
        label: str,
        sol: HierarchicalCloudSolution,
        implication: str,
        *,
        evaluate_targets: bool = True,
    ) -> Dict[str, Any]:
        co2_met = (
            sol.expected_co2 is not None and sol.expected_co2 <= gamma_co2 + 1e-5
        )
        water_met = _water_target_met(sol, gamma_w_by_period)
        if not evaluate_targets:
            co2_display = "not encoded"
            water_display = "not encoded"
        else:
            co2_display = "yes" if co2_met else "no"
            water_display = "yes" if water_met else "no"
        return {
            "regime": label,
            "economic_cost": economic_cost(sol),
            "expected_co2": sol.expected_co2,
            "expected_water": sol.expected_water,
            "co2_target_met": co2_display,
            "water_target_met": water_display,
            "num_opened_sites": len(opened_sites(sol)),
            "active_links": len(active_links(sol)),
            "downstream_implication": implication,
        }

    return [
        row(
            "Cost-only planning",
            baseline,
            "Lowest-cost envelope; sustainability targets not encoded upstream",
            evaluate_targets=False,
        ),
        row(
            "Reporting-only sustainability",
            baseline,
            "Targets checked ex post; replanning required if targets are binding",
        ),
        row(
            "Handoff-contract hard envelope",
            hard_envelope,
            "Targets encoded upstream; downstream allocation inherits feasible envelope",
        ),
        row(
            f"Internal-price planning ({internal_price_label})",
            internal_price,
            "Price response screened ex post; compliance is not guaranteed",
        ),
    ]


def compact_sensitivity_rows(
    accounting_experiments: pd.DataFrame,
    interconnection_experiments: pd.DataFrame,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    accounting = accounting_experiments[
        (accounting_experiments["status"] == OPTIMAL_STATUS)
        & (accounting_experiments["accounting_experiment"] == "cap_85")
    ]
    for _, r in accounting.iterrows():
        rows.append(
            {
                "sensitivity": f"Accounting: {r['accounting_mode']}",
                "economic_cost": r["economic_cost"],
                "expected_co2": r["expected_co2"],
                "expected_water": r["expected_water"],
                "active_links": r["active_links"],
            }
        )
    interconnection = interconnection_experiments[
        interconnection_experiments["status"] == OPTIMAL_STATUS
    ]
    for _, r in interconnection.iterrows():
        rows.append(
            {
                "sensitivity": f"Interconnection x{r['interconnect_cost_multiplier']:g}",
                "economic_cost": r["economic_cost"],
                "expected_co2": r["expected_co2"],
                "expected_water": r["expected_water"],
                "active_links": r["active_links"],
            }
        )
    return rows


def site_selection_rows(
    solutions: Dict[str, HierarchicalCloudSolution],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label, sol in solutions.items():
        for site, value in sol.x.items():
            rows.append(
                {
                    "label": label,
                    "site": site,
                    "open": int(value > 0.5),
                    "committed_capacity": sol.capacity.get(site, 0.0),
                }
            )
    return rows


def allocation_by_site_workload_rows(
    inst: HierarchicalCloudInstance,
    solutions: Dict[str, HierarchicalCloudSolution],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label, sol in solutions.items():
        for site in inst.I:
            for workload in inst.K:
                expected_flow = sum(
                    inst.prob[omega] * flow
                    for (i, r, t, k, omega), flow in sol.y.items()
                    if i == site and k == workload
                )
                if abs(expected_flow) > 1e-7:
                    rows.append(
                        {
                            "label": label,
                            "site": site,
                            "workload": workload,
                            "expected_flow": expected_flow,
                        }
                    )
    return rows


def binding_constraint_rows(
    inst: HierarchicalCloudInstance,
    label: str,
    sol: HierarchicalCloudSolution,
    *,
    gamma_co2: Optional[float] = None,
    gamma_w_by_period: Optional[Dict[Period, float]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if gamma_co2 is not None and sol.expected_co2 is not None:
        slack = gamma_co2 - sol.expected_co2
        rows.append(
            {
                "label": label,
                "constraint": "carbon_cap",
                "period": "",
                "cap": gamma_co2,
                "used": sol.expected_co2,
                "slack": slack,
                "binding": abs(slack) <= 1e-5,
            }
        )
    if gamma_w_by_period:
        for period, cap in gamma_w_by_period.items():
            used = sol.period_water.get(period, 0.0)
            slack = cap - used
            rows.append(
                {
                    "label": label,
                    "constraint": "water_cap",
                    "period": period,
                    "cap": cap,
                    "used": used,
                    "slack": slack,
                    "binding": abs(slack) <= 1e-5,
                }
            )
    return rows


def interval_abatement_rows(cap_sweep: pd.DataFrame) -> List[Dict[str, Any]]:
    """Compute finite-difference interval abatement cost rows."""
    valid = cap_sweep[
        (cap_sweep["status"] == OPTIMAL_STATUS)
        & cap_sweep["economic_cost"].notna()
        & cap_sweep["expected_co2"].notna()
    ].copy()
    if valid.empty:
        return []
    valid = valid.sort_values("alpha", ascending=False)
    rows: List[Dict[str, Any]] = []
    previous = None
    for _, current in valid.iterrows():
        if previous is not None:
            delta_cost = current["economic_cost"] - previous["economic_cost"]
            delta_co2 = previous["expected_co2"] - current["expected_co2"]
            iac = delta_cost / delta_co2 if delta_co2 > 1e-7 else None
            rows.append(
                {
                    "from_alpha": previous["alpha"],
                    "to_alpha": current["alpha"],
                    "delta_cost": delta_cost,
                    "delta_co2": delta_co2,
                    "interval_abatement_cost": iac,
                }
            )
        previous = current
    return rows


def nearest_price_equivalence_rows(
    cap_sweep: pd.DataFrame,
    price_sweep: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """For each cap solution, find the internal-price point closest in CO2."""
    cap_valid = cap_sweep[
        (cap_sweep["status"] == OPTIMAL_STATUS) & cap_sweep["expected_co2"].notna()
    ]
    price_valid = price_sweep[
        (price_sweep["status"] == OPTIMAL_STATUS) & price_sweep["expected_co2"].notna()
    ]
    rows: List[Dict[str, Any]] = []
    if cap_valid.empty or price_valid.empty:
        return rows
    for _, cap_row in cap_valid.iterrows():
        diffs = (price_valid["expected_co2"] - cap_row["expected_co2"]).abs()
        idx = diffs.idxmin()
        price_row = price_valid.loc[idx]
        rows.append(
            {
                "alpha": cap_row["alpha"],
                "cap_co2": cap_row["expected_co2"],
                "cap_cost": cap_row["economic_cost"],
                "nearest_lambda_c": price_row["lambda_c"],
                "nearest_lambda_w": price_row["lambda_w"],
                "price_co2": price_row["expected_co2"],
                "price_cost": price_row["economic_cost"],
                "co2_gap": price_row["expected_co2"] - cap_row["expected_co2"],
                "cost_gap": price_row["economic_cost"] - cap_row["economic_cost"],
            }
        )
    return rows


def instance_summary_rows(inst: HierarchicalCloudInstance) -> List[Dict[str, Any]]:
    links_inf = sum(1 for (i, r, k), ok in inst.eligible.items() if ok and k == WORKLOAD_INFERENCE)
    links_train = sum(1 for (i, r, k), ok in inst.eligible.items() if ok and k == WORKLOAD_TRAINING)
    return [
        {"component": "Sites", "value": len(inst.I), "detail": ",".join(inst.I)},
        {"component": "Demand regions", "value": len(inst.R), "detail": ",".join(inst.R)},
        {"component": "Periods", "value": len(inst.T), "detail": ",".join(inst.T)},
        {"component": "Scenarios", "value": len(inst.Omega), "detail": ",".join(inst.Omega)},
        {"component": "Workload types", "value": len(inst.K), "detail": ",".join(inst.K)},
        {"component": "Inference eligible links", "value": links_inf, "detail": "latency-restricted"},
        {"component": "Training eligible links", "value": links_train, "detail": "looser eligibility"},
        {"component": "Expected demand", "value": total_demand(inst), "detail": "scaled service units"},
    ]


def write_csv(path: str, rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    df.to_csv(path, index=False)
    return df
