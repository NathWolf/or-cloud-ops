# Publication-Ready Evidence Package

This document describes the complete evidence package for the numerical analysis section of your OR/OM/analytics paper.

## Generated Outputs

### Tables (in `results/tables/`)

1. **Table 1: Instance Summary** (`table1_instance_summary.csv`, `.tex`)
   - Instance parameters: sites, regions, demand, costs, capacities, sustainability factors
   - Format: CSV and LaTeX for easy inclusion in papers

2. **Table 2: KPI Comparison** (`table2_kpi_comparison.csv`, `.tex`)
   - Baseline vs Capped-impact vs Scalarized models
   - Columns: Selected sites, Total cost, Total CO₂, Total water, Latency proxy, Sites opened
   - Shows how sustainability constraints change the solution

3. **Table 3: Site-level Shifts** (`table3_site_shifts.csv`, `.tex`)
   - Site-by-site comparison: baseline vs capped selections
   - Flow changes (Δ) showing redistribution behavior
   - Demonstrates which sites are shut out when constraints tighten

### Figures (in `results/figures/`)

#### Required Figures

1. **Figure 1 & 2: Side-by-Side Maps** (`fig_side_by_side_maps.png`)
   - Left: Baseline model spatial allocation
   - Right: Sustainability-aware model spatial allocation
   - Shows opened sites (green), regions (blue), and allocation flows
   - **Purpose**: Visual comparison showing solution changes

2. **Figure 3: KPI Bar Chart** (`fig_kpi_bars.png`)
   - Grouped bars comparing Baseline vs Capped vs Scalarized
   - Metrics: Total cost, Total CO₂, Total water
   - **Purpose**: Clear trade-off visualization

3. **Figure 4: Pareto/Trade-off Curves** 
   - `fig_tradeoff_cost_co2.png`: Cost vs CO₂ trade-off
   - `fig_tradeoff_cost_water.png`: Cost vs water trade-off
   - Points from scalarized scan with different λ weights
   - **Purpose**: Shows optimization produces a trade-off frontier

4. **Figure 5: Sensitivity Analysis** (`fig_sensitivity.png`)
   - Left: Total cost vs CO₂ cap percentage
   - Right: Number of sites opened vs CO₂ cap percentage
   - **Purpose**: Demonstrates policy sensitivity

#### Optional High-Value Figures

5. **Figure 6: Sustainability Heatmap** (`fig_sustainability_heatmap.png`)
   - Left: Baseline allocation matrix (sites × regions)
   - Right: Sustainability-aware allocation matrix
   - **Purpose**: Highlights rerouting/redistribution behavior

6. **Figure 7: Cumulative Impact Curves** (`fig_cumulative_impact.png`)
   - Left: Cumulative CO₂ vs cumulative demand %
   - Right: Cumulative water vs cumulative demand %
   - Baseline vs sustainability-aware comparison
   - **Purpose**: Shows how flow structure changed

#### Additional Supporting Figures

- `fig_all_sites.png`: All possible site locations (grey squares)
- `fig_baseline_selections.png`: Baseline selected sites (red)
- `fig_capped_selections.png`: Capped selected sites (blue)
- `fig_map.png`: Full map with allocations (baseline)
- `fig_eligibility.png`: Eligibility heatmap

## How to Use

### Generate Everything

```bash
# 1. Run all models
python scripts/run_all.py

# 2. Run sensitivity analysis
python scripts/run_sensitivity.py

# 3. Generate tables
python scripts/generate_tables.py

# 4. Generate all figures
python scripts/make_figures.py
```

### Minimal Set (for space-constrained papers)

**Tables:**
- Table 1 (Instance summary)
- Table 2 (KPI comparison)

**Figures:**
- Figure 1 & 2 (Side-by-side maps)
- Figure 3 (KPI bar chart)
- Figure 4 (Pareto frontier)

This minimal set satisfies reviewers and illustrates:
- The problem exists
- Sustainability constraints matter
- Trade-offs are observable

## Narrative Structure

Structure your numerical analysis section as follows:

1. **Describe the toy instance** (Table 1)
   - Instance size, parameter ranges, eligibility logic

2. **Present the baseline** (Figure 1 left + Table 2 row 1)
   - Cost-optimal solution without sustainability constraints

3. **Introduce sustainability mechanisms**
   - Capped-impact model (constraints)
   - Scalarized model (internalization)

4. **Show how solutions change**
   - New site set (Figure 1 & 2 comparison, Table 2)
   - KPI shifts (Figure 3, Table 2)
   - Site-level changes (Table 3)

5. **Plot trade-off frontier** (Figure 4)
   - Highlight non-dominated solutions
   - Show cost vs impact trade-offs

6. **(Optional) Sensitivity experiment** (Figure 5)
   - Policy sensitivity analysis
   - How tightening caps affects decisions

## Key Findings to Highlight

From the generated results:

- **Site Selection Changes**: Baseline selects S10, but capped model selects S4 instead (Table 3)
- **Cost-Impact Trade-off**: Capped model increases cost by 4.36% but reduces CO₂ by 15.4% and water by 23.8% (Table 2)
- **Sensitivity**: At 80% cap, cost jumps significantly and an additional site must be opened (Figure 5)
- **Flow Redistribution**: Allocation patterns shift to lower-impact sites (Figure 6, Table 3)

## Reproducibility

All results are reproducible:
- Instance saved to `data/toy_instance.json` (seed=3)
- All solutions saved as JSON files
- Scripts documented and executable

## File Organization

```
results/
├── tables/
│   ├── table1_instance_summary.csv
│   ├── table1_instance_summary.tex
│   ├── table2_kpi_comparison.csv
│   ├── table2_kpi_comparison.tex
│   ├── table3_site_shifts.csv
│   └── table3_site_shifts.tex
├── figures/
│   ├── fig_side_by_side_maps.png      # Figure 1 & 2
│   ├── fig_kpi_bars.png               # Figure 3
│   ├── fig_tradeoff_cost_co2.png      # Figure 4a
│   ├── fig_tradeoff_cost_water.png    # Figure 4b
│   ├── fig_sensitivity.png            # Figure 5
│   ├── fig_sustainability_heatmap.png # Figure 6
│   └── fig_cumulative_impact.png       # Figure 7
├── baseline_solution.json
├── capped_solution.json
├── scalarized_scan.json
├── sensitivity_analysis.json
└── runs.csv
```

## Notes for Publication

- All figures are generated without titles (as requested)
- Tables are available in both CSV (for review) and LaTeX (for final paper)
- Colors are consistent across plots
- Axis labels and units are clear
- All code is reproducible with seed=3

