"""Modèle de couverture maximale des défibrillateurs."""
from dataclasses import dataclass
import numpy as np
from scipy.spatial.distance import cdist


@dataclass
class CoverageProblem:
    # Coordonnées métriques en Lambert-93 (ou dans un repère métrique fictif en démo).
    demand_xy: np.ndarray
    population: np.ndarray
    candidates_xy: np.ndarray
    existing_xy: np.ndarray
    radius_m: float
    mode: str = "demo"
    city: str = "Ville fictive"

    def __post_init__(self):
        self.demand_xy = np.asarray(self.demand_xy, dtype=float).reshape(-1, 2)
        self.population = np.asarray(self.population, dtype=float).reshape(-1)
        self.candidates_xy = np.asarray(self.candidates_xy, dtype=float).reshape(-1, 2)
        self.existing_xy = np.asarray(self.existing_xy, dtype=float).reshape(-1, 2)
        if len(self.population) != len(self.demand_xy):
            raise ValueError("Une population par point de demande est nécessaire")
        if len(self.population) == 0 or len(self.candidates_xy) == 0:
            raise ValueError("Le problème nécessite des habitants et des candidats")
        if np.any(~np.isfinite(self.population)) or np.any(self.population < 0):
            raise ValueError("Les populations doivent être finies et positives")
        if self.radius_m <= 0:
            raise ValueError("Le rayon de couverture doit être strictement positif")
        self.cover_candidates = (cdist(self.demand_xy, self.candidates_xy) <= self.radius_m)
        self.cover_existing = (
            (cdist(self.demand_xy, self.existing_xy) <= self.radius_m).any(axis=1)
            if len(self.existing_xy) else np.zeros(len(self.population), dtype=bool)
        )

    def covered_mask(self, selected):
        selected = list(selected)
        if not selected:
            return self.cover_existing.copy()
        return self.cover_existing | self.cover_candidates[:, selected].any(axis=1)

    def score(self, selected):
        return float(self.population[self.covered_mask(selected)].sum())

    @property
    def total_population(self):
        return float(self.population.sum())

    @property
    def initial_score(self):
        return self.score([])

    def verify(self, selected, k):
        selected = list(selected)
        if len(selected) != k:
            raise ValueError(f"Il faut exactement {k} nouveaux appareils (reçu {len(selected)})")
        if len(set(selected)) != k:
            raise ValueError("Un emplacement ne peut pas être sélectionné deux fois")
        if any(not isinstance(i, (int, np.integer)) or i < 0 or i >= len(self.candidates_xy)
               for i in selected):
            raise ValueError("Indice d'emplacement invalide")
        score = self.score(selected)
        if score < self.initial_score - 1e-8 or score > self.total_population + 1e-8:
            raise ValueError("Incohérence dans le calcul de couverture")
        return True


def make_demo(seed=42, n=180, n_existing=7, n_candidates=70, radius_m=350):
    """Ville SYNTHÉTIQUE : les résultats ne sont pas des statistiques réelles."""
    rng = np.random.default_rng(seed)
    centers = np.array([[400, 500], [1250, 500], [850, 1350], [1800, 1450]])
    groups = rng.integers(0, len(centers), size=n)
    demand = centers[groups] + rng.normal(0, 280, size=(n, 2))
    demand = np.clip(demand, 0, 2200)
    population = rng.integers(20, 220, size=n).astype(float)
    # Choix reproductible des emplacements et des appareils déjà présents.
    indices = rng.choice(n, size=min(n, n_candidates + n_existing), replace=False)
    candidates = demand[indices[:n_candidates]].copy()
    existing = demand[indices[n_candidates:n_candidates + n_existing]].copy()
    return CoverageProblem(demand, population, candidates, existing, radius_m,
                           mode="demo", city="Ville fictive (simulation)")


def make_small_benchmark(seed=2026):
    """Petite instance indépendante pour comparer à la solution exacte ILP."""
    return make_demo(seed=seed, n=28, n_existing=2, n_candidates=12, radius_m=380)
