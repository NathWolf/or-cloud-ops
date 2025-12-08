# Sustainable Cloud Siting – Numerical Analysis (Toy CFLP)

This project implements the numerical analysis section for the paper:
a **Capacitated Facility Location Problem (CFLP)** for data-center siting with
(a) a **baseline** model, (b) **usage-based CO₂/water caps**, and (c) a **scalarized**
objective to explore trade-offs.

The intent is **illustrative**: a small toy instance to show how sustainability
constraints and/or internalization of impacts changes the siting/allocation solution.

---

## 1) What you will build

### Models
1. **Baseline CFLP**
   - Decision: open sites and assign demand to opened sites.
   - Objective: cost + optional latency proxy
   - Constraints: demand satisfaction, capacity, latency eligibility.

2. **Capped-impact CFLP**
   - Baseline +:
   - **CO₂ cap**: \(\sum_{r}\sum_{i\in A_r} e_i^{CO2} y_{ir} \le \Gamma_{CO2}\)
   - **Water cap**: \(\sum_{r}\sum_{i\in A_r} w_i y_{ir} \le \Gamma_W\)

3. **Scalarized CFLP**
   - Baseline objective +:
   - \(\lambda_C \sum e_i^{CO2} y_{ir} + \lambda_W \sum w_i y_{ir}\)
   - Solve for a grid of \((\lambda_C, \lambda_W)\) to generate a Pareto-style curve.

### Outputs / KPIs
For each solve, compute and report:
- **Total cost**: \(\sum_i (F_i + O_i) x_i\)
- **Latency proxy** (if used): \(\sum_{r}\sum_{i\in A_r} c_{ir} y_{ir}\)
- **Total CO₂**: \(\sum_{r}\sum_{i\in A_r} e_i^{CO2} y_{ir}\)
- **Total water**: \(\sum_{r}\sum_{i\in A_r} w_i y_{ir}\)
- Opened sites set \(\{i : x_i = 1\}\) and allocation flows \(y_{ir}\)

### Figures you will generate
Recommended minimum set:
1. **Map plot** (toy coordinates): sites + demand regions, highlight opened sites
2. **Eligibility heatmap**: which arcs \((i,r)\) are allowed (\(i \in A_r\))
3. **Trade-off curve** (from scalarized grid):
   - Cost vs CO₂
   - Cost vs water (or combined impact)
4. **Before/after bar chart**: compare baseline vs capped vs one scalarized point

---

## 2) Repository layout (suggested)

```
project/
  src/
    models.py           # gurobipy model builders + solve helpers (baseline/capped/scalarized)
    instance.py         # instance dataclass + validation + optional toy generator
    metrics.py          # KPI computation + helpers
    plots.py            # plotting functions (matplotlib)
  scripts/
    run_baseline.py
    run_capped.py
    run_scalarized_scan.py
    make_figures.py
  data/
    toy_instance.json   # optional: saved instance parameters for reproducibility
  results/
    runs.csv            # summary of runs (model variant, parameters, KPIs)
    figures/
      fig_map.png
      fig_eligibility.png
      fig_tradeoff_cost_co2.png
      fig_tradeoff_cost_water.png
      fig_kpi_bars.png
  README.md
```

You can start with a single file if preferred, but splitting into modules helps when the analysis grows.

---

## 3) Environment & dependencies

### Required
- Python 3.10+
- `gurobipy` (requires a working Gurobi installation and license)
- `numpy`, `pandas`, `matplotlib`

Install non-Gurobi deps:

```bash
pip install numpy pandas matplotlib
```

Gurobi installation/licensing varies by platform. Verify:

