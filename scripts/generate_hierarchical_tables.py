#!/usr/bin/env python3
"""Generate compact LaTeX tables for hierarchical experiment results."""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


STALE_MAIN_TABLES = [
    "table_hier_accounting.tex",
    "table_hier_eligibility.tex",
    "table_hier_instance.tex",
    "table_hier_kpi_summary.tex",
    "table_hier_price_equivalence.tex",
    "table_hier_water.tex",
]


def fmt(value, digits: int = 1) -> str:
    if pd.isna(value):
        return "--"
    if isinstance(value, str):
        return value
    return f"{float(value):.{digits}f}"


def fmt_count_or_decimal(component: object, value: object) -> str:
    if pd.isna(value):
        return "--"
    if str(component).lower() == "expected demand":
        return fmt(value, 1)
    return str(int(round(float(value))))


def tex_text(value: object) -> str:
    return (
        str(value)
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("<= ", "$\\leq$ ")
        .replace(">=", "$\\geq$")
    )


def compact_periods(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "--"
    periods = [p.strip() for p in value.split(",") if p.strip()]
    if set(periods) == {"winter", "spring", "summer", "autumn"}:
        return "all periods"
    return ", ".join(periods)


def move_stale_tables(latex_dir: Path, supplement_table_dir: Path) -> None:
    supplement_table_dir.mkdir(parents=True, exist_ok=True)
    for filename in STALE_MAIN_TABLES:
        src = latex_dir / filename
        if not src.exists():
            continue
        dst = supplement_table_dir / filename
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))


