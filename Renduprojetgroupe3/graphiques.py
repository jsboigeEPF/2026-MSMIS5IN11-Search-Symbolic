"""Visualisations : diagramme de Gantt par machine et comparaison des attentes."""
from __future__ import annotations

from typing import Dict, Optional

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

from instance import Instance, PRIORITES

Planning = Dict[int, dict]

COULEURS = {1: "#d62728", 2: "#ff7f0e", 3: "#1f77b4", "fixe": "#c7c7c7"}


def gantt(inst: Instance, planning: Planning, titre: str = "",
          nb_jours: Optional[int] = None, fichier: Optional[str] = None):
    """Un panneau par machine : x = jours ouvrés, y = créneaux horaires.
    Chaque patient = un rectangle (nb_seances jours x durée de séance)."""
    nb_jours = nb_jours or inst.nb_jours + 20
    M = len(inst.machines)
    fig, axes = plt.subplots(M, 1, figsize=(14, 2.8 * M), sharex=True, squeeze=False)
    for ax, m in zip(axes[:, 0], inst.machines):
        for p in inst.patients:
            a = planning[p.id]
            if a["machine"] != m.id:
                continue
            c = COULEURS["fixe"] if p.fixe else COULEURS[p.priorite]
            ax.add_patch(Rectangle((a["debut"], a["creneau"]), p.nb_seances, p.duree,
                                   facecolor=c, edgecolor="white", linewidth=0.6))
        ax.set_xlim(0, nb_jours)
        ax.set_ylim(inst.nb_creneaux, 0)
        ax.set_ylabel(f"{m.nom}\n({'/'.join(m.techniques)})", fontsize=8)
        yt = list(range(0, inst.nb_creneaux + 1, 4))
        ax.set_yticks(yt)
        ax.set_yticklabels([inst.creneau_vers_heure(s) for s in yt], fontsize=7)
        for sem in range(0, nb_jours, 5):
            ax.axvline(sem, color="black", linewidth=0.3, alpha=0.3)
        ax.axvline(inst.nb_jours, color="black", linestyle="--", linewidth=1)
    axes[-1, 0].set_xlabel("Jours ouvrés (traits fins = semaines ; tirets = fin de l'horizon d'arrivée)")
    legende = [Patch(color=COULEURS[k], label=PRIORITES[k]["nom"]) for k in PRIORITES]
    legende.append(Patch(color=COULEURS["fixe"], label="déjà en traitement"))
    fig.legend(handles=legende, loc="upper right", ncol=4, fontsize=8)
    fig.suptitle(titre, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    if fichier:
        fig.savefig(fichier, dpi=120)
        plt.close(fig)
    return fig


def comparaison_attentes(inst: Instance, plannings: Dict[str, Planning],
                         fichier: Optional[str] = None):
    """Attente moyenne et max par catégorie, pour chaque méthode, + délai max autorisé."""
    import numpy as np
    noms = list(plannings)
    prios = list(PRIORITES)
    nv = inst.nouveaux_patients()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    largeur = 0.8 / len(noms)
    for i, nom in enumerate(noms):
        moy, mx = [], []
        for k in prios:
            att = [plannings[nom][p.id]["debut"] - p.arrivee for p in nv if p.priorite == k]
            moy.append(np.mean(att) if att else 0)
            mx.append(max(att) if att else 0)
        x = np.arange(len(prios)) + i * largeur
        ax.bar(x, moy, largeur, label=f"{nom} (moyenne)")
        ax.scatter(x, mx, marker="v", color="black", zorder=3,
                   label="maximum" if i == 0 else None)
    for j, k in enumerate(prios):
        ax.hlines(PRIORITES[k]["attente_max"], j - 0.1, j + 0.8 - 0.1,
                  colors="red", linestyles="--", label="délai max autorisé" if j == 0 else None)
    ax.set_xticks(np.arange(len(prios)) + 0.4 - largeur / 2)
    ax.set_xticklabels([PRIORITES[k]["nom"] for k in prios])
    ax.set_ylabel("Attente avant la 1re séance (jours ouvrés)")
    ax.legend(fontsize=8)
    ax.set_title("Délais d'attente par catégorie de priorité")
    fig.tight_layout()
    if fichier:
        fig.savefig(fichier, dpi=120)
        plt.close(fig)
    return fig
