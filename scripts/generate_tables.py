#!/usr/bin/env python3
"""Generate publication-ready tables for the numerical analysis."""
import sys
from pathlib import Path
import json
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.cflp import CFLPInstance, solve_scalarized
from src.utils import load_instance


def load_solution(filepath: str) -> dict:
    """Load a solution from JSON."""
    with open(filepath, "r") as f:
        return json.load(f)


def generate_table1_instance_summary(inst: CFLPInstance) -> pd.DataFrame:
    """Generate Table 1: Instance definition summary."""
    data = {
        "Parameter": [
            "Number of candidate sites |I|",
            "Number of regions |R|",
            "Total demand",
            "Fixed cost range (F_i)",
            "Operating cost range (O_i)",
            "Capacity range (C_i)",
            "CO₂ factor range (e_i^{CO2})",
            "Water factor range (w_i)",
            "Latency eligibility threshold",
            "Latency penalty weight (φ)",
        ],
        "Value": [
            len(inst.I),
            len(inst.R),
            f"{sum(inst.d.values()):.1f}",
            f"[{min(inst.F.values()):.1f}, {max(inst.F.values()):.1f}]",
            f"[{min(inst.O.values()):.1f}, {max(inst.O.values()):.1f}]",
            f"[{min(inst.C.values()):.1f}, {max(inst.C.values()):.1f}]",
            f"[{min(inst.e_co2.values()):.2f}, {max(inst.e_co2.values()):.2f}]",
            f"[{min(inst.w.values()):.2f}, {max(inst.w.values()):.2f}]",
            "60th percentile of distances per region",
            f"{inst.phi:.1f}",
        ],
    }
    return pd.DataFrame(data)


def generate_table2_kpi_comparison(
    inst: CFLPInstance,
    baseline_sol: dict,
    capped_sol: dict,
    scalarized_results: list,
) -> pd.DataFrame:
    """Generate Table 2: Baseline vs sustainability-aware KPIs."""
    
    def sort_sites(opened):
        def key_fn(s):
            try:
                return int(s.lstrip("S"))
            except ValueError:
                return s
        return sorted(opened, key=key_fn)

    def get_opened_sites(x_dict: dict) -> str:
        opened = [s for s, v in x_dict.items() if abs(v) > 0.5]
        return ", ".join(sort_sites(opened))
    
    rows = []
    baseline_sites = get_opened_sites(baseline_sol["x"])
    
    # Baseline
    rows.append({
        "Model Variant": "Baseline",
        "Selected Sites": baseline_sites,
        "Total Cost": f"{baseline_sol['total_cost']:.2f}",
        "Total CO₂": f"{baseline_sol['total_co2']:.2f}",
        "Total Water": f"{baseline_sol['total_water']:.2f}",
        "Latency Proxy": f"{baseline_sol.get('total_latency_proxy', 0):.2f}",
        "Sites Opened": sum(1 for v in baseline_sol["x"].values() if abs(v) > 0.5),
    })
    
    # Capped-impact
    rows.append({
        "Model Variant": "Capped-impact",
        "Selected Sites": get_opened_sites(capped_sol["x"]),
        "Total Cost": f"{capped_sol['total_cost']:.2f}",
        "Total CO₂": f"{capped_sol['total_co2']:.2f}",
        "Total Water": f"{capped_sol['total_water']:.2f}",
        "Latency Proxy": f"{capped_sol.get('total_latency_proxy', 0):.2f}",
        "Sites Opened": sum(1 for v in capped_sol["x"].values() if abs(v) > 0.5),
    })
    
    # Scalarized - report a high-weight example
    if scalarized_results:
        high_weight = None
        high_weight_sites = None
        
        for result in scalarized_results:
            lc, lw, obj, cost, co2, water = result
            if lc == 50.0 and lw == 50.0:
                high_weight = result

        if high_weight:
            lc, lw, obj, cost, co2, water = high_weight
            # Solve once to recover site openings for reporting
            try:
                sol_hw = solve_scalarized(inst, lambda_c=lc, lambda_w=lw, output_flag=0)
                high_weight_sites = get_opened_sites(sol_hw.x)
                high_weight_opened = sum(1 for v in sol_hw.x.values() if abs(v) > 0.5)
                high_latency = f"{sol_hw.total_latency_proxy:.2f}" if sol_hw.total_latency_proxy is not None else "N/A"
            except Exception:
                high_weight_opened = "N/A"
                high_latency = "N/A"
            
            rows.append({
                "Model Variant": f"Scalarized (λ_C={lc:.0f}, λ_W={lw:.0f})",
                "Selected Sites": high_weight_sites if high_weight_sites else "N/A",
                "Total Cost": f"{cost:.2f}",
                "Total CO₂": f"{co2:.2f}",
                "Total Water": f"{water:.2f}",
                "Latency Proxy": high_latency,
                "Sites Opened": high_weight_opened if high_weight_sites else "N/A",
            })
    
    return pd.DataFrame(rows)


