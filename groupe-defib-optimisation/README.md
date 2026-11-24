# C1 — Implantation de défibrillateurs publics : couverture maximale

Projet de **métaheuristiques et calcul évolutionnaire** (IA, EPF, 2026).

## Objectif

Choisir `k` emplacements pour de nouveaux défibrillateurs automatisés externes (DAE) afin de **maximiser la population couverte** dans un rayon de `R` mètres, en tenant compte des DAE existants. Une personne déjà couverte n'est comptée **qu'une fois**.

Notre approche implémente **trois méthodes** : un algorithme glouton (référence simple), un algorithme génétique et un recuit simulé. Sur un petit problème, nous calculons aussi l'optimum par **programmation linéaire en nombres entiers (ILP)** pour mesurer les éventuels écarts.

## Installation

Prérequis : **Python 3.10 ou version plus récente**.

```bash
python -m venv .venv
# Windows PowerShell : .venv\Scripts\Activate.ps1
# macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement immédiat : démonstration reproductible

```bash
python run.py --mode demo --k 5 --radius 350
```

Cette commande **n'a pas besoin d'Internet**. Elle utilise une **ville fictive** et des populations entièrement **synthétiques**. Elle sert à valider les méthodes et à disposer d'une démo de secours. Elle ne donne aucun résultat statistique sur Montpellier.

Résultats du scénario de démonstration (`seed=42`, rayon 350 m, 5 nouveaux DAE) :

| Méthode | Couverture totale | Gain estimé vs DAE existants |
| --- | ---: | ---: |
| DAE existants, sans ajout | 57,80 % | 0 |
| Glouton | 93,23 % | 7 613 habitants fictifs |
| Génétique | 93,81 % | 7 739 habitants fictifs |
| Recuit simulé | 93,81 % | 7 739 habitants fictifs |

Les deux métaheuristiques améliorent ici la solution gloutonne de **126 habitants fictifs**. Les algorithmes génétiques et le recuit simulé sont initialisés à partir de la solution gloutonne ; ils sont donc conçus pour être au moins aussi bons qu'elle, avec ces paramètres.

## Données réelles : Montpellier

```bash
python run.py --mode real --city-code 34172 --city-name Montpellier --k 5 --radius 350
```

Le premier lancement **télécharge les archives publiques volumineuses** et les place dans `data_cache/`, exclu de Git. Les exécutions suivantes réutilisent le cache. Si les serveurs limitent les téléchargements, les fichiers peuvent être téléchargés manuellement et fournis via :

```bash
python run.py --mode real --city-code 34172 --city-name Montpellier \
    --geodae-csv "chemin/vers/geodae.csv" \
    --insee-zip "chemin/vers/Filosofi2019_carreaux_200m_csv.zip"
