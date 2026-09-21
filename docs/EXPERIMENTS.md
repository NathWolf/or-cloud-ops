# Experiment guide

Run commands from the repository root. The frozen reference archive is `artifacts/revision_2026_09_21/`; new runs belong in `results/`.

## Workflow

| Step | Command | Main output |
| --- | --- | --- |
| Main experiment grid | `python scripts/run_hierarchical_experiments.py --require-public-data --output-dir results/revision_2026_09_21` | Regimes, price/cap sweeps, accounting comparisons and saved solutions |
| Contract and uncertainty audit | `python scripts/run_revision_audit.py --results-dir results/revision_2026_09_21` | Frozen-plan, scenario-wise, stress and seed tests |
| Independent checks | `python scripts/verify_revision.py results/revision_2026_09_21` | Fail-fast residual, objective and comparison assertions |
| Figure/table export | `python scripts/export_revision.py --results-dir results/revision_2026_09_21 --output-dir results/reproduced_figures` | Two main figures and one supplementary figure with plotted-value CSVs, four tables and numerical LaTeX macros |

`python scripts/run_all.py --figure-dir results/reproduced_figures` runs all four steps. `--quick` uses a smaller instance and does not run the full audit or export figures. Its results do not support the manuscript's numerical claims.

## Reference results

| Quantity | Reference value |
| --- | ---: |
| Expected-target cost premium over cost-only | 2.729% |
| Frozen cost-only plan under expected targets | Infeasible |
| Expected-plan worst carbon / target | 1.248 |
| Expected-plan worst seasonal water / target | 1.259 |
| Scenario-wise cost premium | 26.428% |
| Frozen scenario-wise plan after 5% demand increase | Infeasible |
| Expected-target premium over seeds 11–20 | 2.495–2.729% |

These are rounded summaries of the archived CSV files. Costs are normalized planning units, not operator expenditures. The scenario-wise plan is certified only for the modeled scenarios. The saved internal-price pair `(0, 5)` meets the expected targets; finite price sampling is not a global equivalence or impossibility proof.

## Archive contents and verification

- `instance.json` stores all input values and scenario probabilities.
- `solutions/` stores decisions, impacts, objectives, solver statuses and bound/gap metadata. There are 78 feasible saved solutions and two recorded infeasible solutions.
- `planning_regime_comparison.csv`, `cap_sweep.csv` and `supplement/` contain the primary comparisons.
- `handoff_audit.csv`, `stress_tests.csv` and `seed_sensitivity.csv` contain contract and uncertainty tests.
- `audit_manifest.json` records the reference environment, solver settings and source/data checksums. In the public copy, the machine hostname is omitted and the audit-script path is repository-relative. The original manifest's checksum records this publication transformation. No numerical values were changed.
- `SHA256SUMS.json` checks the integrity of every other file in the reference archive.

The original audit source hashes identify the files used for the September 2026 run. Release tooling and documentation can evolve without changing those original hashes. To compare a new run, prioritize objectives, feasibility and impacts rather than timestamps, runtime or a particular alternative optimum. Verification of saved infeasible statuses is not an independent proof of infeasibility; rerun the solver to reproduce that result.

## Scope

The experiment contains eight site zones, six demand regions, four equal-duration seasonal periods, three scenarios and two workload classes. First-stage sites, capacity and link activation are shared across scenarios. Recourse has perfect information within each scenario. Links use distance-based eligibility, and no interperiod workload deferral or endogenous network topology is modeled.

Carbon factors come from Ember; operational inputs are constructed. Water is assumed direct water use. Procurement discounts are hypothetical. The experiment tests how infrastructure choices constrain workload allocation. It does not reconstruct OVHcloud operations or measure organizational effectiveness.

## Reading the figures

1. **Supplementary Figure S1, infrastructure and allocation:** paired points compare cost-only and expected-target capacity commitments and training allocations by city. Capacity is per period; training allocation is the expected total across four periods. The selected sites and inference allocations are unchanged.
2. **Main Figure 1, cost and target interpretation:** four rows compare cost-only, expected-target, internal-price and scenario-wise plans. Cost excludes internal impact charges. Target-use points show expected and worst-scenario ratios; water additionally takes the maximum over seasons. Connecting lines are comparisons, not statistical uncertainty intervals.
3. **Main Figure 2, carbon and water trade-offs:** the carbon-only sweep and joint expected-target plan are plotted against achieved carbon reduction. Water use can rise under a carbon-only limit. Lines between solved plans do not establish feasibility at intermediate values.

The exporter writes `figure_commitments.csv`, `figure_target_use.csv` and `figure_tradeoffs.csv` with the plotted values. It recomputes scenario-water ratios from saved flows and checks the target ratios against the archived audit. Figures retain the same filenames so manuscript builds remain reproducible.

## Which commitments need revision?

`python scripts/run_commitment_review.py --output-dir results/commitment_review` solves five cases for each of seeds 11–20: allocation only; capacity plus allocation; links plus allocation; capacity and links plus allocation with sites fixed; and unrestricted planning. Every case retains the same service obligations and expected carbon/seasonal-water targets. The cost-only solution supplies all fixed values. Costs are pre-approval planning costs, not retrofit costs; sunk and conversion costs are excluded.

The reference is `artifacts/commitment_review_2026_09_21/`. Local Gurobi 12.0.3 and OVH Gurobi 13.0.2 agree on all 50 statuses and on feasible objective values within 1e-8. Neither capacity nor links alone restores feasibility in any seed. Reopening both reaches the unrestricted optimum without changing sites. In the reference solution, four links are added and three removed; the net link count masks this revision.

Verify saved cases with `python scripts/run_commitment_review.py --verify-only --output-dir artifacts/commitment_review_2026_09_21`. This recomputes residuals and targets, checks fixed decisions and the objective ordering under nested revision scopes, and verifies checksums. Infeasible statuses still require solving to reproduce. The full `run_all.py` pipeline includes these tests; `export_revision.py --commitment-dir PATH` selects their outputs for the main table. The original September experiment archive is unchanged.
