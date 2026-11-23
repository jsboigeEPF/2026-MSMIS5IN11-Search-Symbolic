"""
Données du problème + générateur d'instances.

Convention de temps : on travaille en JOURS OUVRÉS indexés 0, 1, 2, ...
(jour 0 = lundi de la semaine 1, jour 5 = lundi de la semaine 2, etc.).
Avec cette convention, "séances consécutives les jours ouvrés" devient
simplement "un bloc de jours contigus", ce qui simplifie énormément le modèle.
La conversion en vraies dates (calendrier) est faite à l'affichage/export.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Paramètres "métier" (ordres de grandeur réalistes, à ajuster/justifier
# dans le rapport à l'aide de Vieira et al., 2016)
# ---------------------------------------------------------------------------

# Catégories de priorité
#   attente_max : délai maximal (en jours ouvrés) entre l'arrivée et la 1re séance
#   preparation : délai minimal incompressible (scanner, dosimétrie...)
#   proportion  : part des nouveaux patients dans cette catégorie
#   seances     : nombre de séances (min, max)
PRIORITES: Dict[int, dict] = {
    1: dict(nom="urgent", attente_max=2, preparation=0, proportion=0.15, seances=(5, 10)),
    2: dict(nom="prioritaire", attente_max=10, preparation=3, proportion=0.35, seances=(20, 35)),
    3: dict(nom="standard", attente_max=20, preparation=5, proportion=0.50, seances=(20, 35)),
}

# Techniques de traitement : durée d'une séance (en créneaux) et fréquence
TECHNIQUES: Dict[str, dict] = {
    "3D": dict(duree=1, proportion=0.45),
    "VMAT": dict(duree=1, proportion=0.45),
    "VMAT_complexe": dict(duree=2, proportion=0.10),
}


@dataclass
class Machine:
    id: int
    nom: str
    techniques: List[str]


@dataclass
class Patient:
    id: int
    arrivee: int                 # jour ouvré d'arrivée de la prescription
    priorite: int                # 1 = urgent, 2 = prioritaire, 3 = standard
    technique: str
    nb_seances: int
    duree: int                   # durée d'une séance, en créneaux
    machines_compatibles: List[int]
    debut_au_plus_tot: int       # arrivee + preparation
    date_limite: int             # arrivee + attente_max (dernier jour de début acceptable)
    # Patient déjà en cours de traitement au début de l'horizon (planning figé)
    fixe: Optional[dict] = None  # {"machine": m, "creneau": s, "debut": 0}


@dataclass
class Instance:
    nom: str
    nb_jours: int                # horizon d'arrivée des patients (jours ouvrés)
    nb_creneaux: int             # créneaux par jour et par machine
    machines: List[Machine]
    patients: List[Patient]
    heure_debut: str = "08:00"
    minutes_par_creneau: int = 30
    date_debut: str = "2027-01-04"   # un lundi
    # Les traitements commencés en fin d'horizon débordent : on prévoit une marge
    marge_jours: int = field(default=0)

    # ----- grandeurs dérivées -----
    @property
    def debut_max(self) -> int:
        """Dernier jour de début autorisé (marge pour absorber la file d'attente)."""
        return self.nb_jours + self.marge_jours

    @property
    def nb_jours_grille(self) -> int:
        """Taille de la grille temporelle (début max + plus long traitement)."""
        return self.debut_max + max(p.nb_seances for p in self.patients)

    def nouveaux_patients(self) -> List[Patient]:
        return [p for p in self.patients if p.fixe is None]

    def patient(self, pid: int) -> Patient:
        return self._index[pid]

    def __post_init__(self):
        self._index = {p.id: p for p in self.patients}
        if self.marge_jours == 0:
            self.marge_jours = self.nb_jours  # marge généreuse par défaut

    # ----- calendrier -----
    def jour_vers_date(self, j: int) -> date:
        d0 = date.fromisoformat(self.date_debut)
        semaine, jour = divmod(j, 5)
        return d0 + timedelta(weeks=semaine, days=jour)

    def creneau_vers_heure(self, s: int) -> str:
        h, m = map(int, self.heure_debut.split(":"))
        total = h * 60 + m + s * self.minutes_par_creneau
        return f"{total // 60:02d}:{total % 60:02d}"

    # ----- sérialisation JSON -----
    def to_json(self, chemin: str) -> None:
        d = {
            "nom": self.nom, "nb_jours": self.nb_jours, "nb_creneaux": self.nb_creneaux,
            "heure_debut": self.heure_debut, "minutes_par_creneau": self.minutes_par_creneau,
            "date_debut": self.date_debut, "marge_jours": self.marge_jours,
            "machines": [asdict(m) for m in self.machines],
            "patients": [asdict(p) for p in self.patients],
        }
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)

    @staticmethod
    def from_json(chemin: str) -> "Instance":
        with open(chemin, encoding="utf-8") as f:
            d = json.load(f)
        d["machines"] = [Machine(**m) for m in d["machines"]]
        d["patients"] = [Patient(**p) for p in d["patients"]]
        return Instance(**d)

    def resume(self) -> str:
        nv = self.nouveaux_patients()
        par_prio = {k: sum(p.priorite == k for p in nv) for k in PRIORITES}
        lignes = [
            f"Instance '{self.nom}' : {len(self.machines)} machine(s), "
            f"{self.nb_creneaux} créneaux/jour, {self.nb_jours} jours ouvrés "
            f"({self.nb_jours // 5} semaines)",
            f"  {len(nv)} nouveaux patients "
            + ", ".join(f"{PRIORITES[k]['nom']}={v}" for k, v in par_prio.items()),
            f"  {len(self.patients) - len(nv)} patients déjà en traitement au jour 0",
        ]
        for m in self.machines:
            lignes.append(f"  Machine {m.id} ({m.nom}) : {', '.join(m.techniques)}")
        return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Générateur
