#!/usr/bin/env python3
"""
Comprehensive analysis script that recomputes all metrics from solution files.
Generates governance outcome tables, MAC tables, flexibility attribution, etc.
"""
import sys
from pathlib import Path
from typing import Optional
import json
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import CFLPInstance, CFLPSolution, solve_scalarized
from src.utils import load_instance, EXISTING_SITES
from src.analysis import compute_binding_constraints, compute_kpis


def load_solution(filepath: str) -> dict:
    """Load a solution from JSON."""
    with open(filepath, "r") as f:
        return json.load(f)


def solution_dict_to_cflp_solution(sol_dict: dict) -> CFLPSolution:
    """Convert solution dictionary to CFLPSolution object."""
    # Parse y dictionary: keys are "i,r" strings
    y = {}
    for key, value in sol_dict.get("y", {}).items():
        if "," in key:
            i, r = key.split(",", 1)
            y[(i, r)] = float(value)
    
    return CFLPSolution(
        status=sol_dict.get("status", 0),
        obj=sol_dict.get("obj"),
        x={k: float(v) for k, v in sol_dict.get("x", {}).items()},
        y=y,
        total_cost=sol_dict.get("total_cost"),
        total_latency_proxy=sol_dict.get("total_latency_proxy"),
        total_co2=sol_dict.get("total_co2"),
        total_water=sol_dict.get("total_water"),
    )


def compute_inference_training_split(
    inst: CFLPInstance,
    sol: CFLPSolution,
) -> dict:
    """
    Estimate inference vs training flows from merged solution.
    
    Since solutions merge y_inf and y_train, we estimate the split:
    - If (i,r) is only in A_inf[r], all flow is inference
    - If (i,r) is only in A_train[r], all flow is training
    - If (i,r) is in both, we need to solve or estimate
    
    For now, we use a heuristic: if flow is <= d_inf[r], assume it's inference;
    otherwise, allocate d_inf[r] to inference and rest to training.
    """
    if not inst.has_split_demand():
        return {
            "co2_inf": sol.total_co2 or 0.0,
            "co2_train": 0.0,
            "water_inf": sol.total_water or 0.0,
            "water_train": 0.0,
        }
    
    A_inf = inst.eligibility_sets("inf")
    A_train = inst.eligibility_sets("train")
    
    co2_inf = 0.0
    co2_train = 0.0
    water_inf = 0.0
    water_train = 0.0
    
    # Track remaining inference demand per region
    remaining_inf_demand = {r: inst.d_inf[r] for r in inst.R}
    
    # First pass: allocate flows that are inference-only or training-only
    for (i, r), flow in sol.y.items():
        if flow < 1e-6:
            continue
        
        is_inf_eligible = i in A_inf[r]
        is_train_eligible = i in A_train[r]
        
        if is_inf_eligible and not is_train_eligible:
            # Inference-only
            co2_inf += inst.e_co2[i] * flow
            water_inf += inst.w[i] * flow
            remaining_inf_demand[r] -= flow
        elif is_train_eligible and not is_inf_eligible:
            # Training-only
            co2_train += inst.e_co2[i] * flow
            water_train += inst.w[i] * flow
        elif is_inf_eligible and is_train_eligible:
            # Both eligible - allocate based on remaining inference demand
            inf_flow = min(flow, max(0, remaining_inf_demand[r]))
            train_flow = flow - inf_flow
            
            co2_inf += inst.e_co2[i] * inf_flow
            water_inf += inst.w[i] * inf_flow
            co2_train += inst.e_co2[i] * train_flow
            water_train += inst.w[i] * train_flow
            
            remaining_inf_demand[r] -= inf_flow
    
    return {
        "co2_inf": co2_inf,
        "co2_train": co2_train,
        "water_inf": water_inf,
        "water_train": water_train,
    }