def generate_table3_site_shifts(
    inst: CFLPInstance,
    baseline_sol: dict,
    capped_sol: dict,
) -> pd.DataFrame:
    """Generate Table 3: Site-level shifts."""
    rows = []
    
    for site in sorted(inst.I):
        baseline_x = 1 if abs(baseline_sol["x"].get(site, 0)) > 0.5 else 0
        capped_x = 1 if abs(capped_sol["x"].get(site, 0)) > 0.5 else 0
        
        # Calculate flow changes
        baseline_flow = sum(
            v for k, v in baseline_sol["y"].items()
            if k.startswith(f"{site},")
        )
        capped_flow = sum(
            v for k, v in capped_sol["y"].items()
            if k.startswith(f"{site},")
        )
        flow_delta = capped_flow - baseline_flow
        
        rows.append({
            "Site": site,
            "Baseline (x_i)": baseline_x,
            "Capped (x_i)": capped_x,
            "Baseline Flow": f"{baseline_flow:.2f}",
            "Capped Flow": f"{capped_flow:.2f}",
            "Flow Change (Δ)": f"{flow_delta:+.2f}",
        })
    
    return pd.DataFrame(rows)


def main():
    print("Generating publication-ready tables...")
    
    # Load instance
    instance_path = Path("data/toy_instance.json")
    if not instance_path.exists():
        print(f"ERROR: Instance file not found at {instance_path}")
        return
    
    inst = load_instance(str(instance_path))
    
    # Load solutions
    baseline_path = Path("results/baseline_solution.json")
    capped_path = Path("results/capped_solution.json")
    scalarized_path = Path("results/scalarized_scan.json")
    
    if not baseline_path.exists() or not capped_path.exists():
        print("ERROR: Solution files not found. Run the models first.")
        return
    
    baseline_sol = load_solution(str(baseline_path))
    capped_sol = load_solution(str(capped_path))
    
    scalarized_results = None
    if scalarized_path.exists():
        with open(scalarized_path, "r") as f:
            scan_data = json.load(f)
            scalarized_results = scan_data["results"]
    
    # Generate tables
    tables_dir = Path("results/tables")
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    # Table 1: Instance summary
    print("\nGenerating Table 1: Instance Summary...")
    table1 = generate_table1_instance_summary(inst)
    table1.to_csv(tables_dir / "table1_instance_summary.csv", index=False)
    table1.to_latex(tables_dir / "table1_instance_summary.tex", index=False, float_format="%.2f")
    print(f"   Saved to {tables_dir / 'table1_instance_summary.csv'}")
    print("\n" + table1.to_string(index=False))
    
    # Table 2: KPI Comparison
    print("\n\nGenerating Table 2: KPI Comparison...")
    table2 = generate_table2_kpi_comparison(inst, baseline_sol, capped_sol, scalarized_results)
    table2.to_csv(tables_dir / "table2_kpi_comparison.csv", index=False)
    table2.to_latex(tables_dir / "table2_kpi_comparison.tex", index=False, float_format="%.2f")
    print(f"   Saved to {tables_dir / 'table2_kpi_comparison.csv'}")
    print("\n" + table2.to_string(index=False))
    
    # Table 3: Site-level shifts
    print("\n\nGenerating Table 3: Site-level Shifts...")
    table3 = generate_table3_site_shifts(inst, baseline_sol, capped_sol)
    table3.to_csv(tables_dir / "table3_site_shifts.csv", index=False)
    table3.to_latex(tables_dir / "table3_site_shifts.tex", index=False, float_format="%.2f")
    print(f"   Saved to {tables_dir / 'table3_site_shifts.csv'}")
    print("\n" + table3.to_string(index=False))
    
    print("\n" + "="*60)
    print("Table generation complete!")
    print(f"All tables saved to: {tables_dir}")
    print("="*60)


if __name__ == "__main__":
    main()
