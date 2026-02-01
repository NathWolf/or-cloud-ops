"""Utility functions for saving/loading instances and results."""
import json
from typing import Dict, Any, Tuple
from pathlib import Path

from src.models.cflp import CFLPInstance, CFLPSolution

# Existing sites (existing infrastructure) - always opened
# These are named C1-C5 to distinguish from expansion sites S1-S5
EXISTING_SITES = ["C1", "C2", "C3", "C4", "C5"]


def get_site_label_mapping(inst: CFLPInstance) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Create identity mapping (sites are already named correctly).
    Existing sites are C1-C5 (existing infrastructure)
    Potential sites are S1-S5 (expansion sites)
    
    Returns:
        (site_to_label, label_to_site) - identity mappings (no transformation needed)
    """
    # Sites are already correctly named, so return identity mappings
    site_to_label = {site: site for site in inst.I}
    label_to_site = {site: site for site in inst.I}
    
    return site_to_label, label_to_site


def save_instance(inst: CFLPInstance, filepath: str) -> None:
    """Save a CFLPInstance to JSON."""
    data = {
        "I": inst.I,
        "R": inst.R,
        "F": inst.F,
        "O": inst.O,
        "C": inst.C,
        "c": {f"{i},{r}": v for (i, r), v in inst.c.items()},
        "e_co2": inst.e_co2,
        "w": inst.w,
        "phi": inst.phi,
    }
    
    # Add optional fields if present
    if inst.P is not None:
        data["P"] = inst.P
    if inst.d is not None:
        data["d"] = inst.d
    if inst.d_inf is not None:
        data["d_inf"] = inst.d_inf
    if inst.d_train is not None:
        data["d_train"] = inst.d_train
    if inst.Lmax is not None:
        data["Lmax"] = inst.Lmax
    if inst.Lmax_inf is not None:
        data["Lmax_inf"] = inst.Lmax_inf
    if inst.Lmax_train is not None:
        data["Lmax_train"] = inst.Lmax_train
    
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
    
    # Build instance with optional fields
    kwargs = {
        "I": data["I"],
        "R": data["R"],
        "F": data["F"],
        "O": data["O"],
        "C": data["C"],
        "c": c,
        "e_co2": data["e_co2"],
        "w": data["w"],
        "phi": data.get("phi", 0.0),
    }
    
    # Add optional fields if present
    if "P" in data:
        kwargs["P"] = data["P"]
    if "d" in data:
        kwargs["d"] = data["d"]
    if "d_inf" in data:
        kwargs["d_inf"] = data["d_inf"]
    if "d_train" in data:
        kwargs["d_train"] = data["d_train"]
    if "Lmax" in data:
        kwargs["Lmax"] = data["Lmax"]
    if "Lmax_inf" in data:
        kwargs["Lmax_inf"] = data["Lmax_inf"]
    if "Lmax_train" in data:
        kwargs["Lmax_train"] = data["Lmax_train"]
    
    return CFLPInstance(**kwargs)


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

