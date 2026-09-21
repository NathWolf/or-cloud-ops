#!/usr/bin/env python3
"""Run curated hierarchical strategic-operational planning experiments."""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis_hierarchical import (
    allocation_by_site_workload_rows,
    binding_constraint_rows,
    compact_sensitivity_rows,
    data_construction_rows,
    instance_summary_rows,
    interval_abatement_rows,
    nearest_price_equivalence_rows,
    planning_regime_comparison_rows,
    site_selection_rows,
    solution_kpi_row,
    write_csv,
)
from src.models.hierarchical import (
    HierarchicalCloudSolution,
    instance_to_dict,
    make_public_calibrated_hierarchical_instance,
    make_synthetic_hierarchical_instance,
    solution_to_dict,
    solve_fixed_plan_recourse_lp_for_duals,
    solve_hierarchical_baseline,
    solve_hierarchical_capped,
    solve_hierarchical_priced,
)


DETAIL_OUTPUTS = [
    "price_cap_equivalence.csv",
    "price_sweep.csv",
    "water_experiments.csv",
]


def save_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def move_stale_detail_outputs(output_dir: Path, supplement_dir: Path) -> None:
    supplement_dir.mkdir(parents=True, exist_ok=True)
    for filename in DETAIL_OUTPUTS:
        src = output_dir / filename
        if not src.exists():
            continue
        dst = supplement_dir / filename
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))


def solve_or_record(label: str, sol: HierarchicalCloudSolution) -> None:
    if sol.status != 2:
        print(f"WARNING: {label} returned status {sol.status}")


