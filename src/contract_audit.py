"""Independent residual checks and executable strategic-to-operational handoff."""
import gurobipy as gp
from gurobipy import GRB
from src.models.hierarchical import build_hierarchical_model, solve_and_extract, emission_factor


def solve_contract(inst, carbon_cap, water_caps, *, plan=None,
                   scenario_wise=False, diagnose=False):
    """Freeze x, capacity and g for handoff; never silently relax physical service.

    diagnose=True minimizes normalized environmental excess with all service
    constraints hard. A positive optimum is a certificate of target infeasibility
    within the specified frozen envelope, not a feasible compliant schedule.
    """
    m, x, cap, g, y, _ = build_hierarchical_model(inst)
    if plan is not None:
        for i in inst.I:
            x[i].LB = x[i].UB = round(plan.x[i])
            cap[i].LB = cap[i].UB = plan.capacity[i]
        for link in inst.active_links():
            g[link].LB = g[link].UB = round(plan.g[link])
    excess = []
    groups = inst.Omega if scenario_wise else [None]
    for omega in groups:
        def weight(ww):
            return inst.prob[ww] if omega is None else float(ww == omega)
        e = gp.quicksum(weight(ww) * inst.e_location[i,t,ww] * v
                        for (i,r,t,k,ww),v in y.items())
        s = m.addVar(lb=0) if diagnose else 0
        m.addConstr(e <= carbon_cap * (1 + s), name=f"contract_carbon_{omega}")
        if diagnose:
            excess.append(s)
        for t in inst.T:
            w = gp.quicksum(weight(ww) * inst.water[i,tt,ww] * v
                           for (i,r,tt,k,ww),v in y.items() if tt == t)
            s = m.addVar(lb=0) if diagnose else 0
            m.addConstr(w <= water_caps[t] * (1+s), name=f"contract_water_{t}_{omega}")
            if diagnose:
                excess.append(s)
    if diagnose:
        m.setObjective(gp.quicksum(excess), GRB.MINIMIZE)
    sol = solve_and_extract(inst,m,x,cap,g,y,accounting_mode="location_time",
                            mip_gap=0.0,params={"scenario_wise":scenario_wise,
                            "fixed_plan":plan is not None,"diagnostic":diagnose})
    m.dispose()
    return sol


def residuals(inst, sol):
    """Recompute feasibility and objective without querying solver expressions."""
    if sol.obj is None:
        return {"status": sol.status, "has_solution": False}
    demand_error = max(abs(sum(sol.y.get((i,r,t,k,w),0) for i in inst.I)-d)
                       for (r,t,k,w),d in inst.demand.items())
    capacity_excess = max(sum(sol.y.get((i,r,t,k,w),0) for r in inst.R for k in inst.K)
                          - sol.capacity[i] for i in inst.I for t in inst.T for w in inst.Omega)
    link_excess = max(v-inst.demand[r,t,k,w]*sol.g[i,r,k]
                      for (i,r,t,k,w),v in sol.y.items())
    carbon = sum(inst.prob[w]*emission_factor(inst,i,t,w,sol.params['accounting_mode'])*v
                 for (i,r,t,k,w),v in sol.y.items())
    water = sum(inst.prob[w]*inst.water[i,t,w]*v for (i,r,t,k,w),v in sol.y.items())
    strategic_excess=max([sol.capacity[i]-inst.max_capacity[i]*sol.x[i] for i in inst.I]
                         +[sol.g[i,r,k]-sol.x[i] for i,r,k in inst.active_links()])
    integer_error=max(abs(v-round(v)) for v in list(sol.x.values())+list(sol.g.values()))
    return dict(status=sol.status,has_solution=True,demand_error=demand_error,
                capacity_excess=max(0,capacity_excess),link_excess=max(0,link_excess),
                strategic_excess=max(0,strategic_excess),integer_error=integer_error,
                carbon_error=abs(carbon-sol.expected_co2),water_error=abs(water-sol.expected_water))


def target_metrics(inst, sol, carbon_cap, water_caps):
    if sol.obj is None:
        return {}
    water_ratios=[sum(inst.water[i,tt,ww]*v for (i,r,tt,k,ww),v in sol.y.items()
                     if tt==t and ww==w)/water_caps[t] for t in inst.T for w in inst.Omega]
    return dict(expected_carbon_ratio=sol.expected_co2/carbon_cap,
                worst_carbon_ratio=max(sol.scenario_co2.values())/carbon_cap,
                expected_water_ratio=max(sol.period_water[t]/water_caps[t] for t in inst.T),
                worst_water_ratio=max(water_ratios))