def compute_governance_kpis(
    inst: CFLPInstance,
    sol: CFLPSolution,
    gamma_co2: Optional[float] = None,
    gamma_w: Optional[float] = None,
) -> dict:
    """Compute comprehensive governance KPIs."""
    # Basic metrics
    opened_sites = [i for i in inst.I if sol.x.get(i, 0.0) > 0.5]
    num_opened = len(opened_sites)
    
    # Existing vs new sites
    existing_opened = [i for i in opened_sites if i in EXISTING_SITES]
    new_opened = [i for i in opened_sites if i not in EXISTING_SITES]
    num_new_sites = len(new_opened)
    
    # Capacity metrics
    opened_capacity = sum(inst.C[i] for i in opened_sites)
    total_demand = sum(inst.get_total_demand().values())
    portfolio_utilization = (total_demand / opened_capacity * 100) if opened_capacity > 0 else 0.0
    
    # Idle existing capacity (capacity minus flow for existing sites)
    idle_existing_capacity = 0.0
    for i in EXISTING_SITES:
        if i in opened_sites:
            total_flow = sum(sol.y.get((i, r), 0.0) for r in inst.R)
            idle_existing_capacity += max(0.0, inst.C[i] - total_flow)
    
    # Intensity metrics
    co2_intensity = (sol.total_co2 / total_demand) if total_demand > 0 else 0.0
    water_intensity = (sol.total_water / total_demand) if total_demand > 0 else 0.0
    
    # Cap utilization
    co2_cap_utilization = None
    water_cap_utilization = None
    if gamma_co2 is not None:
        co2_cap_utilization = (sol.total_co2 / gamma_co2 * 100) if gamma_co2 > 0 else 0.0
    if gamma_w is not None:
        water_cap_utilization = (sol.total_water / gamma_w * 100) if gamma_w > 0 else 0.0
    
    return {
        "total_cost": sol.total_cost or 0.0,
        "total_co2": sol.total_co2 or 0.0,
        "total_water": sol.total_water or 0.0,
        "co2_intensity": co2_intensity,
        "water_intensity": water_intensity,
        "num_opened_sites": num_opened,
        "num_new_sites": num_new_sites,
        "opened_capacity": opened_capacity,
        "portfolio_utilization": portfolio_utilization,
        "idle_existing_capacity": idle_existing_capacity,
        "co2_cap_utilization": co2_cap_utilization,
        "water_cap_utilization": water_cap_utilization,
        "latency_proxy": sol.total_latency_proxy,
    }


