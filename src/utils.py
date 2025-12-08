"""Utility functions for saving/loading instances and results."""
import json
from typing import Dict, Any
from pathlib import Path

from src.models.cflp import CFLPInstance, CFLPSolution


def save_instance(inst: CFLPInstance, filepath: str) -> None:
    """Save a CFLPInstance to JSON."""
    data = {
        "I": inst.I,
        "R": inst.R,
        "F": inst.F,
        "O": inst.O,
        "C": inst.C,
        "d": inst.d,
        "c": {f"{i},{r}": v for (i, r), v in inst.c.items()},
        "Lmax": inst.Lmax,
        "e_co2": inst.e_co2,
        "w": inst.w,
        "phi": inst.phi,
    }
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_instance(filepath: str) -> CFLPInstance:
    """Load a CFLPInstance from JSON."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    # Reconstruct arc dictionary
    c = {}
    for key, value in data["c"].items():
        i, r = key.split(",")
        c[(i, r)] = value
    
    return CFLPInstance(
        I=data["I"],
        R=data["R"],
        F=data["F"],
        O=data["O"],
        C=data["C"],
        d=data["d"],
        c=c,
        Lmax=data["Lmax"],
        e_co2=data["e_co2"],
        w=data["w"],
        phi=data.get("phi", 0.0),
    )


def solution_to_dict(sol: CFLPSolution, model_variant: str, **params) -> Dict[str, Any]:
    """Convert a CFLPSolution to a dictionary for CSV export."""
    return {
        "model_variant": model_variant,
        "status": sol.status,
        "obj": sol.obj,
        "total_cost": sol.total_cost,
        "total_latency_proxy": sol.total_latency_proxy,
        "total_co2": sol.total_co2,
        "total_water": sol.total_water,
        "opened_sites": sum(1 for v in sol.x.values() if v > 0.5),
        **params,
    }