# ---------------------------------------------------------------------------

def _machines_par_defaut(nb_machines: int) -> List[Machine]:
    """Parc hétérogène : toutes les machines font du 3D, la plupart du VMAT,
    et seule la dernière (la plus récente) fait le VMAT complexe."""
    if nb_machines == 1:
        return [Machine(0, "LINAC-A", list(TECHNIQUES))]
    machines = []
    for i in range(nb_machines):
        tech = ["3D"]
        if i >= 1 or nb_machines == 2:
            tech.append("VMAT")
        if i == nb_machines - 1:
            tech.append("VMAT_complexe")
        machines.append(Machine(i, f"LINAC-{chr(65 + i)}", tech))
    return machines


def generer_instance(
    graine: int = 0,
    nb_machines: int = 3,
    nb_semaines: int = 8,
    nb_creneaux: int = 20,
    charge: float = 0.85,
    occupation_initiale: float = 0.6,
    nom: Optional[str] = None,
) -> Instance:
    """
    Génère une instance aléatoire réaliste.

    charge              : charge moyenne demandée par les nouveaux patients,
                          en fraction de la capacité totale (≈ 0.8-1.0 = service tendu)
    occupation_initiale : fraction des créneaux déjà occupés au jour 0 par des
                          patients en cours de traitement (sinon le service
                          démarrerait "à vide", ce qui est irréaliste)
    """
    rng = np.random.default_rng(graine)
    machines = _machines_par_defaut(nb_machines)
    nb_jours = 5 * nb_semaines
    patients: List[Patient] = []

    def compatibles(tech: str) -> List[int]:
        return [m.id for m in machines if tech in m.techniques]

    # --- 1) Patients déjà en traitement au jour 0 (planning figé) -------------
    pid = 0
    for m in machines:
        for s in range(nb_creneaux):
            if rng.random() < occupation_initiale:
                tech = "3D" if "VMAT" not in m.techniques else "VMAT"
                restant = int(rng.integers(1, 31))   # séances restantes
                patients.append(Patient(
                    id=pid, arrivee=-1, priorite=3, technique=tech,
                    nb_seances=restant, duree=1, machines_compatibles=[m.id],
                    debut_au_plus_tot=0, date_limite=0,
                    fixe={"machine": m.id, "creneau": s, "debut": 0},
                ))
                pid += 1

    # --- 2) Nouveaux patients : arrivées de Poisson ---------------------------
    # Nombre moyen de "cases" (jour x créneau) consommées par un patient
    cases_moy = 0.0
    for k, pr in PRIORITES.items():
        n_moy = sum(pr["seances"]) / 2
        if k == 1:
            d_moy = 1.0
        else:
            d_moy = sum(t["duree"] * t["proportion"] for t in TECHNIQUES.values())
        cases_moy += pr["proportion"] * n_moy * d_moy
    capacite_jour = nb_machines * nb_creneaux
    lam = charge * capacite_jour / cases_moy           # arrivées par jour ouvré

    prios = list(PRIORITES)
    p_prios = [PRIORITES[k]["proportion"] for k in prios]
    techs = list(TECHNIQUES)
    p_techs = [TECHNIQUES[t]["proportion"] for t in techs]

    for jour in range(nb_jours):
        for _ in range(rng.poisson(lam)):
            prio = int(rng.choice(prios, p=p_prios))
            pr = PRIORITES[prio]
            # Les urgences (souvent palliatives) : séances courtes en 3D
            tech = "3D" if prio == 1 else str(rng.choice(techs, p=p_techs))
            n = int(rng.integers(pr["seances"][0], pr["seances"][1] + 1))
            patients.append(Patient(
                id=pid, arrivee=jour, priorite=prio, technique=tech,
                nb_seances=n, duree=TECHNIQUES[tech]["duree"],
                machines_compatibles=compatibles(tech),
                debut_au_plus_tot=jour + pr["preparation"],
                date_limite=jour + pr["attente_max"],
            ))
            pid += 1

    return Instance(
        nom=nom or f"inst_s{graine}_m{nb_machines}_w{nb_semaines}_c{int(charge*100)}",
        nb_jours=nb_jours, nb_creneaux=nb_creneaux,
        machines=machines, patients=patients,
    )
