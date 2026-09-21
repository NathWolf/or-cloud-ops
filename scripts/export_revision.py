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

def table(out,name,caption,label,cols,rows,spec):
 text=['\\begin{table}[H]','\\centering\\small',f'\\caption{{{caption}}}\\label{{{label}}}',
       f'\\begin{{tabular}}{{@{{}}{spec}@{{}}}}','\\toprule',' & '.join(cols)+r' \\',r'\midrule']
 text+=[' & '.join(map(str,r))+r' \\' for r in rows]
 text += [r'\bottomrule',r'\end{tabular}']
 text += [r'\end{table}']
 (out/(name+'.tex')).write_text('\n'.join(text)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--results-dir',default='artifacts/revision_2026_09_21');p.add_argument('--output-dir',required=True);p.add_argument('--commitment-dir',default='artifacts/commitment_review_2026_09_21');p.add_argument('--diagnostic-dir',default='artifacts/handoff_diagnostics_2026_09_21');a=p.parse_args()
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
 table(out,'table_revision_regimes','Costs, impacts and target compliance.','tab:regimes',
 ['Regime','Cost','Carbon','Water','C target','W target'],rows,'lrrrrr')
 review=pd.read_csv(Path(a.commitment_dir)/'commitment_review.csv')
 reference=review[review.seed==11].set_index('case')
 labels_review=[('Allocation only','allocation_only',r'$x,K,g$'),
                ('Capacity and allocation','capacity_only',r'$x,g$'),
                ('Links and allocation','links_only',r'$x,K$'),
                ('Capacity, links and allocation','capacity_and_links',r'$x$'),
                ('All decisions','all_decisions','None')]
 rows=[]
 for label,case,fixed in labels_review:
  r=reference.loc[case];samples=review[review.case==case]
  rows.append([label,fixed,'Feasible' if r.status==2 else 'Infeasible',
               f'{r.cost_increase_pct:.3f}'+r'\%' if r.status==2 else '--',
               f'{int((samples.status==2).sum())}/{len(samples)}'])
 table(out,'table_revision_commitments','Feasibility after revising infrastructure decisions.','tab:commitment-review',
       ['Decisions reopened','Fixed','Reference case','Cost increase','Runs meeting targets'],rows,'llrrr')
 diagnostic=pd.read_csv(Path(a.diagnostic_dir)/'diagnostics.csv').set_index('case')
 rows=[]
 for label,case in [('Allocation only','allocation_only'),('Capacity and allocation','capacity_only'),('Links and allocation','links_only')]:
  r=diagnostic.loc[case]
  rows.append([label]+[f'{100*r[k]:.2f}' for k in ['carbon_excess','winter_water_excess','spring_water_excess','summer_water_excess','autumn_water_excess']])
 table(out,'table_revision_diagnostics','Target excess in minimum-excess allocations.','tab:handoff-diagnostics',
       ['Decisions reopened',r'\makecell{Carbon\\(\%)}',r'\makecell{Winter water\\(\%)}',r'\makecell{Spring water\\(\%)}',r'\makecell{Summer water\\(\%)}',r'\makecell{Autumn water\\(\%)}'],rows,'lrrrrr')
 labels={'location_time':'Seasonal, unadjusted','location_annual':'Annual, unadjusted','market_time':'Seasonal, adjusted','market_annual':'Annual, adjusted'}
 rows=[]
 for _,r in acc[acc.accounting_experiment=='cap_85'].iterrows():
  rows.append([labels[r.accounting_mode],f'{r.economic_cost:,.1f}',f'{r.expected_co2:.2f}',f'{r.common_boundary_carbon:.2f}',str(int(r.active_links))])
 table(out,'table_revision_accounting','Accounting sensitivity at the same numerical carbon cap (212.12).','tab:accounting',
 ['Factor convention','Cost','Own boundary','Common boundary','Links'],rows,'lrrrr')
 rows=[]
 for _,r in cap.sort_values('alpha',ascending=False).iterrows():
  d=duals[(duals.constraint=='carbon_cap')&(duals.alpha==r.alpha)].iloc[0]
  iac=duals[duals.to_alpha==r.alpha]
  rows.append([f'{100*r.alpha:.0f}\\%',f'{r.economic_cost:.1f}',f'{r.expected_co2:.2f}',
    '--' if iac.empty else f'{iac.iloc[0].interval_abatement_cost:.3f}',f'{max(0,d.shadow_price):.3f}'])
 table(out,'table_revision_duals','Interval abatement costs and conditional recourse shadow prices.','tab:duals',
 ['Cap','Cost','Carbon','Interval ratio','LP tightening value'],rows,'rrrrr')
 def save(fig,name):
  fig.savefig(out/(name+'.pdf'),bbox_inches='tight',pad_inches=.04)
  fig.savefig(out/(name+'.png'),bbox_inches='tight',pad_inches=.04)
  plt.close(fig)
 export_case_study_figures(root,out,b,cap,save)


def export_case_study_figures(root, out, baseline, cap, save):
 """Compare commitments, target interpretation, and carbon--water trade-offs.

 Plot inputs are exported alongside figures so every mark is traceable to a
 saved solution. Expected and worst water values are maxima over seasonal
 target ratios, not ratios of aggregated annual water use.
 """
 instance=json.loads((root/'instance.json').read_text())
 def solution(name):
  return json.loads((root/'solutions'/name).read_text())
 base=solution('baseline.json')
 joint=solution('handoff_hard_envelope.json')
 sites=instance['I']
 cities=[instance['metadata']['site_info'][i]['city'] for i in sites]
 allocation=pd.read_csv(root/'allocation_by_site_workload.csv')
 rows=[]
 for site,city in zip(sites,cities):
  row={'site':site,'city':city}
  for key,sol,label in [('baseline',base,'Cost-only planning'),
                        ('expected_targets',joint,'Handoff-contract hard envelope')]:
   row[key+'_capacity']=sol['capacity'][site]
   row[key+'_training']=allocation.loc[(allocation.site==site)&
      (allocation.workload=='train')&(allocation.label==label),'expected_flow'].sum()
  rows.append(row)
 commitments=pd.DataFrame(rows)
 commitments.to_csv(out/'figure_commitments.csv',index=False)
 fig,axes=plt.subplots(1,2,figsize=(6.3,3.25),sharey=True,layout='constrained')
 y=np.arange(len(sites))
 for ax,metric,title,xlabel in zip(axes,['capacity','training'],
     ['(a) Committed capacity','(b) Expected training allocation'],
     ['Service units per period','Service units over four periods']):
  old=commitments['baseline_'+metric];new=commitments['expected_targets_'+metric]
  ax.hlines(y,np.minimum(old,new),np.maximum(old,new),color='0.65',lw=1.2)
  ax.scatter(old,y,s=28,facecolors='white',edgecolors=BLUE,zorder=3,label='Cost-only')
  ax.scatter(new,y,s=24,marker='s',color=ORANGE,zorder=4,label='Expected targets')
  ax.set_title(title,loc='left');ax.set_xlabel(xlabel)
  ax.set_xlim(-.04*max(old.max(),new.max()),1.08*max(old.max(),new.max()))
  ax.grid(axis='x');ax.set_axisbelow(True);ax.tick_params(axis='y',length=0)
 axes[0].set_yticks(y,cities);axes[0].invert_yaxis()
 axes[0].legend(frameon=False,loc='lower right')
 save(fig,'fig_revision_allocation')

 carbon_cap=.85*base['expected_co2']
 water_caps={t:.9*v for t,v in base['period_water'].items()}
 rows=[]
 for label,name in [('Cost-only','baseline.json'),('Expected targets','handoff_hard_envelope.json'),
                    ('Prices (0, 5)','internal_price_nearest_targets.json'),
                    ('Scenario-wise targets','audit_6.json')]:
  sol=solution(name)
  water={(t,w):0. for t in instance['T'] for w in instance['Omega']}
  for key,flow in sol['y'].items():
   i,r,t,k,w=key.split('|')
   water[t,w]+=instance['water']['|'.join((i,t,w))]*flow
  cost=sum(sol[k] for k in ['total_first_stage_cost','expected_operating_cost','expected_latency_proxy'])
  rows.append(dict(plan=label,economic_cost=cost,cost_premium_pct=100*(cost/baseline.economic_cost-1),
      expected_carbon_ratio=sol['expected_co2']/carbon_cap,
      worst_carbon_ratio=max(sol['scenario_co2'].values())/carbon_cap,
      expected_water_ratio=max(sol['period_water'][t]/water_caps[t] for t in instance['T']),
      worst_water_ratio=max(v/water_caps[t] for (t,w),v in water.items())))
 risk=pd.DataFrame(rows)
 risk.to_csv(out/'figure_target_use.csv',index=False)
 # Check the recomputed plotted values against independently archived audit rows.
 audit=pd.read_csv(root/'handoff_audit.csv').set_index('experiment')
 for plan,experiment in [('Cost-only','Cost-only'),('Expected targets','Expected-target plan'),
                         ('Scenario-wise targets','Scenario-wise targets / replan')]:
  for metric in ['expected_carbon_ratio','worst_carbon_ratio','expected_water_ratio','worst_water_ratio']:
   assert np.isclose(risk.set_index('plan').loc[plan,metric],audit.loc[experiment,metric],atol=1e-9)
 fig,axes=plt.subplots(1,3,figsize=(6.3,2.85),sharey=True,layout='constrained',
                       gridspec_kw={'width_ratios':[.8,1,1]})
 y=np.arange(len(risk))
 axes[0].barh(y,risk.cost_premium_pct,height=.32,color='0.45')
 for yy,v in zip(y,risk.cost_premium_pct):
  axes[0].text(v+.65,yy,f'{v:.2f}',va='center',fontsize=9)
 axes[0].set_xlim(0,35);axes[0].set_xticks([0,15,30])
 axes[0].set_title('(a) Cost increase',loc='left');axes[0].set_xlabel(r'\% of baseline cost')
 axes[0].set_yticks(y,risk.plan);axes[0].invert_yaxis()
 for ax,metric,title in zip(axes[1:],['carbon','water'],['(b) Carbon','(c) Seasonal water']):
  expected=risk['expected_'+metric+'_ratio'];worst=risk['worst_'+metric+'_ratio']
  ax.hlines(y,expected,worst,color='0.65',lw=1.2)
  ax.scatter(expected,y,s=26,facecolors='white',edgecolors=BLUE,zorder=3,label='Expected')
  ax.scatter(worst,y,s=26,marker='s',color=ORANGE,zorder=3,label='Worst scenario')
  ax.axvline(1,color='black',ls='--',lw=.8)
  ax.set_xlim(.35,1.52);ax.set_xticks([.5,1,1.5]);ax.set_xlabel('Impact / target')
  ax.set_title(title,loc='left')
 for ax in axes:
  ax.set_ylim(3.5,-.75);ax.grid(axis='x');ax.set_axisbelow(True);ax.tick_params(axis='y',length=0)
 axes[2].legend(frameon=False,loc='lower right',bbox_to_anchor=(1,1.12),borderaxespad=0)
 save(fig,'fig_revision_risk')

 c=cap.sort_values('alpha',ascending=False).copy()
 c['carbon_reduction_pct']=100*(1-c.expected_co2/baseline.expected_co2)
 c['cost_increase_pct']=100*(c.economic_cost/baseline.economic_cost-1)
 c['water_change_pct']=100*(c.expected_water/baseline.expected_water-1)
 c['regime']='Carbon only'
 joint_cost=sum(joint[k] for k in ['total_first_stage_cost','expected_operating_cost','expected_latency_proxy'])
 joint_row=dict(alpha=.85,carbon_reduction_pct=100*(1-joint['expected_co2']/baseline.expected_co2),
                cost_increase_pct=100*(joint_cost/baseline.economic_cost-1),
                water_change_pct=100*(joint['expected_water']/baseline.expected_water-1),regime='Carbon + water')
 columns=['regime','alpha','carbon_reduction_pct','cost_increase_pct','water_change_pct']
 pd.concat([c,pd.DataFrame([joint_row])],ignore_index=True)[columns].to_csv(out/'figure_tradeoffs.csv',index=False)
 fig,axes=plt.subplots(1,2,figsize=(6.3,2.85),layout='constrained')
 for ax,col,title,ylabel in zip(axes,['cost_increase_pct','water_change_pct'],
     ['(a) Economic cost','(b) Expected water use'],
     [r'Cost increase (\% of baseline)',r'Water change (\% of baseline)']):
  ax.plot(c.carbon_reduction_pct,c[col],color=BLUE,marker='o',ms=4,label='Carbon only')
  ax.scatter(joint_row['carbon_reduction_pct'],joint_row[col],color=ORANGE,marker='s',s=32,
             zorder=4,label='Carbon + water')
  ax.set_ylabel(ylabel);ax.set_title(title,loc='left');ax.grid();ax.set_axisbelow(True)
  ax.set_xlabel(r'Achieved carbon reduction (\%)');ax.set_xlim(-1,27);ax.set_xticks([0,5,10,15,20,25])
 axes[0].set_ylim(-.15,3.65);axes[0].legend(frameon=False,loc='upper left')
 axes[1].axhline(0,color='0.4',ls='--',lw=.8);axes[1].set_ylim(-12.5,3)
 at85=c.loc[np.isclose(c.alpha,.85)].iloc[0]
 axes[1].annotate(r'85\% carbon cap',xy=(at85.carbon_reduction_pct,at85.water_change_pct),
                  xytext=(6,2),fontsize=9,arrowprops=dict(arrowstyle='-',color='0.4',lw=.6))
 save(fig,'fig_revision_frontier')

if __name__=='__main__':main()
