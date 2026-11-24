"""Lancement : python run.py --mode demo ou python run.py --mode real."""
import argparse
from pathlib import Path
from src.problem import make_demo, make_small_benchmark
from src.data import make_city_problem
from src.algorithms import evaluate_all, greedy, genetic, simulated_annealing, exact_ilp
from src.visualize import save_outputs


def print_table(problem, methods):
    print(f"\nVille : {problem.city} | type : {problem.mode} | rayon : {problem.radius_m:.0f} m")
    print(f"Population simulée/estimée : {problem.total_population:,.1f}"
          f" | couverte avant ajout : {problem.initial_score:,.1f}"
          f" ({100 * problem.initial_score / problem.total_population:.1f} %)")
    print(f"{'Méthode':<18} {'Couverture (%)':>15} {'Gain (habitants)':>18} {'Temps (s)':>12}")
    for r in methods:
        print(f"{r.name:<18} {100*r.score/problem.total_population:>14.2f}% "
              f"{r.score-problem.initial_score:>18.1f} {r.duration_s:>12.3f}")


def main():
    parser = argparse.ArgumentParser(description="Optimiser la localisation des défibrillateurs")
    parser.add_argument("--mode", choices=["demo", "real"], default="demo",
                        help="demo = données synthétiques ; real = sources publiques")
    parser.add_argument("--city-code", default="34172", help="Code INSEE, défaut : Montpellier")
    parser.add_argument("--city-name", default="Montpellier", help="Nom affiché")
    parser.add_argument("--k", type=int, default=5, help="Nombre de nouveaux défibrillateurs")
    parser.add_argument("--radius", type=float, default=350, help="Rayon en mètres")
    parser.add_argument("--max-candidates", type=int, default=160)
    parser.add_argument("--geodae-csv", help="Option : chemin du CSV Géo'DAE déjà téléchargé")
    parser.add_argument("--insee-zip", help="Option : chemin du ZIP INSEE déjà téléchargé")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="results")
    parser.add_argument("--skip-benchmark", action="store_true")
    args = parser.parse_args()

    if args.mode == "real":
        try:
            problem = make_city_problem(args.city_code, args.city_name, args.radius,
                                        args.max_candidates, args.geodae_csv, args.insee_zip)
        except Exception as exc:
            parser.exit(1, f"Impossible de charger les données réelles : {exc}\n"
                           "Consultez le README. Aucun basculement silencieux en mode démo.\n")
    else:
        problem = make_demo(seed=args.seed, radius_m=args.radius)

    methods = evaluate_all(problem, args.k, seed=args.seed)
    print_table(problem, methods)
    output = save_outputs(problem, methods, args.k, args.output)
    print(f"\nVérificateur : PASSÉ pour {len(methods)} méthodes")
    print(f"Fichiers exportés dans : {Path(output).resolve()}")

    if not args.skip_benchmark:
        small = make_small_benchmark()
        print("\n--- Validation sur petite instance (solution exacte ILP) ---")
        bench_k = 3
        reference = exact_ilp(small, bench_k)
        results = [greedy(small, bench_k), genetic(small, bench_k, seed=args.seed,
                                                  generations=70, population_size=30),
                   simulated_annealing(small, bench_k, seed=args.seed,
                                       iterations=1400), reference]
        for r in results:
            small.verify(r.selected, bench_k)
            gap = 100 * (reference.score - r.score) / max(reference.score, 1)
            print(f"{r.name:<18} {r.score:>9.1f} couverts | écart à l'optimum : {gap:>5.2f} %")
        with (output / "benchmark_exact.txt").open("w", encoding="utf-8") as f:
            f.write("Instance SYNTHÉTIQUE de petite taille, k=3, optimum certifié par ILP\n")
            for r in results:
                gap = 100 * (reference.score - r.score) / max(reference.score, 1)
                f.write(f"{r.name}: {r.score:.1f} individus, écart {gap:.2f} %, {r.duration_s:.3f} s\n")


if __name__ == "__main__":
    main()
