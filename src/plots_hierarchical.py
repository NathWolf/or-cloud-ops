"""Plots for hierarchical cloud-planning experiments."""

import shutil
from pathlib import Path
from typing import Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "legend.fontsize": 9,
        "figure.titlesize": 12,
    }
)


MAIN_FIGURES = {
    "fig_hier_cap_sweep.png",
    "fig_hier_workload_allocation.png",
}

SUPPLEMENT_FIGURES = {
    "fig_hier_accounting_comparison.png",
    "fig_hier_frontier.png",
    "fig_hier_interconnection_sensitivity.png",
    "fig_hier_price_heatmap_co2.png",
    "fig_hier_price_heatmap_cost.png",
    "fig_hier_shadow_price.png",
    "fig_hier_water_binding.png",
}


def _move_stale_main_figures(directories: Iterable[Path], supplement_dir: Path) -> None:
    supplement_dir.mkdir(parents=True, exist_ok=True)
    for directory in directories:
        if not directory.exists():
            continue
        for filename in SUPPLEMENT_FIGURES:
            src = directory / filename
            if not src.exists():
                continue
            dst = supplement_dir / filename
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))


def _save(fig: plt.Figure, name: str, output_dirs: Iterable[Path]) -> None:
    for directory in output_dirs:
        directory.mkdir(parents=True, exist_ok=True)
        fig.savefig(directory / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_frontier(cap_df: pd.DataFrame, price_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    cap = cap_df[cap_df["status"] == 2].sort_values("expected_co2", ascending=False)
    price = price_df[price_df["status"] == 2]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.scatter(
        price["expected_co2"].to_numpy(dtype=float),
        price["economic_cost"].to_numpy(dtype=float),
        s=22,
        alpha=0.45,
        label="Internal-price runs",
    )
    ax.plot(
        cap["expected_co2"].to_numpy(dtype=float),
        cap["economic_cost"].to_numpy(dtype=float),
        marker="o",
        color="black",
        label="Hard carbon caps",
    )
    ax.set_xlabel("Expected CO2")
    ax.set_ylabel("Economic cost")
    ax.grid(True, alpha=0.25)
    ax.legend()
    _save(fig, "fig_hier_frontier", output_dirs)


def plot_cap_sweep(cap_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    cap = cap_df[cap_df["status"] == 2].sort_values("alpha", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4))
    x = cap["alpha"] * 100
    axes[0].plot(x, cap["economic_cost"], marker="o", color="#1f77b4")
    axes[0].set_ylabel("Economic cost")
    axes[1].plot(x, cap["expected_co2"], marker="o", color="#2ca02c")
    axes[1].set_ylabel("Expected CO2")
    for ax in axes:
        ax.invert_xaxis()
        ax.set_xlabel("Carbon cap (% of baseline)")
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    _save(fig, "fig_hier_cap_sweep", output_dirs)


def plot_water_binding(water_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    df = water_df[water_df["status"] == 2].sort_values("water_cap_factor", ascending=False)
    period_cols = [c for c in df.columns if c.startswith("water_slack_")]
    periods = [c.replace("water_slack_", "") for c in period_cols]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    width = 0.18
    x = np.arange(len(df))
    for idx, period in enumerate(periods):
        ax.bar(
            x + (idx - (len(periods) - 1) / 2) * width,
            df[f"water_slack_{period}"],
            width=width,
            label=period,
        )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(v * 100)}%" for v in df["water_cap_factor"]])
    ax.set_xlabel("Water cap (% of baseline period use)")
    ax.set_ylabel("Water slack")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(ncol=2)
    _save(fig, "fig_hier_water_binding", output_dirs)


def _heatmap(df: pd.DataFrame, value_col: str, title: str, filename: str, output_dirs: List[Path]) -> None:
    pivot = df.pivot(index="lambda_c", columns="lambda_w", values=value_col).sort_index(ascending=True)
    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    im = ax.imshow(pivot.values, origin="lower", aspect="auto", cmap="viridis")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(v)) for v in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(int(v)) for v in pivot.index])
    ax.set_xlabel("lambda_W")
    ax.set_ylabel("lambda_C")
    ax.set_title(title)
    fig.colorbar(im, ax=ax)
    _save(fig, filename, output_dirs)


