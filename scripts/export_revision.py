#!/usr/bin/env python3
"""Generate all main-paper numbers, tables and vector figures from archived runs."""
import argparse,json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'text.usetex':True,'text.latex.preamble':r'\usepackage[T1]{fontenc}\usepackage{lmodern}','font.family':'serif','font.serif':['Computer Modern Roman'],
 'font.size':10,'axes.labelsize':10,'axes.titlesize':10,'legend.fontsize':9,
 'xtick.labelsize':9,'ytick.labelsize':9,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':.6,'grid.linewidth':.4,'grid.alpha':.25,'lines.linewidth':1.3,
 'pdf.fonttype':42,'savefig.dpi':300})
BLUE='#0072B2';ORANGE='#D55E00';GREEN='#009E73'

def table(out,name,caption,label,cols,rows,spec,note=''):
 text=['\\begin{table}[tbp]','\\centering\\small',f'\\caption{{{caption}}}\\label{{{label}}}',
       f'\\begin{{tabular}}{{@{{}}{spec}@{{}}}}','\\toprule',' & '.join(cols)+r' \\',r'\midrule']
 text+=[' & '.join(map(str,r))+r' \\' for r in rows]
 text += [r'\bottomrule',r'\end{tabular}']
 if note:text += [r'\par\smallskip\begin{minipage}{\linewidth}\footnotesize '+note+r'\end{minipage}']
 text += [r'\end{table}']
 (out/(name+'.tex')).write_text('\n'.join(text)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--results-dir',default='artifacts/revision_2026_09_21');p.add_argument('--output-dir',required=True);a=p.parse_args()
 root=Path(a.results_dir);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 regimes=pd.read_csv(root/'planning_regime_comparison.csv'); audit=pd.read_csv(root/'handoff_audit.csv');seed=pd.read_csv(root/'seed_sensitivity.csv');cap=pd.read_csv(root/'cap_sweep.csv');acc=pd.read_csv(root/'accounting_experiments.csv');duals=pd.read_csv(root/'shadow_prices.csv')
 b=regimes.iloc[0];h=regimes.iloc[2];price=regimes.iloc[3];robust=audit[audit.experiment=='Scenario-wise targets / replan'].iloc[0]
 vals=dict(CostPremium=100*(h.economic_cost/b.economic_cost-1),ExcessMinimum=audit.iloc[3].minimum_normalized_excess,
 WorstCarbon=audit.iloc[1].worst_carbon_ratio,WorstWater=audit.iloc[1].worst_water_ratio,
 RobustCost=robust.cost,RobustPremium=100*(robust.cost/b.economic_cost-1),RobustCarbon=100*robust.expected_carbon_ratio,
 SeedMin=seed.cost_increase_pct.min(),SeedMax=seed.cost_increase_pct.max(),CarbonOnlyWater=cap[cap.alpha==.85].iloc[0].expected_water,BaselineWater=b.expected_water)
 (out/'results_numbers.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+f'{v:.3f}'+'}' for k,v in vals.items())+'\n')
 rows=[]
 for label,r,ct,wt in [('Cost-only / reporting',b,'No','No'),('Expected targets',h,'Yes','Yes'),('Prices $(0,5)$',price,'Yes','Yes')]:
  rows.append([label,f'{r.economic_cost:,.1f}',f'{r.expected_co2:.1f}',f'{r.expected_water:.1f}',ct,wt])
 rows += [['Frozen cost-only','Infeasible','--','--','--','--'],['Scenario-wise targets',f'{robust.cost:,.1f}',f'{robust.expected_carbon_ratio*.85*b.expected_co2:.1f}',f'{sum(json.loads((root/"solutions/audit_6.json").read_text())["period_water"].values()):.1f}','Yes','Yes']]
 table(out,'table_revision_regimes','Planning and downstream acceptance under common expected targets.','tab:regimes',
 ['Regime','Cost','Carbon','Water','C target','W target'],rows,'lrrrrr',
 'Cost is in normalized planning units; carbon is in kg CO$_2$-equivalent electricity-impact proxy and water in assumed litres. C/W tests use expected carbon and each expected seasonal-water target. The scenario-wise row also satisfies every modeled scenario. Infeasible means no compliant allocation exists for fixed sites, capacity and links; it is not a solver timeout.')
 labels={'location_time':'Seasonal, unadjusted','location_annual':'Annual, unadjusted','market_time':'Seasonal, adjusted','market_annual':'Annual, adjusted'}
 rows=[]
 for _,r in acc[acc.accounting_experiment=='cap_85'].iterrows():
  rows.append([labels[r.accounting_mode],f'{r.economic_cost:,.1f}',f'{r.expected_co2:.2f}',f'{r.common_boundary_carbon:.2f}',str(int(r.active_links))])
 table(out,'table_revision_accounting','Accounting sensitivity at the same numerical carbon cap (212.12).','tab:accounting',
 ['Factor convention','Cost','Own boundary','Common boundary','Links'],rows,'lrrrr',
 'Both impact columns use kg CO$_2$-equivalent electricity-impact proxy. Adjusted factors use assumed procurement discounts and are not certified market-based Scope~2 factors. The common boundary always uses unadjusted seasonal factors. The selected site set is unchanged.')
 rows=[]
 for _,r in cap.sort_values('alpha',ascending=False).iterrows():
  d=duals[(duals.constraint=='carbon_cap')&(duals.alpha==r.alpha)].iloc[0]
  iac=duals[duals.to_alpha==r.alpha]
  rows.append([f'{100*r.alpha:.0f}\\%',f'{r.economic_cost:.1f}',f'{r.expected_co2:.2f}',
    '--' if iac.empty else f'{iac.iloc[0].interval_abatement_cost:.3f}',f'{max(0,d.shadow_price):.3f}'])
 table(out,'table_revision_duals','Interval abatement costs and conditional recourse shadow prices.','tab:duals',
 ['Cap','Cost','Carbon','Interval ratio','LP tightening value'],rows,'rrrrr',
 'Each interval ratio starts at the preceding row. Both final columns are planning-cost units per kg of electricity-impact proxy; the LP fixes sites, links and continuous capacity. Values do not describe global mixed-integer derivatives.')
 def save(fig,name):
  fig.savefig(out/(name+'.pdf'),bbox_inches='tight',pad_inches=.04)
  fig.savefig(out/(name+'.png'),bbox_inches='tight',pad_inches=.04)
  plt.close(fig)
 allocation=pd.read_csv(root/'allocation_by_site_workload.csv')
 sites=['C1','C2','C3','C4','S1','S2','S3','S4'];cities=['Paris','Frankfurt','Amsterdam','Dublin','Stockholm','Warsaw','Madrid','Helsinki']
 fig,axes=plt.subplots(1,2,figsize=(6.3,3.05),sharey=True,layout='constrained')
 for ax,label,title in zip(axes,['Cost-only planning','Handoff-contract hard envelope'],['(a) Cost-only','(b) Expected targets']):
  d=allocation[allocation.label==label];inf=[d[(d.site==i)&(d.workload=='inf')].expected_flow.sum() for i in sites];train=[d[(d.site==i)&(d.workload=='train')].expected_flow.sum() for i in sites]
  x=np.arange(8);ax.bar(x,inf,color=BLUE,label='Inference',width=.68);ax.bar(x,train,bottom=inf,color=ORANGE,label='Training',width=.68)
  ax.set_xticks(x,cities,rotation=50,ha='right');ax.set_title(title,loc='left');ax.grid(axis='y');ax.set_axisbelow(True)
 axes[0].set_ylabel('Expected service units');axes[1].legend(frameon=False)
 save(fig,'fig_revision_allocation')
 fig,axes=plt.subplots(1,2,figsize=(6.3,2.8),sharey=True,layout='constrained')
 selected=audit.iloc[[0,1,5]]
 for ax,col,title in zip(axes,['carbon','water'],['(a) Carbon target use','(b) Seasonal-water target use']):
  x=np.arange(3);ax.bar(x-.18,selected['expected_'+col+'_ratio'],width=.35,color=BLUE,label='Expected');ax.bar(x+.18,selected['worst_'+col+'_ratio'],width=.35,color=ORANGE,label='Worst scenario')
  ax.axhline(1,color='black',ls='--',lw=.9);ax.set_xticks(x,['Cost-only','Expected\ntargets','Scenario-wise\ntargets']);ax.set_title(title,loc='left');ax.grid(axis='y');ax.set_axisbelow(True);ax.set_ylim(0,1.6)
 axes[0].set_ylabel('Impact / target');axes[1].legend(frameon=False,loc='upper right',fontsize=9)
 save(fig,'fig_revision_risk')
 fig,axes=plt.subplots(1,2,figsize=(6.3,2.6),layout='constrained')
 c=cap.sort_values('alpha');x=100*c.alpha
 axes[0].plot(x,c.economic_cost,color=BLUE,marker='o',ms=4);axes[0].set_ylabel('Economic cost (planning units)');axes[0].set_title('(a) Cost',loc='left')
 axes[1].plot(x,c.expected_co2,color=GREEN,marker='s',ms=4);axes[1].set_ylabel(r'Expected electricity impact (kg CO$_2$e)');axes[1].set_title('(b) Carbon',loc='left')
 for ax in axes:ax.invert_xaxis();ax.set_xlabel('Carbon cap (\\% of baseline)');ax.set_xticks([100,95,90,85,80,75]);ax.grid()
 save(fig,'fig_revision_frontier')

if __name__=='__main__':main()
