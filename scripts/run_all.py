#!/usr/bin/env python3
"""Reproduce the September 2026 manuscript pipeline without mixing smoke results."""
import argparse,os,subprocess,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--output-dir');p.add_argument('--figure-dir',default='latex/fig');a=p.parse_args()
 root=Path(__file__).resolve().parents[1]
 result=a.output_dir or ('results/revision_smoke' if a.quick else 'results/revision_2026_09_21')
 commands=[['scripts/run_hierarchical_experiments.py','--require-public-data','--output-dir',result]+(['--quick'] if a.quick else [])]
 if not a.quick:
  commands += [['scripts/run_revision_audit.py','--results-dir',result],['scripts/verify_revision.py',result],['scripts/export_revision.py','--results-dir',result,'--output-dir',a.figure_dir]]
 env=os.environ.copy();env.setdefault('MPLCONFIGDIR',str(root/'results/.mplcache'))
 for command in commands:subprocess.run([sys.executable,*command],cwd=root,env=env,check=True)
 print('Complete:',result)
 if a.quick:print('Smoke outputs were not exported to the manuscript.')
if __name__=='__main__':main()