```bash
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

---

## 4) Data model (instance definition)

You need:
- Sets: sites \(I\), regions \(R\)
- Costs: \(F_i\), \(O_i\)
- Capacities: \(C_i\)
- Demand: \(d_r\)
- Latency/distance: \(c_{ir}\)
- Eligibility thresholds per region: \(L_r^{max}\), defining \(A_r = \{i: c_{ir} \le L_r^{max}\}\)
- Sustainability factors:
  - \(e_i^{CO2}\): CO₂ per unit served
  - \(w_i\): water per unit served
- Optional: \(\phi\) latency weight

### Units (pick ONE consistent interpretation)
To keep the toy instance coherent, choose:
- Demand \(d_r\): “service units” (abstract)
- Capacity \(C_i\): same service units
- CO₂ factor \(e_i^{CO2}\): kgCO₂e per service unit
- Water factor \(w_i\): liters per service unit
- Latency \(c_{ir}\): milliseconds or normalized distance (only a proxy unless you calibrate)

Document units in the numerical section to avoid ambiguity.

---

## 5) Running the three model variants

### A) Baseline
1. Build baseline model
2. Solve
3. Extract KPIs

Expected result: cheapest siting pattern under eligibility/capacity.

### B) Capped-impact
1. Start from the baseline model builder
2. Add CO₂ and water caps
3. Solve and compare:
   - Does it open “cleaner” sites?
   - Does it shift allocations to lower-impact sites?

**Choosing caps** (practical approach for toy):
- Solve baseline, compute \(CO2_0\), \(W_0\)
- Set \(\Gamma_{CO2} = \alpha\,CO2_0\) and \(\Gamma_W = \beta\,W_0\)
- Try \(\alpha,\beta \in \{0.95, 0.9, 0.85, 0.8\}\)

### C) Scalarized scan (trade-offs)
1. Keep feasibility constraints identical
2. Vary \((\lambda_C,\lambda_W)\) over a grid
3. For each solve, store KPIs
4. Plot cost vs impacts

Suggested grids:
- If costs are ~hundreds and impacts are ~tens, start with:
  - \(\lambda_C \in \{0, 1, 5, 10, 25, 50\}\)
  - \(\lambda_W \in \{0, 1, 5, 10, 25, 50\}\)

Adjust so that the added terms actually influence decisions (you should observe changing solutions).

---

## 6) Testing and validation checklist

### Feasibility checks
- Every region must have at least one eligible site: \(A_r \neq \emptyset\)
- Total capacity of potentially open sites should cover total demand
- If caps are too tight, the capped model can become infeasible:
  - Detect infeasibility and relax caps or report it (use IIS if needed)

### Sanity checks
- With \(\phi=0\), objective should ignore latency proxy
- If \(\lambda_C=\lambda_W=0\), scalarized model should match baseline
- Tightening caps should not decrease impacts (monotonicity check):
  - It may increase cost, and may change opened set and allocations

### Reproducibility
- Fix random seed for toy generator
- Save instance to JSON and reuse across runs

---

## 7) Recommended reporting (for the paper)

In the numerical analysis section:
1. Describe toy instance sizes: \(|I|\), \(|R|\)
2. Explain how costs, capacities, and impacts were generated (or provide a table)
3. Show baseline solution KPIs
4. Show capped solution KPIs (and whether caps bind)
5. Show scalarized trade-off curves
6. Provide brief interpretation:
   - “Cost increases by X% to reduce CO₂ by Y%”
   - “Allocation shifts from sites {…} to {…}”
   - “Latency eligibility keeps SLA feasibility”

Avoid claiming real-world calibration unless you actually calibrate.

---

## 8) Common pitfalls

- **Unit mismatch**: costs, demands, and impact factors not aligned
- **Eligibility too strict**: some regions have no feasible sites
- **Caps too tight**: infeasible capped model
- **Scalarization weights too small/large**: no solution change (too small) or weird dominance (too large)
- **Interpreting latency**: in toy examples, treat it as a proxy, not a real SLA metric unless you model it carefully

---

## 9) Next extensions (optional)

If you later want a richer demonstration:
- Add a **resilience constraint** (e.g., each region must be served by at least 2 sites)
- Add **multi-period opening** (strategic realism)
- Add **time-varying carbon intensity** (hourly grid mix)
- Add **portfolio renewable share** constraints

Keep the toy section minimal unless the paper’s contribution depends on these.

---
