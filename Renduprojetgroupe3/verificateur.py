"""
Vérificateur INDÉPENDANT.

Il n'utilise ni le modèle CP-SAT ni FCFS : il prend la liste EXPLICITE des
séances (une ligne = un patient, un jour, une machine, un créneau) et
re-vérifie toutes les règles métier une par une. Il sert à prouver que les
plannings produits sont corrects, sans faire confiance au code qui les produit.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from typing import Dict, List

from instance import Instance

Planning = Dict[int, dict]


def planning_vers_seances(inst: Instance, planning: Planning) -> List[dict]:
    """Déplie un planning compact (machine, début, créneau) en séances individuelles."""
    seances = []
    for pid, a in planning.items():
        p = inst.patient(pid)
        for k in range(p.nb_seances):
            seances.append({"patient": pid, "numero": k + 1, "jour": a["debut"] + k,
                            "machine": a["machine"], "creneau": a["creneau"]})
    return seances


def verifier(inst: Instance, seances: List[dict], delai_strict: bool = False) -> dict:
    erreurs: List[str] = []
    avertissements: List[str] = []
    S = inst.nb_creneaux

    par_patient = defaultdict(list)
    for x in seances:
        par_patient[x["patient"]].append(x)

    # R0 : chaque patient est planifié, et seulement les patients connus
    ids = {p.id for p in inst.patients}
    for pid in ids - set(par_patient):
        erreurs.append(f"Patient {pid} non planifié")
    for pid in set(par_patient) - ids:
        erreurs.append(f"Patient inconnu {pid} dans le planning")

    for pid, lst in par_patient.items():
        if pid not in ids:
            continue
        p = inst.patient(pid)
        lst.sort(key=lambda x: x["jour"])
        jours = [x["jour"] for x in lst]

        # R1 : bon nombre de séances
        if len(lst) != p.nb_seances:
            erreurs.append(f"P{pid} : {len(lst)} séances au lieu de {p.nb_seances}")
        # R2 : jours ouvrés consécutifs (indices contigus = pas de trou)
        if jours != list(range(jours[0], jours[0] + len(jours))):
            erreurs.append(f"P{pid} : séances non consécutives {jours}")
        # R3 : toujours la même machine
        if len({x["machine"] for x in lst}) != 1:
            erreurs.append(f"P{pid} : plusieurs machines utilisées")
        # R4 : créneau horaire stable
        if len({x["creneau"] for x in lst}) != 1:
            erreurs.append(f"P{pid} : créneau horaire non constant")
        m, s, d = lst[0]["machine"], lst[0]["creneau"], jours[0]
        # R5 : machine compatible avec la technique
        if m not in p.machines_compatibles:
            erreurs.append(f"P{pid} : machine {m} incompatible avec {p.technique}")
        # R6 : la séance tient dans la journée
        if not (0 <= s and s + p.duree <= S):
            erreurs.append(f"P{pid} : créneau {s} hors journée")
        # R7 : pas de début avant la fin de la préparation
        if d < p.debut_au_plus_tot:
            erreurs.append(f"P{pid} : début jour {d} < au plus tôt {p.debut_au_plus_tot}")
        # R8 : patients déjà en cours -> planning inchangé
        if p.fixe and (m, s, d) != (p.fixe["machine"], p.fixe["creneau"], p.fixe["debut"]):
            erreurs.append(f"P{pid} : planning d'un patient en cours modifié")
        # R9 : délai maximal selon la priorité
        if p.fixe is None and d > p.date_limite:
            msg = f"P{pid} (prio {p.priorite}) : début jour {d} > limite {p.date_limite}"
            (erreurs if delai_strict else avertissements).append(msg)

    # R10 : une machine ne traite qu'un patient par case (jour, créneau)
    occupation = {}
    for x in seances:
        p = inst.patient(x["patient"])
        for c in range(x["creneau"], x["creneau"] + p.duree):
            cle = (x["machine"], x["jour"], c)
            if cle in occupation and occupation[cle] != x["patient"]:
                erreurs.append(f"Conflit machine {cle[0]}, jour {cle[1]}, créneau {c} : "
                               f"P{occupation[cle]} et P{x['patient']}")
            occupation[cle] = x["patient"]

    return {"valide": not erreurs, "erreurs": erreurs, "avertissements": avertissements}


def exporter_csv(inst: Instance, seances: List[dict], chemin: str) -> None:
    """Export lisible : vraies dates, heures, noms de machines."""
    noms = {m.id: m.nom for m in inst.machines}
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["patient", "priorite", "technique", "seance", "date", "heure", "machine"])
        for x in sorted(seances, key=lambda x: (x["jour"], x["machine"], x["creneau"])):
            p = inst.patient(x["patient"])
            w.writerow([x["patient"], p.priorite, p.technique,
                        f"{x['numero']}/{p.nb_seances}",
                        inst.jour_vers_date(x["jour"]).isoformat(),
                        inst.creneau_vers_heure(x["creneau"]), noms[x["machine"]]])
