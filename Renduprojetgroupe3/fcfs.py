"""
Règle de référence : « premier arrivé, premier servi » (FCFS).

Les patients sont traités dans leur ordre d'arrivée. Chacun reçoit la PREMIÈRE
place libre (jour le plus tôt, puis machine, puis créneau) compatible avec
ses contraintes. On ne revient jamais sur une décision.
C'est ce que ferait une secrétaire médicale qui remplit l'agenda au fil de l'eau.

Variante ordre="priorite" : à jour d'arrivée égal, les urgents passent d'abord
(FCFS "intelligent", baseline plus exigeante).
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from instance import Instance

Planning = Dict[int, dict]   # id patient -> {"machine", "debut", "creneau"}


def planifier_fcfs(inst: Instance, ordre: str = "arrivee") -> Planning:
    G, S = inst.nb_jours_grille, inst.nb_creneaux
    # grille[m][jour, creneau] = True si la case est occupée
    grille = {m.id: np.zeros((G, S), dtype=bool) for m in inst.machines}
    planning: Planning = {}

    # 1) Les patients déjà en cours de traitement sont figés
    for p in inst.patients:
        if p.fixe is not None:
            m, s, d = p.fixe["machine"], p.fixe["creneau"], p.fixe["debut"]
            grille[m][d:d + p.nb_seances, s:s + p.duree] = True
            planning[p.id] = {"machine": m, "debut": d, "creneau": s}

    # 2) Les nouveaux patients, dans l'ordre d'arrivée
    if ordre == "arrivee":
        cle = lambda p: (p.arrivee, p.id)
    elif ordre == "priorite":
        cle = lambda p: (p.arrivee, p.priorite, p.id)
    else:
        raise ValueError(ordre)

    for p in sorted(inst.nouveaux_patients(), key=cle):
        place = None
        for d in range(p.debut_au_plus_tot, inst.debut_max + 1):
            for m in p.machines_compatibles:
                g = grille[m]
                for s in range(S - p.duree + 1):
                    if not g[d:d + p.nb_seances, s:s + p.duree].any():
                        place = (m, d, s)
                        break
                if place:
                    break
            if place:
                break
        if place is None:
            raise RuntimeError(f"FCFS : aucune place pour le patient {p.id} "
                               f"(augmenter marge_jours)")
        m, d, s = place
        grille[m][d:d + p.nb_seances, s:s + p.duree] = True
        planning[p.id] = {"machine": m, "debut": d, "creneau": s}

    return planning
