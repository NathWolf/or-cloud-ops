# Quick Start Guide

This guide will help you run the toy CFLP problem and generate results.

## Prerequisites

1. **Python 3.10+** installed
2. **Gurobi** installed and licensed (see [Gurobi installation guide](https://www.gurobi.com/documentation/))
3. **Dependencies** installed:

```bash
pip install -r requirements.txt
```

Verify Gurobi installation:
```bash
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

## Running the Analysis

### Option 1: Run Everything at Once

```bash
python scripts/run_all.py
```

This will:
1. Generate a toy instance and solve the baseline model
2. Solve the capped-impact model
3. Run a scalarized scan over a grid of lambda values
4. Generate all figures

### Option 2: Run Scripts Individually

1. **Generate instance and solve baseline:**
   ```bash
   python scripts/run_baseline.py
   ```

2. **Solve capped-impact model:**
   ```bash
   python scripts/run_capped.py
   ```

3. **Run scalarized scan:**
   ```bash
   python scripts/run_scalarized_scan.py
   ```

4. **Generate figures:**
   ```bash
   python scripts/make_figures.py
   ```

## Output Files

After running, you'll find:

- **`data/toy_instance.json`**: Saved instance parameters for reproducibility
- **`results/runs.csv`**: Summary of all runs (model variant, parameters, KPIs)
- **`results/baseline_solution.json`**: Detailed baseline solution
- **`results/capped_solution.json`**: Detailed capped solution
- **`results/scalarized_scan.json`**: Scalarized scan results
- **`results/figures/`**: All generated figures
  - `fig_map.png`: Map showing sites, regions, and opened sites
  - `fig_eligibility.png`: Eligibility heatmap
  - `fig_tradeoff_cost_co2.png`: Cost vs CO₂ trade-off curve
  - `fig_tradeoff_cost_water.png`: Cost vs water trade-off curve
  - `fig_kpi_bars.png`: KPI comparison bar chart

## Customizing Parameters

### Instance Parameters

Edit the scripts to change:
- `n_sites`: Number of sites (default: 10)
- `n_regions`: Number of regions (default: 8)
- `seed`: Random seed for reproducibility (default: 3)
- `phi`: Latency penalty weight (default: 10.0)

### Capped Model Parameters

In `scripts/run_capped.py`, adjust:
- `alpha`: Cap as percentage of baseline (default: 0.85 = 85%)

### Scalarized Scan Grid

In `scripts/run_scalarized_scan.py`, modify:
- `lambda_c_values`: List of CO₂ penalty weights
- `lambda_w_values`: List of water penalty weights

## Troubleshooting

### Gurobi License Issues

If you see Gurobi license errors:
- Check your Gurobi license: `grbgetkey`
- For academic use, get a free academic license from [Gurobi](https://www.gurobi.com/academia/academic-program-and-licenses/)

### Import Errors

If you see import errors, make sure you're running from the project root:
```bash
cd /path/to/or-cloud-ops
python scripts/run_baseline.py
```

### Infeasible Models

If the capped model is infeasible:
- The caps may be too tight
- Try increasing `alpha` in `run_capped.py` (e.g., 0.90 or 0.95)

## Next Steps

- Review the generated figures in `results/figures/`
- Analyze the trade-offs in `results/runs.csv`
- Modify instance parameters to explore different scenarios
- Extend the models with additional constraints (see README.md)