def nearest_price_to_targets(
    price_solutions: Dict[Tuple[float, float], HierarchicalCloudSolution],
    *,
    gamma_co2: float,
    gamma_w_by_period: Dict[str, float],
) -> Tuple[Tuple[float, float], HierarchicalCloudSolution]:
    best_key = None
    best_sol = None
    best_score = float("inf")
    for key, sol in price_solutions.items():
        if sol.status != 2 or sol.expected_co2 is None or sol.expected_water is None:
            continue
        score = abs(sol.expected_co2 - gamma_co2) / max(gamma_co2, 1e-9)
        score += sum(abs(sol.period_water[t] - limit) / max(limit, 1e-9)
                     for t, limit in gamma_w_by_period.items()) / len(gamma_w_by_period)
        if score < best_score:
            best_score = score
            best_key = key
            best_sol = sol
    if best_key is None or best_sol is None:
        raise RuntimeError("No feasible internal-price solution found for planning-regime comparison.")
    return best_key, best_sol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Use a smaller deterministic instance.")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--output-dir", default="results/hierarchical")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--legacy-synthetic", action="store_true", help="Run the legacy synthetic instance.")
    parser.add_argument(
        "--require-public-data",
        action="store_true",
        help="Require the source-derived carbon input at data/public/carbon_2024.csv.",
    )
    parser.add_argument("--mip-gap", type=float, default=0.0)
    parser.add_argument("--time-limit", type=float, default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    supplement_dir = output_dir / "supplement"
    solution_dir = output_dir / "solutions"
    output_dir.mkdir(parents=True, exist_ok=True)
    supplement_dir.mkdir(parents=True, exist_ok=True)
    move_stale_detail_outputs(output_dir, supplement_dir)
    solution_dir.mkdir(parents=True, exist_ok=True)

    carbon_path = Path(args.data_dir) / "public" / "carbon_2024.csv"
    public_data_found = carbon_path.is_file()
    if args.require_public_data and not public_data_found:
        raise SystemExit(
            "Missing data/public/carbon_2024.csv. Supply the source-derived carbon rows "
            "before using --require-public-data."
        )

    if args.legacy_synthetic:
        inst = make_synthetic_hierarchical_instance(seed=args.seed, quick=args.quick)
        calibration_status = "legacy_synthetic"
    else:
        calibration_status = "public_proxy"
        inst = make_public_calibrated_hierarchical_instance(
            seed=args.seed,
            quick=args.quick,
            calibration_status=calibration_status,
            carbon_data_path=str(carbon_path) if public_data_found else None,
        )
        calibration_status = inst.metadata["calibration_status"]
    save_json(output_dir / "instance.json", instance_to_dict(inst))
    write_csv(str(output_dir / "instance_summary.csv"), instance_summary_rows(inst))
    write_csv(str(output_dir / "data_construction.csv"), data_construction_rows(inst))

    print("Solving baseline...")
    baseline = solve_hierarchical_baseline(
        inst, output_flag=0, mip_gap=args.mip_gap, time_limit_s=args.time_limit
    )
    solve_or_record("baseline", baseline)
    save_json(solution_dir / "baseline.json", solution_to_dict(baseline))

    if baseline.expected_co2 is None or baseline.expected_water is None:
        raise RuntimeError("Baseline solve failed; cannot build experiment caps.")

    baseline_co2 = baseline.expected_co2
    baseline_period_water = dict(baseline.period_water)
    hard_gamma_co2 = 0.85 * baseline_co2
    hard_gamma_w_by_period = {t: 0.90 * value for t, value in baseline_period_water.items()}

    cap_levels = [1.00, 0.95, 0.90, 0.85, 0.80, 0.75]
    if args.quick:
        cap_levels = [1.00, 0.90, 0.80]

    cap_rows = []
    binding_rows = []
    shadow_rows = []
    representative_solutions: Dict[str, HierarchicalCloudSolution] = {"Baseline": baseline}
    representative_caps: Dict[str, Dict] = {"Baseline": {}}

    print("Solving carbon cap sweep...")
    for alpha in cap_levels:
        gamma_co2 = alpha * baseline_co2
        label = f"Carbon cap {int(alpha * 100)}%"
        sol = solve_hierarchical_capped(
            inst,
            gamma_co2=gamma_co2,
            output_flag=0,
            mip_gap=args.mip_gap,
            time_limit_s=args.time_limit,
        )
        solve_or_record(label, sol)
        save_json(solution_dir / f"carbon_cap_{int(alpha * 100)}.json", solution_to_dict(sol))
        row = solution_kpi_row(
            inst,
            label,
            sol,
            gamma_co2=gamma_co2,
            extra={"alpha": alpha, "experiment": "carbon_cap_sweep"},
        )
        cap_rows.append(row)
        binding_rows.extend(binding_constraint_rows(inst, label, sol, gamma_co2=gamma_co2))
        if sol.status == 2:
            dual = solve_fixed_plan_recourse_lp_for_duals(
                inst,
                sol,
                gamma_co2=gamma_co2,
                gamma_w_by_period=None,
                output_flag=0,
            )
            shadow_rows.append(
                {
                    "label": label,
                    "experiment": "carbon_cap_sweep",
                    "alpha": alpha,
                    "constraint": "carbon_cap",
                    "period": "",
                    "status": dual["status"],
                    "shadow_price": dual["carbon_shadow_price"],
                    "slack": dual["carbon_slack"],
                    "interpretation": "local conditional LP recourse shadow price",
                }
            )
        if abs(alpha - 0.85) < 1e-9:
            representative_solutions[label] = sol
            representative_caps[label] = {"gamma_co2": gamma_co2}

    cap_df = write_csv(str(output_dir / "cap_sweep.csv"), cap_rows)

    print("Solving handoff-contract hard envelope...")
    hard_label = "Handoff-contract hard envelope"
    hard_envelope = solve_hierarchical_capped(
        inst,
        gamma_co2=hard_gamma_co2,
        gamma_w_by_period=hard_gamma_w_by_period,
        output_flag=0,
        mip_gap=args.mip_gap,
        time_limit_s=args.time_limit,
    )
    solve_or_record(hard_label, hard_envelope)
    save_json(solution_dir / "handoff_hard_envelope.json", solution_to_dict(hard_envelope))
    binding_rows.extend(
        binding_constraint_rows(
            inst,
            hard_label,
            hard_envelope,
            gamma_co2=hard_gamma_co2,
            gamma_w_by_period=hard_gamma_w_by_period,
        )
    )
    representative_solutions[hard_label] = hard_envelope
    representative_caps[hard_label] = {
        "gamma_co2": hard_gamma_co2,
        "gamma_w_by_period": hard_gamma_w_by_period,
    }

    print("Solving water cap experiments...")
    water_rows = []
    water_factors = [1.00, 0.95, 0.90, 0.85]
    if args.quick:
        water_factors = [1.00, 0.90]
    for factor in water_factors:
        gamma_w_by_period = {t: factor * value for t, value in baseline_period_water.items()}
        label = f"Water cap {int(factor * 100)}%"
        sol = solve_hierarchical_capped(
            inst,
            gamma_w_by_period=gamma_w_by_period,
            output_flag=0,
            mip_gap=args.mip_gap,
            time_limit_s=args.time_limit,
        )
        solve_or_record(label, sol)
        save_json(solution_dir / f"water_cap_{int(factor * 100)}.json", solution_to_dict(sol))
        water_rows.append(
            solution_kpi_row(
                inst,
                label,
                sol,
                gamma_w_by_period=gamma_w_by_period,
                extra={"water_cap_factor": factor, "experiment": "water_cap_sweep"},
            )
        )
        binding_rows.extend(
            binding_constraint_rows(inst, label, sol, gamma_w_by_period=gamma_w_by_period)
        )
        if sol.status == 2:
            dual = solve_fixed_plan_recourse_lp_for_duals(
                inst,
                sol,
                gamma_co2=None,
                gamma_w_by_period=gamma_w_by_period,
                output_flag=0,
            )
            for period, price in dual["water_shadow_prices"].items():
                shadow_rows.append(
                    {
                        "label": label,
                        "experiment": "water_cap_sweep",
                        "alpha": factor,
                        "constraint": "water_cap",
                        "period": period,
                        "status": dual["status"],
                        "shadow_price": price,
                        "slack": dual["water_slacks"].get(period),
                        "interpretation": "local conditional LP recourse shadow price",
                    }
                )
        if abs(factor - 0.90) < 1e-9:
            representative_solutions[label] = sol
            representative_caps[label] = {"gamma_w_by_period": gamma_w_by_period}

    write_csv(str(supplement_dir / "water_experiments.csv"), water_rows)

    print("Solving internal price sweep...")
    lambda_c_values = [0, 2, 5, 10, 20, 40, 80]
    lambda_w_values = [0, 2, 5, 10, 20, 40, 80]
    if args.quick:
        lambda_c_values = [0, 10, 40]
        lambda_w_values = [0, 10, 40]
    price_rows = []
    price_solutions: Dict[Tuple[float, float], HierarchicalCloudSolution] = {}
    for lambda_c in lambda_c_values:
        for lambda_w in lambda_w_values:
            label = f"Price C={lambda_c}, W={lambda_w}"
            sol = solve_hierarchical_priced(
                inst,
                lambda_c=float(lambda_c),
                lambda_w=float(lambda_w),
                output_flag=0,
                mip_gap=args.mip_gap,
                time_limit_s=args.time_limit,
            )
            solve_or_record(label, sol)
            price_solutions[(float(lambda_c), float(lambda_w))] = sol
            save_json(solution_dir / f"price_C{lambda_c}_W{lambda_w}.json", solution_to_dict(sol))
            price_rows.append(
                solution_kpi_row(
                    inst,
                    label,
                    sol,
                    extra={
                        "lambda_c": lambda_c,
                        "lambda_w": lambda_w,
                        "experiment": "internal_price_sweep",
                    },
                )
            )
            if lambda_c == 20 and lambda_w == 10:
                representative_solutions["Internal price C=20 W=10"] = sol
                representative_caps["Internal price C=20 W=10"] = {}
                save_json(solution_dir / "price_20_10.json", solution_to_dict(sol))

    price_key, price_solution = nearest_price_to_targets(
        price_solutions,
        gamma_co2=hard_gamma_co2,
        gamma_w_by_period=hard_gamma_w_by_period,
    )
    price_label = f"lambda_C={price_key[0]:g}, lambda_W={price_key[1]:g}"
    representative_solutions[f"Internal-price planning ({price_label})"] = price_solution
    representative_caps[f"Internal-price planning ({price_label})"] = {}
    save_json(solution_dir / "internal_price_nearest_targets.json", solution_to_dict(price_solution))

    price_df = write_csv(str(supplement_dir / "price_sweep.csv"), price_rows)
    write_csv(
        str(supplement_dir / "price_cap_equivalence.csv"),
        nearest_price_equivalence_rows(cap_df, price_df),
    )

    print("Solving accounting experiments...")
    accounting_rows = []
    accounting_modes = ["location_time", "location_annual", "market_time", "market_annual"]
    for mode in accounting_modes:
        base_mode = solve_hierarchical_baseline(
            inst,
            accounting_mode=mode,
            output_flag=0,
            mip_gap=args.mip_gap,
            time_limit_s=args.time_limit,
        )
        # Common numerical cap across conventions, not a new baseline per mode.
        gamma_mode = hard_gamma_co2
        cap_mode = solve_hierarchical_capped(
            inst,
            gamma_co2=gamma_mode,
            accounting_mode=mode,
            output_flag=0,
            mip_gap=args.mip_gap,
            time_limit_s=args.time_limit,
        )
        save_json(solution_dir / f"accounting_{mode}_baseline.json", solution_to_dict(base_mode))
        save_json(solution_dir / f"accounting_{mode}_cap.json", solution_to_dict(cap_mode))
        accounting_rows.append(
            solution_kpi_row(
                inst,
                f"{mode} baseline",
                base_mode,
                extra={"accounting_experiment": "baseline"},
            )
        )
        accounting_rows.append(
            solution_kpi_row(
                inst,
                f"{mode} cap 85%",
                cap_mode,
                gamma_co2=gamma_mode,
                extra={"accounting_experiment": "cap_85"},
            )
        )
    accounting_df = write_csv(str(output_dir / "accounting_experiments.csv"), accounting_rows)

    print("Solving interconnection sensitivity experiments...")
    eligibility_rows = []
    multipliers = [0.5, 1.0, 2.0, 4.0]
    for multiplier in multipliers:
        sol = solve_hierarchical_baseline(
            inst,
            output_flag=0,
            mip_gap=args.mip_gap,
            time_limit_s=args.time_limit,
            interconnect_cost_multiplier=multiplier,
        )
        save_json(solution_dir / f"interconnection_{multiplier:g}.json", solution_to_dict(sol))
        eligibility_rows.append(
            solution_kpi_row(
                inst,
                f"Interconnection cost x{multiplier:g}",
                sol,
                extra={
                    "interconnect_cost_multiplier": multiplier,
                    "experiment": "interconnection_sensitivity",
                },
            )
        )
    eligibility_df = write_csv(str(output_dir / "eligibility_experiments.csv"), eligibility_rows)
    write_csv(
        str(output_dir / "compact_sensitivity.csv"),
        compact_sensitivity_rows(accounting_df, eligibility_df),
    )

    print("Writing planning-regime comparison...")
    write_csv(
        str(output_dir / "planning_regime_comparison.csv"),
        planning_regime_comparison_rows(
            baseline,
            hard_envelope,
            price_solution,
            gamma_co2=hard_gamma_co2,
            gamma_w_by_period=hard_gamma_w_by_period,
            internal_price_label=price_label,
        ),
    )

    print("Writing summary CSVs...")
    kpi_labels = list(representative_solutions.keys())
    kpi_rows = []
    for label in kpi_labels:
        caps = representative_caps.get(label, {})
        kpi_rows.append(solution_kpi_row(inst, label, representative_solutions[label], **caps))
    write_csv(str(output_dir / "kpi_summary.csv"), kpi_rows)
    write_csv(str(output_dir / "site_selection.csv"), site_selection_rows(representative_solutions))
    write_csv(
        str(output_dir / "allocation_by_site_workload.csv"),
        allocation_by_site_workload_rows(
            inst,
            {
                "Cost-only planning": baseline,
                "Handoff-contract hard envelope": hard_envelope,
            },
        ),
    )
    write_csv(str(output_dir / "binding_constraints.csv"), binding_rows)

    iac_rows = interval_abatement_rows(cap_df)
    for row in iac_rows:
        row["experiment"] = "carbon_cap_sweep"
    shadow_rows.extend(iac_rows)
    write_csv(str(output_dir / "shadow_prices.csv"), shadow_rows)

    manifest = {
        "quick": args.quick,
        "seed": args.seed,
        "legacy_synthetic": args.legacy_synthetic,
        "calibration_status": calibration_status,
        "actual_public_data_found": public_data_found,
        "outputs": sorted(str(p.relative_to(output_dir)) for p in output_dir.glob("*.csv")),
        "supplement_outputs": sorted(str(p.relative_to(output_dir)) for p in supplement_dir.glob("*.csv")),
    }
    save_json(output_dir / "manifest.json", manifest)
    print(f"Done. Outputs written to {output_dir}")


if __name__ == "__main__":
    main()
