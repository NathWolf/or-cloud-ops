# Experiment guide

Run commands from the repository root. The frozen reference archive is `artifacts/revision_2026_09_21/`; new runs belong in `results/`.

## Workflow

| Step | Command | Main output |
| --- | --- | --- |
| Main experiment grid | `python scripts/run_hierarchical_experiments.py --require-public-data --output-dir results/revision_2026_09_21` | Regimes, price/cap sweeps, accounting comparisons and saved solutions |
| Contract and uncertainty audit | `python scripts/run_revision_audit.py --results-dir results/revision_2026_09_21` | Frozen-plan, scenario-wise, stress and seed tests |
| Independent checks | `python scripts/verify_revision.py results/revision_2026_09_21` | Fail-fast residual, objective and comparison assertions |
| Figure/table export | `python scripts/export_revision.py --results-dir results/revision_2026_09_21 --output-dir results/reproduced_figures` | Three PDF/PNG figures, three tables and numerical LaTeX macros |

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
