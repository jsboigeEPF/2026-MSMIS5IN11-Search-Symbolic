"""
Modèle CP-SAT (OR-Tools) pour la planification des séances de radiothérapie.

IDÉE CLÉ DE MODÉLISATION
------------------------
Comme toutes les séances d'un patient sont
  - sur des jours ouvrés consécutifs,
  - sur la même machine,
  - au même créneau horaire,
un patient est entièrement décrit par 3 décisions : (machine, jour de début, créneau).

Sur la grille "jours x créneaux" d'une machine, un patient est donc un
RECTANGLE de largeur nb_seances (en jours) et de hauteur duree (en créneaux).
La contrainte "une machine ne traite qu'un patient à la fois" devient :
les rectangles d'une même machine ne se chevauchent pas
  -> contrainte globale AddNoOverlap2D de CP-SAT.

Le choix de la machine est modélisé par des intervalles OPTIONNELS : pour
chaque machine compatible, un rectangle "présent" ou non, avec exactement
un rectangle présent par patient.

OBJECTIF
--------
Minimiser  Σ poids[prio] * attente  +  PENALITE * Σ poids[prio] * retard
  attente = jour de début - jour d'arrivée
  retard  = max(0, jour de début - date limite de la catégorie)
"""
from __future__ import annotations

import time
from typing import Dict, Optional

from ortools.sat.python import cp_model

from instance import Instance

Planning = Dict[int, dict]

POIDS_PRIORITE = {1: 10, 2: 3, 3: 1}   # un jour d'attente d'un urgent "coûte" 10
PENALITE_RETARD = 100                  # dépasser le délai max coûte très cher


def resoudre_cpsat(
    inst: Instance,
    temps_limite: float = 60.0,
    delai_strict: bool = False,
    solution_initiale: Optional[Planning] = None,
    nb_workers: int = 8,
    verbose: bool = False,
) -> dict:
    """
    delai_strict      : True  -> le délai max par priorité est une contrainte DURE
                                 (le problème peut alors être infaisable)
                        False -> contrainte MOLLE, pénalisée dans l'objectif
    solution_initiale : planning (ex. FCFS) donné comme "hint" au solveur
                        -> CP-SAT part d'une bonne solution et ne peut que l'améliorer
    """
    model = cp_model.CpModel()
    S = inst.nb_creneaux

    debut, creneau, presence, retard = {}, {}, {}, {}
    x_intervalles = {m.id: [] for m in inst.machines}   # dimension "jours"
    y_intervalles = {m.id: [] for m in inst.machines}   # dimension "créneaux"
    termes_objectif = []

    for p in inst.patients:
        # ---------------- Variables de décision ----------------
        if p.fixe is not None:
            lo = hi = p.fixe["debut"]
            s_lo = s_hi = p.fixe["creneau"]
            machines = [p.fixe["machine"]]
        else:
            lo = p.debut_au_plus_tot
            hi = inst.debut_max if not delai_strict else min(p.date_limite, inst.debut_max)
            if hi < lo:  # délai strict impossible à tenir pour ce patient
                hi = lo
            s_lo, s_hi = 0, S - p.duree
            machines = p.machines_compatibles

        debut[p.id] = model.NewIntVar(lo, hi, f"debut_{p.id}")
        creneau[p.id] = model.NewIntVar(s_lo, s_hi, f"creneau_{p.id}")

        # ---------------- Choix de la machine ----------------
        for m in machines:
            b = model.NewBoolVar(f"sur_{p.id}_m{m}")
            presence[p.id, m] = b
            # Rectangle optionnel : [debut, debut + nb_seances) x [creneau, creneau + duree)
            x_intervalles[m].append(model.NewOptionalFixedSizeIntervalVar(
                debut[p.id], p.nb_seances, b, f"jours_{p.id}_m{m}"))
            y_intervalles[m].append(model.NewOptionalFixedSizeIntervalVar(
                creneau[p.id], p.duree, b, f"creneaux_{p.id}_m{m}"))
        model.AddExactlyOne(presence[p.id, m] for m in machines)

        # ---------------- Objectif ----------------
        if p.fixe is None:
            w = POIDS_PRIORITE[p.priorite]
            termes_objectif.append(w * (debut[p.id] - p.arrivee))
            r = model.NewIntVar(0, max(0, hi - p.date_limite), f"retard_{p.id}")
            model.Add(r >= debut[p.id] - p.date_limite)   # r >= 0 par son domaine
            retard[p.id] = r
            termes_objectif.append(PENALITE_RETARD * w * r)

    # ---------------- Pas de chevauchement sur une machine ----------------
    for m in inst.machines:
        model.AddNoOverlap2D(x_intervalles[m.id], y_intervalles[m.id])

    model.Minimize(sum(termes_objectif))

    # ---------------- Hint : solution de départ ----------------
    if solution_initiale:
        for pid, aff in solution_initiale.items():
            model.AddHint(debut[pid], aff["debut"])
            model.AddHint(creneau[pid], aff["creneau"])
            for (q, m), b in presence.items():
                if q == pid:
                    model.AddHint(b, int(m == aff["machine"]))

    # ---------------- Résolution ----------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = temps_limite
    solver.parameters.num_workers = nb_workers
    solver.parameters.log_search_progress = verbose
    t0 = time.perf_counter()
    statut = solver.Solve(model)
    duree = time.perf_counter() - t0

    res = {
        "statut": solver.StatusName(statut),
        "temps_s": round(duree, 2),
        "nb_variables": len(model.Proto().variables),
        "nb_contraintes": len(model.Proto().constraints),
        "planning": None,
    }
    if statut in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["objectif"] = solver.ObjectiveValue()
        res["borne_inf"] = solver.BestObjectiveBound()
        res["gap_%"] = round(100 * (res["objectif"] - res["borne_inf"])
                             / max(1.0, abs(res["objectif"])), 2)
        planning = {}
        for p in inst.patients:
            m = next(m for (q, m), b in presence.items() if q == p.id and solver.Value(b))
            planning[p.id] = {"machine": m,
                              "debut": solver.Value(debut[p.id]),
                              "creneau": solver.Value(creneau[p.id])}
        res["planning"] = planning
    return res


def cout_planning(inst: Instance, planning: Planning) -> float:
    """Calcule la même fonction objectif pour n'importe quel planning
    (permet de comparer FCFS et CP-SAT sur le même critère)."""
    total = 0
    for p in inst.nouveaux_patients():
        d = planning[p.id]["debut"]
        w = POIDS_PRIORITE[p.priorite]
        total += w * (d - p.arrivee) + PENALITE_RETARD * w * max(0, d - p.date_limite)
    return total