```

Sur **PowerShell**, écrire la commande sur une seule ligne (ou utiliser l'accent grave à la place de `\`).

Les sources sont :

- **Géo'DAE**, base nationale des défibrillateurs (Ministère de la Santé / Atlasanté), extraction CSV : https://www.data.gouv.fr/datasets/geodae-base-nationale-des-defibrillateurs
- **INSEE Filosofi 2019**, données carroyées à 200 mètres, colonne `ind` représentant le nombre d'individus estimés : https://www.insee.fr/fr/statistiques/7655475

**Traitement** : on filtre la commune par son code INSEE (Montpellier : `34172`). On convertit les centres des carreaux de la projection EPSG:3035 à Lambert-93 (EPSG:2154), et les coordonnées géographiques des DAE de WGS84 (EPSG:4326) à Lambert-93. Ainsi, les distances sont calculées en mètres dans un système métrique projeté.

Les **emplacements candidats** sont les centres des `160` carreaux peuplés les plus importants (paramétrables avec `--max-candidates`) ; tous les carreaux de population de la commune entrent dans le calcul de couverture. Ce choix accélère le calcul mais ne garantit pas la meilleure implantation possible dans toute la commune.

> Il n'y a **aucun basculement automatique** en mode fictif si les données réelles ne chargent pas : le programme affiche une erreur et précise pourquoi.

## Modèle mathématique

Soient des points de population `i` (poids `p_i`), des emplacements candidats `j`, un rayon `R`, et `k` nouveaux DAE à placer. Les appareils existants donnent une couverture initiale `b_i` valant 0 ou 1. La matrice `a_ij` vaut 1 si la distance euclidienne entre `i` et `j` est inférieure ou égale à `R`, 0 sinon.

**Objectif** : maximiser `Σ_i p_i y_i` sous les contraintes :

- `Σ_j x_j = k` ;
- `y_i ≤ b_i + Σ_j a_ij x_j` pour chaque point `i` ;
- `x_j, y_i ∈ {0,1}`.

Les variables `x_j` indiquent les emplacements retenus ; `y_i` indique si la population du carreau `i` est couverte. La résolution exacte du petit problème utilise `scipy.optimize.milp` (solveur HiGHS).

## Algorithmes

1. **Glouton** : ajouter successivement l'emplacement apportant le plus de population **nouvellement** couverte.
2. **Génétique** : coder une solution par une combinaison de `k` indices uniques ; initialiser une population avec des solutions aléatoires et la solution gloutonne ; sélection par tournoi, croisement, mutation par échange et élitisme.
3. **Recuit simulé** : partir de la solution gloutonne, remplacer un emplacement par un autre, accepter toujours les améliorations et parfois les dégradations avec la probabilité `exp(Δ/T)` ; faire décroître `T`.
4. **Exact ILP** : résoudre le petit cas de test par programmation entière afin de connaître l'optimum et calculer l'écart des méthodes heuristiques.

## Résultats produits

La commande enregistre dans `results/` (dossier non versionné) :

- `implantation.png` : schéma spatial des points de population, appareils existants et nouveaux emplacements ;
- `comparaison.png` : couverture en pourcentage de chaque méthode ;
- `emplacements.csv` : coordonnées des emplacements recommandés (latitude et longitude seulement en mode réel) ;
- `resultats.json` : scores, gains, temps et vérification des contraintes ;
- `benchmark_exact.txt` : comparaison au solveur exact sur un petit cas synthétique.

Les trois algorithmes sont **évalués sur les mêmes données**, avec un nombre fixé de nouveaux DAE. Le vérificateur `CoverageProblem.verify()` confirme qu'ils rendent exactement `k` indices différents, tous valides, et que leur couverture est cohérente.

## Tests

```bash
python -m unittest discover -s tests -v
```

Les tests vérifient notamment le **non-double-comptage**, le respect des contraintes, la couverture gloutonne et la cohérence des résultats avec une solution ILP exacte sur une petite instance.

## Paramètres utiles

```bash
python run.py --help
python run.py --mode demo --k 3 --radius 500 --seed 7
python run.py --mode real --city-code 34172 --max-candidates 200 --skip-benchmark
```

## Limites et pistes d'amélioration

- **Distance à vol d'oiseau** : un rayon de 350 m n'est pas exactement 350 m de marche. Ajouter un graphe piéton serait une extension.
- **Disponibilité réelle** : certains DAE sont dans des bâtiments fermés ou ne sont pas utilisables à toute heure. Le prototype n'intègre pas leurs horaires ni un audit de fonctionnement.
- **Population** : la variable `ind` des carreaux Filosofi 2019 est un effectif estimé et parfois imputé, pas la population présente à tout instant ; les données ne sont pas à jour au jour de la soutenance.
- **Positions candidates** : les centres de carreaux ne sont pas des lieux d'installation validés ; une vérification terrain et des autorisations seraient nécessaires.
- **Objectif unique** : ce modèle n'intègre ni les coûts, ni le risque d'arrêt cardiaque, ni la circulation piétonne. Maximiser la population théoriquement couverte ne démontre pas une amélioration des chances de survie.
- **Métaheuristiques** : elles ne garantissent pas un optimum global pour un problème de taille réelle.

## Organisation des fichiers

```text
groupe-defib-optimisation/
├── run.py                  # Point d'entrée de la démonstration
├── README.md               # Guide d'utilisation, résultats et limites
├── requirements.txt        # Dépendances
├── .gitignore              # Exclure données et environnements
├── src/
│   ├── problem.py          # Modèle, couverture, vérificateur
│   ├── algorithms.py       # Glouton, génétique, recuit simulé et ILP
│   ├── data.py             # Sources publiques et préparation des données
│   └── visualize.py        # Exports, graphiques et carte schématique
└── tests/
    └── test_algorithms.py  # Tests automatisés
```

## Répartition du travail

À compléter par le groupe avant la soumission :

- **@pseudo1** : [partie réellement réalisée].
- **@pseudo2** : [partie réellement réalisée].
- **@pseudo3** : [partie réellement réalisée].

Ce projet est une **aide à la décision et une démonstration pédagogique**, pas un outil d'aménagement opérationnel certifié.
