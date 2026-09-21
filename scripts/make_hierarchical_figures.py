#!/usr/bin/env python3
"""Generate manuscript-ready figures for hierarchical experiments."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.plots_hierarchical import generate_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results/hierarchical")
    parser.add_argument("--latex-fig-dir", default="latex/fig")
    args = parser.parse_args()
    generate_all(args.results_dir, args.latex_fig_dir)
    print(f"Hierarchical figures written to {args.results_dir}/figures and {args.latex_fig_dir}")


if __name__ == "__main__":
    main()
