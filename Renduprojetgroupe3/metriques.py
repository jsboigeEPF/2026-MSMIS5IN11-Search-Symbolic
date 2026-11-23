"""Indicateurs de comparaison entre plannings."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from instance import Instance, PRIORITES

Planning = Dict[int, dict]


def indicateurs(inst: Instance, planning: Planning) -> dict:
    res = {}
    nv = inst.nouveaux_patients()
    for k, pr in PRIORITES.items():
        attentes = [planning[p.id]["debut"] - p.arrivee for p in nv if p.priorite == k]
        dans_delai = [planning[p.id]["debut"] <= p.date_limite for p in nv if p.priorite == k]
        nom = pr["nom"]
        res[f"{nom}_n"] = len(attentes)
        res[f"{nom}_attente_moy"] = round(float(np.mean(attentes)), 2) if attentes else np.nan
        res[f"{nom}_attente_max"] = int(max(attentes)) if attentes else np.nan
        res[f"{nom}_%_dans_delai"] = round(100 * float(np.mean(dans_delai)), 1) if dans_delai else np.nan

    attentes = [planning[p.id]["debut"] - p.arrivee for p in nv]
    res["global_attente_moy"] = round(float(np.mean(attentes)), 2)
    res["global_%_dans_delai"] = round(
        100 * float(np.mean([planning[p.id]["debut"] <= p.date_limite for p in nv])), 1)

    # Taux d'occupation des machines sur l'horizon [0, nb_jours)
    H = inst.nb_jours
    occupees = 0
    for p in inst.patients:
        a = planning[p.id]
        d0, d1 = a["debut"], a["debut"] + p.nb_seances
        jours_dans_horizon = max(0, min(d1, H) - max(d0, 0))
        occupees += jours_dans_horizon * p.duree
    res["occupation_%"] = round(100 * occupees / (H * inst.nb_creneaux * len(inst.machines)), 1)
    # Date de fin du dernier traitement (jours ouvrés)
    res["fin_dernier_traitement"] = max(planning[p.id]["debut"] + p.nb_seances
                                        for p in inst.patients)
    return res


def tableau_comparatif(resultats: Dict[str, dict]) -> pd.DataFrame:
    """resultats : {"FCFS": indicateurs(...), "CP-SAT": indicateurs(...)}"""
    return pd.DataFrame(resultats)
