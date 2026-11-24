"""Export des résultats et figures de la démonstration."""
from pathlib import Path
import csv
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer


def save_outputs(problem, methods, k, output_dir="results"):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    initial, total = problem.initial_score, problem.total_population
    best = max(methods, key=lambda result: result.score)
    data = {
        "ville": problem.city,
        "donnees": "simulation synthétique" if problem.mode == "demo" else "Géo'DAE et INSEE Filosofi 2019",
        "rayon_m": problem.radius_m,
        "nombre_nouveaux_dae": k,
        "population_totale_estimee": round(total, 1),
        "population_deja_couverte": round(initial, 1),
        "resultats": [
            {"methode": r.name, "population_couverte": round(r.score, 1),
             "taux_couverture_pourcent": round(100 * r.score / total, 2),
             "gain_vs_initial": round(r.score - initial, 1),
             "temps_secondes": round(r.duration_s, 4),
             "contraintes_verifiees": problem.verify(r.selected, k)}
            for r in methods
        ],
        "meilleure_methode": best.name,
        "limites": ["Distance euclidienne, pas de cheminement piéton",
                    "La couverture géographique ne prédit pas directement la survie",
                    "Accès et disponibilité des DAE non contrôlés",
                    "Candidats limités aux centres de certains carreaux peuplés"]
    }
    (output / "resultats.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    with (output / "emplacements.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["rang", "methode", "latitude", "longitude", "x_m", "y_m"])
        for rank, idx in enumerate(best.selected, start=1):
            x, y = problem.candidates_xy[idx]
            if problem.mode == "real":
                lon, lat = transformer.transform(x, y)
                writer.writerow([rank, best.name, round(lat, 6), round(lon, 6),
                                 round(x, 1), round(y, 1)])
            else:
                writer.writerow([rank, best.name, "", "", round(x, 1), round(y, 1)])

    fig, ax = plt.subplots(figsize=(9, 6))
    names = [r.name for r in methods]
    percentages = [100 * r.score / total for r in methods]
    bars = ax.bar(names, percentages)
    ax.axhline(100 * initial / total, linestyle="--", color="gray", label="Couverture initiale")
    for bar, pct in zip(bars, percentages):
        ax.text(bar.get_x() + bar.get_width() / 2, pct + 0.4, f"{pct:.1f} %",
                ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Part de la population couverte (%)")
    ax.set_ylim(0, max(100, max(percentages) + 8))
    ax.set_title(f"Comparaison des méthodes : {problem.city} ({k} appareils)")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(output / "comparaison.png", dpi=160)
    plt.close(fig)

    covered = problem.covered_mask(best.selected)
    fig, ax = plt.subplots(figsize=(10, 8))
    offset = problem.demand_xy.min(axis=0)
    demand_km = (problem.demand_xy - offset) / 1000
    ex_km = (problem.existing_xy - offset) / 1000
    new_km = (problem.candidates_xy[list(best.selected)] - offset) / 1000
    sizes = 15 + 90 * problem.population / max(problem.population)
    ax.scatter(demand_km[~covered, 0], demand_km[~covered, 1], s=sizes[~covered],
               alpha=0.55, color="#E29A38", label="Population non couverte")
    ax.scatter(demand_km[covered, 0], demand_km[covered, 1], s=sizes[covered],
               alpha=0.35, color="#327A89", label="Population couverte")
    if len(ex_km):
        ax.scatter(ex_km[:, 0], ex_km[:, 1], marker="s", s=65,
                   facecolors="white", edgecolors="#194D54", linewidths=1.7,
                   label="DAE existants")
    ax.scatter(new_km[:, 0], new_km[:, 1], marker="*", s=230,
               color="#C83D48", edgecolors="black", linewidths=0.5,
               label="Nouveaux DAE proposés")
    for i, (x, y) in enumerate(new_km, 1):
        ax.annotate(str(i), (x, y), xytext=(7, 8), textcoords="offset points")
    # Cadrer sur la population plutôt que sur d'éventuels DAE aberrants.
    frame_min = demand_km.min(axis=0) - 1.0
    frame_max = demand_km.max(axis=0) + 1.0
    ax.set_xlim(frame_min[0], frame_max[0])
    ax.set_ylim(frame_min[1], frame_max[1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Distance relative Est (km)")
    ax.set_ylabel("Distance relative Nord (km)")
    ax.set_title(f"Implantation proposée : {problem.city}\n{best.name} | "
                 f"{100 * best.score / total:.1f} % couverts | rayon {problem.radius_m:.0f} m")
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(output / "implantation.png", dpi=170)
    plt.close(fig)
    return output
