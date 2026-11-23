"""
Point d'entrée.

  python main.py demo                 # une instance : FCFS vs CP-SAT, graphiques, CSV
  python main.py demo --plan-b        # même chose avec une seule machine
  python main.py experiences          # plusieurs graines x plusieurs charges -> tableau
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from fcfs import planifier_fcfs
from graphiques import comparaison_attentes, gantt
from instance import generer_instance
from metriques import indicateurs, tableau_comparatif
from modele_cpsat import cout_planning, resoudre_cpsat
from verificateur import exporter_csv, planning_vers_seances, verifier


def comparer(inst, temps_limite=30.0, delai_strict=False, verbose=True):
    """Résout une instance avec FCFS, FCFS+priorité et CP-SAT ; vérifie tout."""
    plannings = {
        "FCFS": planifier_fcfs(inst, "arrivee"),
        "FCFS+prio": planifier_fcfs(inst, "priorite"),
    }
    meilleur_fcfs = min(plannings.values(), key=lambda pl: cout_planning(inst, pl))
    res = resoudre_cpsat(inst, temps_limite=temps_limite, delai_strict=delai_strict,
                         solution_initiale=meilleur_fcfs)
    if res["planning"] is None:
        raise RuntimeError(f"CP-SAT : {res['statut']}")
    plannings["CP-SAT"] = res["planning"]

    resultats = {}
    for nom, pl in plannings.items():
        v = verifier(inst, planning_vers_seances(inst, pl), delai_strict=False)
        assert v["valide"], f"{nom} invalide : {v['erreurs'][:5]}"
        ind = indicateurs(inst, pl)
        ind["cout_objectif"] = cout_planning(inst, pl)
        ind["depassements_delai"] = len(v["avertissements"])
        resultats[nom] = ind
        if verbose:
            print(f"  [vérificateur] {nom:9s} : planning VALIDE, "
                  f"{len(v['avertissements'])} dépassement(s) de délai")
    if verbose:
        print(f"  CP-SAT : {res['statut']} en {res['temps_s']} s, gap {res['gap_%']} %, "
              f"{res['nb_variables']} variables, {res['nb_contraintes']} contraintes")
    return plannings, resultats, res


def demo(args):
    os.makedirs(args.sortie, exist_ok=True)
    inst = generer_instance(graine=args.graine, nb_machines=1 if args.plan_b else args.machines,
                            nb_semaines=args.semaines, charge=args.charge)
    inst.to_json(os.path.join(args.sortie, f"{inst.nom}.json"))
    print(inst.resume())
    plannings, resultats, _ = comparer(inst, args.temps)
    df = tableau_comparatif(resultats)
    print(df.to_string())
    df.to_csv(os.path.join(args.sortie, "comparaison.csv"), sep=";")
    for nom, pl in plannings.items():
        f = nom.replace("+", "_").replace("-", "")
        gantt(inst, pl, f"{nom} — {inst.nom}", fichier=os.path.join(args.sortie, f"gantt_{f}.png"))
        exporter_csv(inst, planning_vers_seances(inst, pl),
                     os.path.join(args.sortie, f"seances_{f}.csv"))
    comparaison_attentes(inst, plannings, fichier=os.path.join(args.sortie, "attentes.png"))
    print(f"Résultats écrits dans {args.sortie}/")


def experiences(args):
    os.makedirs(args.sortie, exist_ok=True)
    lignes = []
    for charge in args.charges:
        for g in range(args.nb_graines):
            inst = generer_instance(graine=g, nb_machines=args.machines,
                                    nb_semaines=args.semaines, charge=charge)
            print(f"charge={charge} graine={g} ({len(inst.nouveaux_patients())} patients)")
            _, resultats, res = comparer(inst, args.temps, verbose=False)
            for methode, ind in resultats.items():
                lignes.append({"charge": charge, "graine": g, "methode": methode,
                               "statut_cpsat": res["statut"], **ind})
    df = pd.DataFrame(lignes)
    df.to_csv(os.path.join(args.sortie, "experiences_detail.csv"), sep=";", index=False)
    colonnes = ["urgent_attente_moy", "urgent_%_dans_delai", "prioritaire_attente_moy",
                "prioritaire_%_dans_delai", "standard_attente_moy", "standard_%_dans_delai",
                "global_%_dans_delai", "occupation_%", "cout_objectif"]
    synthese = df.groupby(["charge", "methode"])[colonnes].mean().round(1)
    synthese.to_csv(os.path.join(args.sortie, "experiences_synthese.csv"), sep=";")
    print(synthese.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="demo", choices=["demo", "experiences"])
    ap.add_argument("--graine", type=int, default=0)
    ap.add_argument("--machines", type=int, default=3)
    ap.add_argument("--semaines", type=int, default=8)
    ap.add_argument("--charge", type=float, default=0.9)
    ap.add_argument("--charges", type=float, nargs="+", default=[0.8, 0.9, 1.0])
    ap.add_argument("--nb-graines", type=int, default=5)
    ap.add_argument("--temps", type=float, default=30.0, help="temps limite CP-SAT (s)")
    ap.add_argument("--plan-b", action="store_true", help="une seule machine")
    ap.add_argument("--sortie", default="resultats")
    args = ap.parse_args()
    demo(args) if args.mode == "demo" else experiences(args)
