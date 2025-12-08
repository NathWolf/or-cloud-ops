#!/usr/bin/env python3
"""Run all model variants and generate figures in sequence."""
import sys
from pathlib import Path
import subprocess

def main():
    scripts_dir = Path(__file__).parent
    
    print("="*60)
    print("Running Complete CFLP Analysis Pipeline")
    print("="*60)
    
    scripts = [
        ("run_baseline.py", "Baseline Model"),
        ("run_capped.py", "Capped-Impact Model"),
        ("run_scalarized_scan.py", "Scalarized Scan"),
        ("make_figures.py", "Generate Figures"),
    ]
    
    for script_name, description in scripts:
        script_path = scripts_dir / script_name
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Script: {script_name}")
        print(f"{'='*60}\n")
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                cwd=scripts_dir.parent
            )
            print(f"\n✓ {description} completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"\n✗ {description} failed with exit code {e.returncode}")
            print("Continuing with next script...")
        except Exception as e:
            print(f"\n✗ Error running {script_name}: {e}")
            print("Continuing with next script...")
    
    print("\n" + "="*60)
    print("Pipeline Complete!")
    print("="*60)
    print("\nResults saved to:")
    print("  - data/toy_instance.json")
    print("  - results/runs.csv")
    print("  - results/*_solution.json")
    print("  - results/figures/*.png")


if __name__ == "__main__":
    main()