def generate_governance_kpi_table(
    inst: CFLPInstance,
    baseline_sol: dict,
    capped_90_sol: dict,
    capped_80_sol: dict,
    scalarized_50_50_sol: dict,
) -> pd.DataFrame:
    """Generate comprehensive governance KPI table."""
    baseline_cflp = solution_dict_to_cflp_solution(baseline_sol)
    capped_90_cflp = solution_dict_to_cflp_solution(capped_90_sol)
    capped_80_cflp = solution_dict_to_cflp_solution(capped_80_sol)
    scalarized_cflp = solution_dict_to_cflp_solution(scalarized_50_50_sol)
    
    rows = []
    
    # Baseline
    kpis_baseline = compute_governance_kpis(inst, baseline_cflp)
    rows.append({
        "Model Variant": "Baseline",
        **kpis_baseline,
    })
    
    # Capped 90%
    gamma_co2_90 = capped_90_sol.get("gamma_co2")
    gamma_w_90 = capped_90_sol.get("gamma_w")
    kpis_90 = compute_governance_kpis(inst, capped_90_cflp, gamma_co2_90, gamma_w_90)
    rows.append({
        "Model Variant": "Capped 90%",
        **kpis_90,
    })
    
    # Capped 80%
    gamma_co2_80 = capped_80_sol.get("gamma_co2")
    gamma_w_80 = capped_80_sol.get("gamma_w")
    kpis_80 = compute_governance_kpis(inst, capped_80_cflp, gamma_co2_80, gamma_w_80)
    rows.append({
        "Model Variant": "Capped 80%",
        **kpis_80,
    })
    
    # Scalarized (50,50)
    kpis_scalar = compute_governance_kpis(inst, scalarized_cflp)
    rows.append({
        "Model Variant": "Scalarized (50,50)",
        **kpis_scalar,
    })
    
    df = pd.DataFrame(rows)
    
    # Format columns for display
    for col in ["total_cost", "total_co2", "total_water", "opened_capacity", "idle_existing_capacity"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.2f}")
    
    for col in ["co2_intensity", "water_intensity", "portfolio_utilization"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.2f}")
    
    for col in ["co2_cap_utilization", "water_cap_utilization"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.1f}%" if x is not None and not pd.isna(x) else "N/A")
    
    for col in ["num_opened_sites", "num_new_sites"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{int(x)}")
    
    if "latency_proxy" in df.columns:
        df["latency_proxy"] = df["latency_proxy"].apply(lambda x: f"{x:.2f}" if x is not None and not pd.isna(x) else "N/A")
    
    return df


def generate_mac_table(
    baseline_sol: dict,
    capped_90_sol: dict,
    capped_80_sol: dict,
) -> pd.DataFrame:
    """Generate Marginal Abatement Cost (MAC) table."""
    rows = []
    
    # Baseline → Capped 90%
    delta_cost_90 = (capped_90_sol["total_cost"] - baseline_sol["total_cost"])
    delta_co2_90 = (baseline_sol["total_co2"] - capped_90_sol["total_co2"])
    delta_water_90 = (baseline_sol["total_water"] - capped_90_sol["total_water"])
    
    mac_co2_90 = (delta_cost_90 / delta_co2_90) if delta_co2_90 > 1e-6 else None
    mac_water_90 = (delta_cost_90 / delta_water_90) if delta_water_90 > 1e-6 else None
    
    rows.append({
        "Transition": "Baseline → Capped 90%",
        "Δ Cost": f"{delta_cost_90:.2f}",
        "Δ CO₂": f"{delta_co2_90:.2f}",
        "Δ Water": f"{delta_water_90:.2f}",
        "MAC CO₂": f"{mac_co2_90:.2f}" if mac_co2_90 is not None else "N/A",
        "MAC Water": f"{mac_water_90:.2f}" if mac_water_90 is not None else "N/A",
    })
    
    # Baseline → Capped 80%
    delta_cost_80 = (capped_80_sol["total_cost"] - baseline_sol["total_cost"])
    delta_co2_80 = (baseline_sol["total_co2"] - capped_80_sol["total_co2"])
    delta_water_80 = (baseline_sol["total_water"] - capped_80_sol["total_water"])
    
    mac_co2_80 = (delta_cost_80 / delta_co2_80) if delta_co2_80 > 1e-6 else None
    mac_water_80 = (delta_cost_80 / delta_water_80) if delta_water_80 > 1e-6 else None
    
    rows.append({
        "Transition": "Baseline → Capped 80%",
        "Δ Cost": f"{delta_cost_80:.2f}",
        "Δ CO₂": f"{delta_co2_80:.2f}",
        "Δ Water": f"{delta_water_80:.2f}",
        "MAC CO₂": f"{mac_co2_80:.2f}" if mac_co2_80 is not None else "N/A",
        "MAC Water": f"{mac_water_80:.2f}" if mac_water_80 is not None else "N/A",
    })
    
    # Capped 90% → Capped 80%
    delta_cost_90_80 = (capped_80_sol["total_cost"] - capped_90_sol["total_cost"])
    delta_co2_90_80 = (capped_90_sol["total_co2"] - capped_80_sol["total_co2"])
    delta_water_90_80 = (capped_90_sol["total_water"] - capped_80_sol["total_water"])
    
    mac_co2_90_80 = (delta_cost_90_80 / delta_co2_90_80) if delta_co2_90_80 > 1e-6 else None
    mac_water_90_80 = (delta_cost_90_80 / delta_water_90_80) if delta_water_90_80 > 1e-6 else None
    
    rows.append({
        "Transition": "Capped 90% → Capped 80%",
        "Δ Cost": f"{delta_cost_90_80:.2f}",
        "Δ CO₂": f"{delta_co2_90_80:.2f}",
        "Δ Water": f"{delta_water_90_80:.2f}",
        "MAC CO₂": f"{mac_co2_90_80:.2f}" if mac_co2_90_80 is not None else "N/A",
        "MAC Water": f"{mac_water_90_80:.2f}" if mac_water_90_80 is not None else "N/A",
    })
    
    return pd.DataFrame(rows)


def generate_scenario_feasibility_table(
    scenario_sensitivity_path: Path,
) -> pd.DataFrame:
    """Generate scenario feasibility boundary table."""
    if not scenario_sensitivity_path.exists():
        return None
    
    with open(scenario_sensitivity_path, "r") as f:
        data = json.load(f)
    
    rows = []
    for scenario in data.get("scenarios", []):
        scenario_name = scenario.get("scenario", "unknown")
        baseline_co2 = scenario.get("baseline_co2")
        capped_cost = scenario.get("capped_cost")
        capped_co2 = scenario.get("capped_co2")
        plan_changed = scenario.get("plan_changed", False)
        
        # Determine feasibility
        is_feasible = capped_cost is not None and capped_co2 is not None
        cap_binding = is_feasible and plan_changed
        
        # Format scenario name
        if scenario_name == "baseline_grid":
            scenario_label = "Baseline grid"
            multiplier = "1.0×"
        elif scenario_name == "clean":
            scenario_label = "Clean grid"
            multiplier = "0.7×"
        elif scenario_name == "dirty":
            scenario_label = "Dirty grid"
            multiplier = "1.3×"
        else:
            scenario_label = scenario_name
            multiplier = "N/A"
        
        rows.append({
            "Scenario": scenario_label,
            "CO₂ Multiplier": multiplier,
            "Baseline CO₂": f"{baseline_co2:.2f}" if baseline_co2 is not None else "N/A",
            "Capped 90% Feasible?": "Yes" if is_feasible else "No",
            "Cap Binding?": "Yes" if cap_binding else "No",
            "Capped Cost": f"{capped_cost:.2f}" if capped_cost is not None else "Infeasible",
            "Capped CO₂": f"{capped_co2:.2f}" if capped_co2 is not None else "N/A",
        })
    
    return pd.DataFrame(rows)


def generate_flexibility_attribution_table(
    inst: CFLPInstance,
    baseline_sol: dict,
    capped_80_sol: dict,
) -> pd.DataFrame:
    """Generate flexibility attribution table (inference vs training split)."""
    baseline_cflp = solution_dict_to_cflp_solution(baseline_sol)
    capped_80_cflp = solution_dict_to_cflp_solution(capped_80_sol)
    
    baseline_split = compute_inference_training_split(inst, baseline_cflp)
    capped_80_split = compute_inference_training_split(inst, capped_80_cflp)
    
    # Compute reductions
    delta_co2_inf = baseline_split["co2_inf"] - capped_80_split["co2_inf"]
    delta_co2_train = baseline_split["co2_train"] - capped_80_split["co2_train"]
    delta_water_inf = baseline_split["water_inf"] - capped_80_split["water_inf"]
    delta_water_train = baseline_split["water_train"] - capped_80_split["water_train"]
    
    total_delta_co2 = delta_co2_inf + delta_co2_train
    total_delta_water = delta_water_inf + delta_water_train
    
    rows = [
        {
            "Workload": "Inference",
            "Baseline CO₂": f"{baseline_split['co2_inf']:.2f}",
            "Capped 80% CO₂": f"{capped_80_split['co2_inf']:.2f}",
            "Δ CO₂": f"{delta_co2_inf:.2f}",
            "% of Total Δ CO₂": f"{(delta_co2_inf / total_delta_co2 * 100):.1f}%" if total_delta_co2 > 1e-6 else "N/A",
            "Baseline Water": f"{baseline_split['water_inf']:.2f}",
            "Capped 80% Water": f"{capped_80_split['water_inf']:.2f}",
            "Δ Water": f"{delta_water_inf:.2f}",
            "% of Total Δ Water": f"{(delta_water_inf / total_delta_water * 100):.1f}%" if total_delta_water > 1e-6 else "N/A",
        },
        {
            "Workload": "Training",
            "Baseline CO₂": f"{baseline_split['co2_train']:.2f}",
            "Capped 80% CO₂": f"{capped_80_split['co2_train']:.2f}",
            "Δ CO₂": f"{delta_co2_train:.2f}",
            "% of Total Δ CO₂": f"{(delta_co2_train / total_delta_co2 * 100):.1f}%" if total_delta_co2 > 1e-6 else "N/A",
            "Baseline Water": f"{baseline_split['water_train']:.2f}",
            "Capped 80% Water": f"{capped_80_split['water_train']:.2f}",
            "Δ Water": f"{delta_water_train:.2f}",
            "% of Total Δ Water": f"{(delta_water_train / total_delta_water * 100):.1f}%" if total_delta_water > 1e-6 else "N/A",
        },
        {
            "Workload": "Total",
            "Baseline CO₂": f"{baseline_split['co2_inf'] + baseline_split['co2_train']:.2f}",
            "Capped 80% CO₂": f"{capped_80_split['co2_inf'] + capped_80_split['co2_train']:.2f}",
            "Δ CO₂": f"{total_delta_co2:.2f}",
            "% of Total Δ CO₂": "100.0%",
            "Baseline Water": f"{baseline_split['water_inf'] + baseline_split['water_train']:.2f}",
            "Capped 80% Water": f"{capped_80_split['water_inf'] + capped_80_split['water_train']:.2f}",
            "Δ Water": f"{total_delta_water:.2f}",
            "% of Total Δ Water": "100.0%",
        },
    ]
    
    return pd.DataFrame(rows)


def main():
    print("="*60)
    print("Comprehensive Analysis: Recomputing all metrics from solutions")
    print("="*60)
    
    # Load instance
    instance_path = Path("data/toy_instance.json")
    if not instance_path.exists():
        print(f"ERROR: Instance file not found at {instance_path}")
        return
    
    inst = load_instance(str(instance_path))
    print(f"\nLoaded instance: {len(inst.I)} sites, {len(inst.R)} regions")
    
    # Load solutions
    baseline_path = Path("results/baseline_solution.json")
    capped_90_path = Path("results/capped_solution_90pct.json")
    capped_80_path = Path("results/capped_solution_80pct.json")
    
    if not baseline_path.exists():
        print("ERROR: Baseline solution not found. Run models first.")
        return
    
    baseline_sol = load_solution(str(baseline_path))
    
    if not capped_90_path.exists() or not capped_80_path.exists():
        print("ERROR: Capped solutions not found. Run models first.")
        return
    
    capped_90_sol = load_solution(str(capped_90_path))
    capped_80_sol = load_solution(str(capped_80_path))
    
    # Solve scalarized (50,50) if needed
    scalarized_50_50_path = Path("results/scalarized_solution_50_50.json")
    if scalarized_50_50_path.exists():
        scalarized_50_50_sol = load_solution(str(scalarized_50_50_path))
    else:
        print("\nSolving scalarized model (λ_C=50, λ_W=50)...")
        scalarized_sol = solve_scalarized(inst, lambda_c=50.0, lambda_w=50.0, output_flag=0)
        scalarized_50_50_sol = {
            "status": scalarized_sol.status,
            "obj": scalarized_sol.obj,
            "x": scalarized_sol.x,
            "y": {f"{i},{r}": v for (i, r), v in scalarized_sol.y.items()},
            "total_cost": scalarized_sol.total_cost,
            "total_latency_proxy": scalarized_sol.total_latency_proxy,
            "total_co2": scalarized_sol.total_co2,
            "total_water": scalarized_sol.total_water,
        }
        with open(scalarized_50_50_path, "w") as f:
            json.dump(scalarized_50_50_sol, f, indent=2)
        print("   Saved scalarized solution.")
    
    # Generate tables
    tables_dir = Path("results/tables")
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    # Table: Governance KPIs
    print("\n" + "="*60)
    print("Generating Governance KPI Table...")
    print("="*60)
    table_gov = generate_governance_kpi_table(
        inst, baseline_sol, capped_90_sol, capped_80_sol, scalarized_50_50_sol
    )
    table_gov.to_csv(tables_dir / "table_governance_kpis.csv", index=False)
    # Generate LaTeX version
    table_gov_latex = table_gov.copy()
    # Replace N/A with \text{---} for LaTeX
    table_gov_latex = table_gov_latex.replace("N/A", r"\text{---}")
    table_gov_latex.to_latex(
        tables_dir / "table_governance_kpis.tex",
        index=False,
        escape=False,
        float_format="%.2f",
        caption="Governance KPIs: Baseline vs sustainability-aware variants",
        label="tab:kpi",
    )
    print("\n" + table_gov.to_string(index=False))
    
    # Table: MAC
    print("\n" + "="*60)
    print("Generating MAC Table...")
    print("="*60)
    table_mac = generate_mac_table(baseline_sol, capped_90_sol, capped_80_sol)
    table_mac.to_csv(tables_dir / "table_mac.csv", index=False)
    table_mac_latex = table_mac.copy()
    table_mac_latex = table_mac_latex.replace("N/A", r"\text{---}")
    table_mac_latex.to_latex(
        tables_dir / "table_mac.tex",
        index=False,
        escape=False,
        float_format="%.2f",
        caption="Marginal abatement costs (MAC) for transitions between model variants",
        label="tab:mac",
    )
    print("\n" + table_mac.to_string(index=False))
    
    # Table: Flexibility Attribution
    print("\n" + "="*60)
    print("Generating Flexibility Attribution Table...")
    print("="*60)
    table_flex = generate_flexibility_attribution_table(inst, baseline_sol, capped_80_sol)
    table_flex.to_csv(tables_dir / "table_flexibility_attribution.csv", index=False)
    table_flex_latex = table_flex.copy()
    table_flex_latex = table_flex_latex.replace("N/A", r"\text{---}")
    table_flex_latex.to_latex(
        tables_dir / "table_flexibility_attribution.tex",
        index=False,
        escape=False,
        float_format="%.2f",
        caption="Flexibility attribution: CO$_2$ and water reductions by workload type (baseline to capped 80\%)",
        label="tab:flexibility",
    )
    print("\n" + table_flex.to_string(index=False))
    
    # Table: Scenario Feasibility
    scenario_sensitivity_path = Path("results/scenario_sensitivity.json")
    if scenario_sensitivity_path.exists():
        print("\n" + "="*60)
        print("Generating Scenario Feasibility Table...")
        print("="*60)
        table_scenario = generate_scenario_feasibility_table(scenario_sensitivity_path)
        if table_scenario is not None:
            table_scenario.to_csv(tables_dir / "table_scenario_feasibility.csv", index=False)
            table_scenario_latex = table_scenario.copy()
            table_scenario_latex = table_scenario_latex.replace("N/A", r"\text{---}")
            table_scenario_latex.to_latex(
                tables_dir / "table_scenario_feasibility.tex",
                index=False,
                escape=False,
                float_format="%.2f",
                caption="Scenario feasibility boundary: impact of grid carbon intensity on capped model feasibility",
                label="tab:scenario",
            )
            print("\n" + table_scenario.to_string(index=False))
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print(f"All tables saved to: {tables_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

