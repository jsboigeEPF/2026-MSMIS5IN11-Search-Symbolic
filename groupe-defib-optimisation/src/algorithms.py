"""Méthodes d'optimisation : glouton, génétique, recuit simulé, exact ILP."""
from dataclasses import dataclass
import math
import time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import hstack, vstack, csr_matrix


@dataclass
class Result:
    name: str
    selected: tuple
    score: float
    duration_s: float
    history: list


def greedy(problem, k):
    start = time.perf_counter()
    if not 0 <= k <= len(problem.candidates_xy):
        raise ValueError("Nombre d'appareils demandé hors limites")
    selected = []
    mask = problem.cover_existing.copy()
    history = [problem.initial_score]
    for _ in range(k):
        # Une population déjà couverte ne compte pas une seconde fois.
        gains = ((~mask).astype(float) * problem.population) @ problem.cover_candidates
        gains[selected] = -1.0
        winner = int(np.argmax(gains))
        selected.append(winner)
        mask |= problem.cover_candidates[:, winner]
        history.append(float(problem.population[mask].sum()))
    return Result("Glouton", tuple(selected), problem.score(selected),
                  time.perf_counter() - start, history)


def simulated_annealing(problem, k, seed=42, iterations=3500):
    start = time.perf_counter()
    if not 0 <= k <= len(problem.candidates_xy):
        raise ValueError("Nombre d'appareils demandé hors limites")
    if k == 0 or k == len(problem.candidates_xy):
        r = greedy(problem, k)
        return Result("Recuit simulé", r.selected, r.score,
                      time.perf_counter() - start, [r.score])
    rng = np.random.default_rng(seed)
    current = tuple(greedy(problem, k).selected)
    current_score = problem.score(current)
    best, best_score = current, current_score
    history = [best_score]
    # La température décroît géométriquement entre deux échelles de gain.
    temp_start = max(1.0, problem.total_population * 0.025)
    temp_end = max(0.01, temp_start * 0.001)
    for step in range(iterations):
        new = list(current)
        position = int(rng.integers(k))
        available = np.setdiff1d(np.arange(len(problem.candidates_xy)),
                                 np.array(current), assume_unique=True)
        new[position] = int(rng.choice(available))
        new = tuple(new)
        new_score = problem.score(new)
        delta = new_score - current_score
        temp = temp_start * (temp_end / temp_start) ** (step / max(1, iterations - 1))
        if delta >= 0 or rng.random() < math.exp(delta / temp):
            current, current_score = new, new_score
            if current_score > best_score:
                best, best_score = current, current_score
        if step % max(1, iterations // 100) == 0:
            history.append(best_score)
    history.append(best_score)
    return Result("Recuit simulé", tuple(sorted(best)), best_score,
                  time.perf_counter() - start, history)


def genetic(problem, k, seed=42, population_size=55, generations=120,
            mutation_rate=0.35):
    start = time.perf_counter()
    m = len(problem.candidates_xy)
    if not 0 <= k <= m:
        raise ValueError("Nombre d'appareils demandé hors limites")
    if k == 0 or k == m:
        r = greedy(problem, k)
        return Result("Génétique", r.selected, r.score,
                      time.perf_counter() - start, [r.score])
    rng = np.random.default_rng(seed)
    pop = [tuple(sorted(rng.choice(m, size=k, replace=False).tolist()))
           for _ in range(population_size - 1)]
    # Une solution gloutonne sert de référence parmi la population initiale.
    pop.append(tuple(sorted(greedy(problem, k).selected)))
    best, best_score = None, -1
    history = []

    def tournament(population, scores):
        ids = rng.choice(len(population), size=min(3, len(population)), replace=False)
        return population[max(ids, key=lambda i: scores[int(i)])]

    def crossover(a, b):
        common = set(a) & set(b)
        pool = list((set(a) | set(b)) - common)
        rng.shuffle(pool)
        genes = list(common) + pool[:k - len(common)]
        if len(genes) < k:
            remaining = list(set(range(m)) - set(genes))
            rng.shuffle(remaining)
            genes += remaining[:k - len(genes)]
        return tuple(sorted(genes))

    def mutate(genes):
        if rng.random() < mutation_rate:
            genes = list(genes)
            at = int(rng.integers(k))
            free = np.setdiff1d(np.arange(m), np.array(genes), assume_unique=True)
            genes[at] = int(rng.choice(free))
            return tuple(sorted(genes))
        return genes

    for _ in range(generations):
        scores = [problem.score(g) for g in pop]
        elite_ids = np.argsort(scores)[-2:]
        winner = int(elite_ids[-1])
        if scores[winner] > best_score:
            best_score, best = scores[winner], pop[winner]
        history.append(best_score)
        new_pop = [pop[int(i)] for i in elite_ids]
        while len(new_pop) < population_size:
            a = tournament(pop, scores)
            b = tournament(pop, scores)
            new_pop.append(mutate(crossover(a, b)))
        pop = new_pop
    # Vérification de la dernière génération également.
    scores = [problem.score(g) for g in pop]
    winner = int(np.argmax(scores))
    if scores[winner] > best_score:
        best_score, best = scores[winner], pop[winner]
    history.append(best_score)
    return Result("Génétique", best, best_score,
                  time.perf_counter() - start, history)


def exact_ilp(problem, k, time_limit_s=20):
    """Programmation linéaire en nombres entiers (SciPy/HiGHS).

    x_j=1 si le candidat j est retenu ; y_i=1 si la population i est couverte.
    max somme population_i*y_i
    s.c. y_i <= baseline_i + somme_j cover_ij*x_j ; somme_j x_j = k.
    """
    start = time.perf_counter()
    m, n = len(problem.candidates_xy), len(problem.population)
    if not 0 <= k <= m:
        raise ValueError("Nombre d'appareils demandé hors limites")
    c = np.concatenate([np.zeros(m), -problem.population])
    A = hstack([-csr_matrix(problem.cover_candidates.astype(float)),
                csr_matrix(np.eye(n))], format="csr")
    limit = LinearConstraint(A, np.full(n, -np.inf),
                             problem.cover_existing.astype(float))
    count = LinearConstraint(csr_matrix(np.r_[np.ones(m), np.zeros(n)]).reshape(1, -1),
                             lb=[k], ub=[k])
    result = milp(c=c, integrality=np.ones(m + n),
                  bounds=Bounds(np.zeros(m + n), np.ones(m + n)),
                  constraints=[limit, count],
                  options={"time_limit": time_limit_s})
    if result.x is None or result.status != 0:
        raise RuntimeError(f"Résolution exacte non aboutie (status={result.status})")
    selected = tuple(np.flatnonzero(result.x[:m] >= 0.5).tolist())
    return Result("Exact ILP", selected, problem.score(selected),
                  time.perf_counter() - start, [problem.score(selected)])


def evaluate_all(problem, k, seed=42):
    methods = [greedy(problem, k), genetic(problem, k, seed=seed),
               simulated_annealing(problem, k, seed=seed)]
    for result in methods:
        problem.verify(result.selected, k)
    return methods