def plot_price_heatmaps(price_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    price = price_df[price_df["status"] == 2].copy()
    _heatmap(price, "expected_co2", "Achieved CO2 under internal prices", "fig_hier_price_heatmap_co2", output_dirs)
    _heatmap(price, "economic_cost", "Economic cost under internal prices", "fig_hier_price_heatmap_cost", output_dirs)


def plot_accounting(accounting_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    caps = accounting_df[(accounting_df["status"] == 2) & (accounting_df["accounting_experiment"] == "cap_85")]
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    labels = [v.replace("_", "\n") for v in caps["accounting_mode"]]
    ax.bar(labels, caps["expected_co2"], color="#2ca02c", alpha=0.8)
    ax.set_ylabel("Expected CO2 under accounting mode")
    ax.grid(True, axis="y", alpha=0.25)
    _save(fig, "fig_hier_accounting_comparison", output_dirs)


def plot_interconnection(eligibility_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    df = eligibility_df[eligibility_df["status"] == 2].sort_values("interconnect_cost_multiplier")
    fig, ax1 = plt.subplots(figsize=(6.2, 4.0))
    ax2 = ax1.twinx()
    ax1.plot(df["interconnect_cost_multiplier"], df["economic_cost"], marker="o", color="#1f77b4", label="Cost")
    ax2.plot(df["interconnect_cost_multiplier"], df["active_links"], marker="s", color="#d62728", label="Active links")
    ax1.set_xlabel("Interconnection cost multiplier")
    ax1.set_ylabel("Economic cost", color="#1f77b4")
    ax2.set_ylabel("Active workload links", color="#d62728")
    ax1.grid(True, alpha=0.25)
    _save(fig, "fig_hier_interconnection_sensitivity", output_dirs)


def plot_workload_allocation(allocation_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    labels = [
        x
        for x in ["Cost-only planning", "Handoff-contract hard envelope"]
        if x in set(allocation_df["label"])
    ]
    if not labels:
        return
    sites = sorted(allocation_df["site"].unique())
    fig, axes = plt.subplots(1, len(labels), figsize=(9.2, 3.6), sharey=True)
    if len(labels) == 1:
        axes = [axes]
    x = np.arange(len(sites))
    for ax, label in zip(axes, labels):
        df = allocation_df[allocation_df["label"] == label]
        inf = [df[(df["site"] == site) & (df["workload"] == "inf")]["expected_flow"].sum() for site in sites]
        train = [df[(df["site"] == site) & (df["workload"] == "train")]["expected_flow"].sum() for site in sites]
        ax.bar(x, inf, label="Inference", color="#1f77b4")
        ax.bar(x, train, bottom=inf, label="Training", color="#ff7f0e", alpha=0.75)
        ax.set_title(label)
        ax.grid(True, axis="y", alpha=0.25)
        ax.set_xticks(x)
        ax.set_xticklabels(sites)
    axes[0].set_ylabel("Expected workload allocation")
    axes[0].legend(ncol=2)
    fig.tight_layout()
    _save(fig, "fig_hier_workload_allocation", output_dirs)


def plot_shadow_prices(shadow_df: pd.DataFrame, output_dirs: List[Path]) -> None:
    df = shadow_df[(shadow_df["constraint"] == "carbon_cap") & shadow_df["shadow_price"].notna()].copy()
    if df.empty:
        return
    df = df.sort_values("alpha", ascending=False)
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    ax.plot(df["alpha"] * 100, df["shadow_price"], marker="o", color="#444444")
    ax.invert_xaxis()
    ax.set_xlabel("Carbon cap (% of baseline)")
    ax.set_ylabel("Local conditional shadow price")
    ax.grid(True, alpha=0.25)
    _save(fig, "fig_hier_shadow_price", output_dirs)


def generate_all(results_dir: str = "results/hierarchical", latex_fig_dir: str = "latex/fig") -> None:
    root = Path(results_dir)
    output_dirs = [root / "figures", Path(latex_fig_dir)]
    supplement_dirs = [root / "supplement" / "figures"]
    _move_stale_main_figures(output_dirs, supplement_dirs[0])
    cap_df = pd.read_csv(root / "cap_sweep.csv")
    accounting_df = pd.read_csv(root / "accounting_experiments.csv")
    eligibility_df = pd.read_csv(root / "eligibility_experiments.csv")
    allocation_df = pd.read_csv(root / "allocation_by_site_workload.csv")
    shadow_df = pd.read_csv(root / "shadow_prices.csv")

    plot_cap_sweep(cap_df, output_dirs)
    plot_workload_allocation(allocation_df, output_dirs)

    supplement = root / "supplement"
    price_path = supplement / "price_sweep.csv"
    water_path = supplement / "water_experiments.csv"
    if price_path.exists():
        price_df = pd.read_csv(price_path)
        plot_frontier(cap_df, price_df, supplement_dirs)
        plot_price_heatmaps(price_df, supplement_dirs)
    if water_path.exists():
        water_df = pd.read_csv(water_path)
        plot_water_binding(water_df, supplement_dirs)
    plot_accounting(accounting_df, supplement_dirs)
    plot_interconnection(eligibility_df, supplement_dirs)
    plot_shadow_prices(shadow_df, supplement_dirs)