def write_table(
    path: Path,
    caption: str,
    label: str,
    columns: List[str],
    rows: Iterable[Iterable[str]],
    align_spec: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    align = align_spec or ("@{}" + "l" + "r" * (len(columns) - 1) + "@{}")
    lines = [
        "\\begin{table}[!htbp]",
        "  \\centering",
        f"  \\caption{{{caption}}}",
        f"  \\label{{{label}}}",
        f"  \\begin{{tabular}}{{{align}}}",
        "    \\toprule",
        "    " + " & ".join(columns) + " \\\\",
        "    \\midrule",
    ]
    for row in rows:
        lines.append("    " + " & ".join(row) + " \\\\")
    lines.extend(
        [
            "    \\bottomrule",
            "  \\end{tabular}",
        ]
    )
    if note:
        lines.extend(
            [
                "  \\vspace{2pt}",
                f"  \\parbox{{0.92\\linewidth}}{{\\footnotesize \\emph{{Note.}} {note}}}",
            ]
        )
    lines.extend(["\\end{table}", ""])
    path.write_text("\n".join(lines))


def write_tabularx_table(
    path: Path,
    caption: str,
    label: str,
    columns: List[str],
    rows: Iterable[Iterable[str]],
    align_spec: str,
    note: Optional[str] = None,
    sideways: bool = False,
    font_size: str = "\\scriptsize",
) -> None:
    env = "sidewaystable" if sideways else "table"
    width = "\\linewidth"
    lines = [
        f"\\begin{{{env}}}[!htbp]",
        "  \\centering",
        f"  \\caption{{{caption}}}",
        f"  \\label{{{label}}}",
        f"  {font_size}",
        "  \\setlength{\\tabcolsep}{4pt}",
        "  \\renewcommand{\\arraystretch}{1.12}",
        f"  \\begin{{tabularx}}{{{width}}}{{{align_spec}}}",
        "    \\toprule",
        "    " + " & ".join(columns) + " \\\\",
        "    \\midrule",
    ]
    for row in rows:
        lines.append("    " + " & ".join(row) + " \\\\")
    lines.extend(
        [
            "    \\bottomrule",
            "  \\end{tabularx}",
        ]
    )
    if note:
        lines.extend(
            [
                "  \\vspace{2pt}",
                f"  \\parbox{{0.92\\linewidth}}{{\\footnotesize \\emph{{Note.}} {note}}}",
            ]
        )
    lines.extend([f"\\end{{{env}}}", ""])
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results/hierarchical")
    parser.add_argument("--latex-dir", default="latex/fig")
    args = parser.parse_args()

    root = Path(args.results_dir)
    latex_dir = Path(args.latex_dir)
    latex_dir.mkdir(parents=True, exist_ok=True)
    move_stale_tables(latex_dir, root / "supplement" / "tables")

    data_construction = pd.read_csv(root / "data_construction.csv")
    write_tabularx_table(
        latex_dir / "table_hier_data_construction.tex",
        "Data construction for the public-proxy planning case.",
        "tab:hier-data-construction",
        ["Parameter group", "Public/proxy basis", "Proxy or transformation", "Role in the model"],
        (
            [
                tex_text(r["parameter_group"]),
                tex_text(r["public_proxy_basis"]),
                tex_text(r["proxy_or_transformation"]),
                tex_text(r["role_in_model"]),
            ]
            for _, r in data_construction.iterrows()
        ),
        align_spec="@{}p{0.18\\linewidth}YYY@{}",
        sideways=True,
        font_size="\\footnotesize",
    )

    regimes = pd.read_csv(root / "planning_regime_comparison.csv")
    write_tabularx_table(
        latex_dir / "table_hier_planning_regime.tex",
        "Planning-regime comparison.",
        "tab:hier-regime-comparison",
        [
            "Regime",
            "Cost",
            "CO$_2$",
            "Water",
            "CO$_2$ target met?",
            "Water target met?",
            "Sites",
            "Links",
            "Downstream feasibility / replanning implication",
        ],
        (
            [
                tex_text(r["regime"]),
                fmt(r["economic_cost"], 1),
                fmt(r["expected_co2"], 1),
                fmt(r["expected_water"], 1),
                tex_text(r["co2_target_met"]),
                tex_text(r["water_target_met"]),
                str(int(r["num_opened_sites"])),
                str(int(r["active_links"])),
                tex_text(r["downstream_implication"]),
            ]
            for _, r in regimes.iterrows()
        ),
        align_spec="@{}p{0.16\\linewidth}rrrccrrY@{}",
        sideways=True,
    )

    cap = pd.read_csv(root / "cap_sweep.csv")
    write_table(
        latex_dir / "table_hier_cap_sweep.tex",
        "Hard carbon-envelope sweep.",
        "tab:hier-cap-sweep",
        ["Cap", "Cost", "CO$_2$", "Sites", "Links"],
        (
            [
                f"{int(r['alpha'] * 100)}\\%",
                fmt(r["economic_cost"], 1),
                fmt(r["expected_co2"], 1),
                str(int(r["num_opened_sites"])),
                str(int(r["active_links"])),
            ]
            for _, r in cap.iterrows()
            if int(r["status"]) == 2
        ),
    )

    sensitivity = pd.read_csv(root / "compact_sensitivity.csv")
    write_table(
        latex_dir / "table_hier_sensitivity.tex",
        "Compact accounting and interconnection sensitivity.",
        "tab:hier-sensitivity",
        ["Sensitivity", "Cost", "CO$_2$", "Water", "Links"],
        (
            [
                tex_text(r["sensitivity"]),
                fmt(r["economic_cost"], 1),
                fmt(r["expected_co2"], 1),
                fmt(r["expected_water"], 1),
                str(int(r["active_links"])),
            ]
            for _, r in sensitivity.iterrows()
        ),
        align_spec="@{}lrrrr@{}",
    )

    shadow = pd.read_csv(root / "shadow_prices.csv")
    iac = shadow[shadow["interval_abatement_cost"].notna()] if "interval_abatement_cost" in shadow else pd.DataFrame()
    duals = shadow[(shadow["constraint"] == "carbon_cap") & shadow["shadow_price"].notna()]
    rows = []
    for _, r in iac.iterrows():
        rows.append(
            [
                f"{int(r['from_alpha'] * 100)}\\% $\\rightarrow$ {int(r['to_alpha'] * 100)}\\%",
                fmt(r["interval_abatement_cost"], 2),
                "--",
                "interval",
            ]
        )
    for _, r in duals.iterrows():
        rows.append(
            [
                f"{int(r['alpha'] * 100)}\\%",
                "--",
                fmt(r["shadow_price"], 2),
                "fixed-plan LP",
            ]
        )
    write_table(
        latex_dir / "table_hier_shadow_prices.tex",
        "Interval abatement costs and local conditional shadow prices.",
        "tab:hier-shadow",
        ["Cap/transition", "IAC", "Shadow price", "Interpretation"],
        rows,
        align_spec="@{}lrrl@{}",
    )

    print(f"Hierarchical LaTeX tables written to {latex_dir}")


if __name__ == "__main__":
    main()
