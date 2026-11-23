# B1 — Planification des séances de radiothérapie avec CP-SAT

Projet IA · Programmation par contraintes et optimisation combinatoire

---

## Sommaire

1. [Le problème en bref](#1-le-problème-en-bref)
2. [Les deux méthodes comparées : FCFS et CP-SAT](#2-les-deux-méthodes-comparées--fcfs-et-cp-sat)
3. [Installation](#3-installation)
4. [Lancer le projet](#4-lancer-le-projet)
5. [Organisation des fichiers](#5-organisation-des-fichiers)
6. [Le générateur d'instances](#6-le-générateur-dinstances)
7. [La modélisation CP-SAT](#7-la-modélisation-cp-sat)
8. [Le vérificateur indépendant](#8-le-vérificateur-indépendant)
9. [Résultats](#9-résultats)
10. [Limites et extensions](#10-limites-et-extensions)
11. [Dépannage](#11-dépannage)
12. [Questions probables à l'oral](#12-questions-probables-à-loral)
13. [Références](#13-références)

---

## 1. Le problème en bref

Un service de radiothérapie dispose de plusieurs **accélérateurs** (machines LINAC). Chaque patient reçoit une prescription de **20 à 35 séances** (5 à 10 pour une urgence palliative), une par jour ouvré.

Pour chaque patient, le planning doit respecter quatre règles :

| Règle | Signification |
|---|---|
| Séances consécutives | tous les jours ouvrés, sans trou, du début à la fin du traitement |
| Même machine | un seul accélérateur, compatible avec la technique prescrite (3D, VMAT, VMAT complexe) |
| Même horaire | le patient revient au même créneau chaque jour |
| Délai maximal | la 1re séance doit avoir lieu avant un délai qui dépend de la priorité |

**Objectif** : réduire l'attente avant la première séance, en priorité pour les cas urgents.

---

## 2. Les deux méthodes comparées : FCFS et CP-SAT

### FCFS : « First Come, First Served » (premier arrivé, premier servi)

C'est la **méthode de référence**, simple et sans optimisation, comme une file d'attente à la boulangerie :
1. on trie les patients par jour d'arrivée ;
2. chacun prend la **première place libre** (jour le plus tôt, puis machine, puis créneau) ;
3. on ne revient jamais sur une décision.

**Sa faiblesse** : un patient urgent arrivé après des patients standards doit attendre la prochaine place libre.

Une variante **FCFS+prio** fait passer les urgents d'abord quand plusieurs patients arrivent le même jour.

### CP-SAT : le solveur de Google OR-Tools

- **CP** = *Constraint Programming* (programmation par contraintes) : on décrit des règles à respecter.
- **SAT** = *satisfiabilité* : la technique mathématique utilisée pour chercher des solutions.

On ne dit pas au solveur *comment* faire le planning : on lui donne **les règles** et **le but** (minimiser l'attente pondérée par la priorité), et il cherche le meilleur planning en considérant **tous les patients en même temps**. Il peut donc décaler un patient standard de quelques jours pour faire passer un urgent tout de suite.

| | FCFS | CP-SAT |
|---|---|---|
| Principe | ordre d'arrivée, première place libre | meilleur planning global |
| Temps de calcul | instantané | quelques secondes (limite réglable) |
| Rôle dans le projet | la référence à battre | notre solution |

---

## 3. Installation

Python 3.9 ou plus récent.

```bash
cd ~/Downloads/radiotherapie        # adapter le chemin
python3 -m pip install -r requirements.txt
```

Bibliothèques installées : `ortools`, `matplotlib`, `pandas`, `numpy`.

> **Important** : installez les bibliothèques avec **le même Python** que celui qui lance le code. Écrire `python3 -m pip` (et non `pip` tout court) garantit cela. Voir [Dépannage](#11-dépannage).

---

## 4. Lancer le projet

### Option A — Le notebook (recommandé pour présenter)

Ouvrir **`radiotherapie_cpsat.ipynb`** (VS Code ou Jupyter), choisir le noyau Python en haut à droite, puis **Run All**.
Le notebook déroule toute la démarche avec des explications : instance → FCFS → CP-SAT → vérificateur → comparaison → expériences → plan B.
Il est livré **déjà exécuté** : les résultats sont visibles sans rien lancer.

### Option B — En ligne de commande

| Commande | Ce qu'elle fait | Durée |
|---|---|---|
| `python3 main.py demo` | une instance : FCFS vs CP-SAT, vérification, graphiques, CSV | ~1 min |
| `python3 main.py demo --temps 10` | idem avec 10 s de calcul (pour une démo live) | ~20 s |
| `python3 main.py demo --plan-b` | plan B : une seule machine | ~30 s |
| `python3 main.py demo --charge 1.0` | service plus chargé (100 % de la capacité) | ~1 min |
| `python3 main.py experiences --nb-graines 3 --temps 15` | plusieurs instances × charges 80/90/100 % | ~3 min |
| `python3 tests.py` | prouve que le vérificateur détecte les plannings faux | 1 s |

Le bouton ▶ de VS Code sur `main.py` lance directement `demo`.

**Options disponibles** : `--graine` (instance aléatoire différente), `--machines`, `--semaines`, `--charge`, `--charges`, `--nb-graines`, `--temps` (limite CP-SAT en secondes), `--plan-b`, `--sortie` (dossier de sortie).

### Ce qui s'affiche

```
  [vérificateur] FCFS      : planning VALIDE, 13 dépassement(s) de délai
  [vérificateur] FCFS+prio : planning VALIDE, 12 dépassement(s) de délai
  [vérificateur] CP-SAT    : planning VALIDE, 5 dépassement(s) de délai
  CP-SAT : FEASIBLE en 30.18 s, gap 91.55 %, 654 variables, 800 contraintes
```
puis le tableau comparatif.

### Fichiers produits (dossier `resultats/`)

| Fichier | Contenu |
|---|---|
| `gantt_FCFS.png`, `gantt_CPSAT.png`, `gantt_FCFS_prio.png` | plannings : un panneau par machine, une ligne par créneau, une barre par patient |
| `attentes.png` | attente moyenne et maximale par catégorie, avec le délai autorisé |
| `comparaison.csv` | tableau des indicateurs (s'ouvre dans Excel, séparateur `;`) |
| `seances_*.csv` | planning complet avec **vraies dates, heures et noms de machines** |
| `inst_*.json` | l'instance générée (pour la rejouer à l'identique) |

Couleurs des Gantt : rouge = urgent, orange = prioritaire, bleu = standard, gris = déjà en traitement au jour 0.

Le mode `experiences` écrit dans `resultats/` (ou `--sortie`) : `experiences_detail.csv` (une ligne par instance et par méthode) et `experiences_synthese.csv` (moyennes par charge).

---

## 5. Organisation des fichiers

| Fichier | Rôle |
|---|---|
| `instance.py` | Données (machines, patients, priorités, techniques), **générateur** d'instances, sauvegarde JSON |
| `fcfs.py` | Méthode de référence **premier arrivé, premier servi** (+ variante avec priorité) |
| `modele_cpsat.py` | **Modèle CP-SAT** — n'est pas fait pour être lancé seul, il est appelé par `main.py` |
| `verificateur.py` | **Vérificateur indépendant** + export CSV avec vraies dates |
| `metriques.py` | Indicateurs : attente par catégorie, % dans les délais, taux d'occupation |
| `graphiques.py` | Gantt par machine, graphique des attentes |
| `main.py` | **Point d'entrée** : démo et campagne d'expériences |
| `tests.py` | Tests du vérificateur (8 erreurs injectées volontairement) |
| `radiotherapie_cpsat.ipynb` | Notebook de démonstration commenté |
| `requirements.txt` | Bibliothèques à installer |

---

## 6. Le générateur d'instances

Fichier `instance.py`. Il crée des services hospitaliers fictifs mais réalistes.

**Convention de temps** : on compte en **jours ouvrés** (jour 0 = lundi semaine 1, jour 5 = lundi semaine 2…). Ainsi « séances consécutives » = un bloc de jours contigus, et les week-ends sont gérés automatiquement. La conversion en vraies dates se fait à l'export.

**Parc de machines (hétérogène)**

| Machine | Techniques |
|---|---|
| LINAC-A | 3D |
| LINAC-B | 3D, VMAT |
| LINAC-C | 3D, VMAT, VMAT complexe (séance de 2 créneaux) |

**Catégories de patients**

| Catégorie | Part | Délai max | Préparation | Séances |
|---|---|---|---|---|
| Urgent | 15 % | 2 jours | 0 jour | 5 à 10 |
| Prioritaire | 35 % | 10 jours | 3 jours | 20 à 35 |
| Standard | 50 % | 20 jours | 5 jours | 20 à 35 |

**Autres paramètres par défaut** : 8 semaines, 20 créneaux de 30 min par jour (8h–18h), arrivées aléatoires selon une loi de Poisson calibrée pour une **charge** donnée (80 à 100 % de la capacité), et **60 % des créneaux déjà occupés** au jour 0 par des patients en cours de traitement (planning figé).

> Ces valeurs sont des **hypothèses** de travail, modifiables en tête de `instance.py` (dictionnaires `PRIORITES` et `TECHNIQUES`). Elles sont à justifier à l'aide de la revue de Vieira et al. (2016).

---

## 7. La modélisation CP-SAT

Fichier `modele_cpsat.py`.

### L'idée clé : un patient = un rectangle

Comme toutes les séances d'un patient sont consécutives, sur la même machine et au même créneau, un patient est entièrement décrit par **3 décisions** :

> **machine · jour de début · créneau**

Sur la grille *jours × créneaux* d'une machine, un patient occupe donc un **rectangle** :
- largeur = nombre de séances (en jours),
- hauteur = durée d'une séance (1 créneau, ou 2 pour le VMAT complexe).

```
créneaux ↓   jours ouvrés →
08:00  [gris■■■■■]  [bleu■■■■■■■■■■■■■■■]
08:30
09:00     [rouge■■■][orange■■■■■■■■■■■■■■■■]
09:30
10:00        [bleu■■■■■■■■■■■■■■■■■■■■■]   ← patient VMAT complexe :
10:30        [■■■■■■■■■■■■■■■■■■■■■■■■■]     2 créneaux de haut
```

Les trois premières règles (consécutif, même machine, même horaire) sont alors **vraies par construction**. Il ne reste qu'une vraie contrainte : **les rectangles d'une même machine ne doivent pas se chevaucher** → contrainte globale `AddNoOverlap2D`.

### Le modèle

```python
# Pour chaque patient p
debut[p]   = NewIntVar(arrivée + préparation, horizon)
creneau[p] = NewIntVar(0, 20 - durée)
sur[p, m]  = NewBoolVar()          # une par machine compatible
AddExactlyOne(sur[p, m])           # une seule machine

# Pour chaque machine m
AddNoOverlap2D(jours[m], creneaux[m])   # intervalles optionnels, actifs si sur[p, m]

Minimize( Σ poids[prio] × attente  +  100 × Σ poids[prio] × retard )
```

- **Intervalles optionnels** : pour chaque machine compatible, un rectangle existe mais n'est « présent » que si le patient est affecté à cette machine.
- **attente** = jour de début − jour d'arrivée.
- **retard** = max(0, jour de début − date limite).
- **Poids** : urgent ×10, prioritaire ×3, standard ×1. Un jour d'attente d'un urgent « coûte » 10 fois plus que celui d'un standard.
- **Pénalité ×100** sur le retard : le délai maximal est une contrainte **molle** (le solveur l'évite autant que possible, mais le problème reste soluble même si le service est saturé). L'option `delai_strict=True` la rend **dure**.
- **Hint** : la meilleure solution FCFS est donnée au solveur comme point de départ, il ne peut donc que l'améliorer.
- Paramètres modifiables en tête du fichier : `POIDS_PRIORITE`, `PENALITE_RETARD`.

### Statuts du solveur

- `OPTIMAL` : la meilleure solution possible est trouvée **et prouvée**.
- `FEASIBLE` : une bonne solution est trouvée dans le temps imparti, sans preuve qu'il n'existe pas mieux. Le **gap** indique l'écart avec la borne inférieure calculée par le solveur.

---

## 8. Le vérificateur indépendant

Fichier `verificateur.py`. Il **ne réutilise ni le modèle ni FCFS** : il déplie chaque planning en **séances individuelles** (patient, jour, machine, créneau) et revérifie chaque règle une par une :

1. nombre de séances exact
2. jours ouvrés consécutifs
3. une seule machine
4. créneau horaire constant
5. machine compatible avec la technique
6. séance contenue dans la journée
7. pas de début avant la fin de la préparation
8. planning des patients déjà en cours inchangé
9. délai maximal (signalé comme avertissement ; erreur si `delai_strict=True`)
10. aucun conflit : une machine ne traite qu'un patient par créneau

**Preuve que le vérificateur fonctionne** : `tests.py` part d'un planning valide, le casse volontairement de 8 façons (séance supprimée, trou dans la série, changement de machine, créneau qui bouge, machine incompatible, début trop tôt, conflit entre deux patients, patient oublié) et vérifie que chaque erreur est détectée.

---

## 9. Résultats

### Instance de démonstration

3 machines, 8 semaines, 103 nouveaux patients, charge 90 %, 30 s de calcul.

| Indicateur | FCFS | FCFS+prio | CP-SAT |
|---|---|---|---|
| Urgents dans les délais | 81,8 % | 81,8 % | **100 %** |
| Prioritaires dans les délais | 65,6 % | 68,8 % | **87,5 %** |
| Standards dans les délais | 100 % | 100 % | 98,3 % |
| **Tous patients dans les délais** | 87,4 % | 88,3 % | **95,1 %** |
| Attente moyenne des urgents | 1,45 j | 1,18 j | **0 j** |
| Attente moyenne des standards | 7,5 j | 7,8 j | 9,3 j |
| Patients en retard sur leur délai | 13 | 12 | **5** |
| Occupation des machines | 79,0 % | 79,1 % | 77,9 % |

### Selon la charge du service

Moyenne sur 3 instances par niveau de charge, 15 s de calcul par instance.

| Charge | Urgents dans les délais (FCFS → CP-SAT) | Tous patients dans les délais (FCFS → CP-SAT) |
|---|---|---|
| 80 % | 90,5 % → **100 %** | 97,7 % → **100 %** |
| 90 % | 74,3 % → **100 %** | 92,9 % → **97,1 %** |
| 100 % | 64,3 % → **86,3 %** | 93,0 % → **95,8 %** |

### Ce qu'il faut retenir

- CP-SAT **ne crée pas de capacité** (l'occupation reste la même) : il **réorganise l'ordre de passage**.
- Il fait passer **urgents et prioritaires d'abord** ; l'écart avec FCFS **se creuse quand le service sature**.
- Contrepartie : les **standards attendent un peu plus** (et parfois beaucoup pour l'un d'eux).
- FCFS+prio ne change presque rien : trier par priorité *au sein d'une même journée* ne suffit pas, il faut raisonner sur l'ensemble du planning.

> CP-SAT ne trouve pas toujours exactement la même solution en temps limité : en relançant, les chiffres varient légèrement.

---

## 10. Limites et extensions

### Limites

1. **Compromis d'équité** : les patients standards attendent plus (7,5 → 9,3 jours en moyenne, jusqu'à 34 jours pour l'un d'eux). Piste : ajouter un terme sur l'attente maximale.
2. **Comparaison favorable à CP-SAT** : il connaît toutes les arrivées à l'avance (planification *hors ligne*), alors que FCFS les découvre au jour le jour.
3. **Optimalité non prouvée** sur les grandes instances : avec 3 machines, le solveur s'arrête au temps limite avec un gap élevé. Avec 1 machine (plan B), l'optimum est prouvé en ~2 s.
4. **Paramètres hypothétiques** : délais, proportions, durées sont des ordres de grandeur, pas des données réelles d'un hôpital.

### Extensions possibles (non implémentées)

| Extension | Idée de mise en œuvre |
|---|---|
| Horizon glissant | chaque jour, replanifier uniquement les patients arrivés ; figer ceux qui ont commencé (comme les patients « déjà en traitement ») |
| Panne de machine | ajouter un rectangle fixe qui bloque la machine k jours, puis replanifier les patients touchés |
| Préférences horaires | pénaliser dans l'objectif un créneau hors de la plage souhaitée (matin / après-midi) |
| Équité | minimiser aussi l'attente maximale par catégorie |

---

## 11. Dépannage

**`ModuleNotFoundError: No module named 'ortools'`**
Les bibliothèques sont installées dans un autre Python que celui qui lance le code. Sur Mac avec Anaconda, VS Code utilise parfois `/usr/bin/python3` (Python système) au lieu de celui de conda. Deux solutions :
```bash
/usr/bin/python3 -m pip install --user ortools matplotlib pandas numpy   # installer dans le Python utilisé
```
ou, dans VS Code : `Cmd + Shift + P` → **Python: Select Interpreter** → choisir celui qui contient *conda* / *base*, puis `python -m pip install -r requirements.txt`.

**Rien ne se passe en lançant `modele_cpsat.py`**
Normal : ce fichier contient le modèle mais ne l'exécute pas. Lancer **`main.py`**.

**`error: the following arguments are required: mode`**
Ancienne version de `main.py`. Lancer `python3 main.py demo`, ou utiliser la version à jour où `demo` est le mode par défaut.

**`KeyboardInterrupt` / `^C`**
Le programme a été arrêté avec Ctrl+C. Le premier lancement est lent (chargement de pandas et OR-Tools), puis CP-SAT calcule pendant 30 s : il faut attendre ~1 minute sans rien toucher.

**Le calcul est trop long**
Réduire le temps limite : `--temps 10`. Ou réduire l'instance : `--semaines 4`.

---

## 12. Questions probables à l'oral

**Pourquoi CP-SAT plutôt qu'un algorithme glouton ?**
Un glouton (comme FCFS) prend chaque décision définitivement, sans voir les patients suivants. CP-SAT considère tous les patients en même temps et peut arbitrer entre eux.

**Pourquoi `AddNoOverlap2D` ?**
Parce qu'un patient forme un rectangle sur la grille jours × créneaux. C'est une contrainte globale que CP-SAT propage efficacement, au lieu d'écrire une contrainte par couple de patients et par case.

**Pourquoi un délai maximal « mou » ?**
Si le service est saturé, il peut être impossible de respecter tous les délais : avec une contrainte dure, le solveur répondrait « infaisable » et ne donnerait aucun planning. La pénalité ×100 fait qu'il ne dépasse un délai que s'il n'a pas le choix.

**Comment avez-vous choisi les poids 10 / 3 / 1 ?**
Ils traduisent l'ordre de priorité médicale ; ce sont des paramètres réglables. On peut montrer l'effet de les changer (par exemple 5 / 2 / 1).

**Pourquoi la même heure chaque jour ?**
Pour le confort et l'organisation du patient (transport, travail), et c'est une pratique courante en radiothérapie. C'est aussi ce qui rend la modélisation en rectangle possible.

**Que signifie « gap 90 % » ?**
Le solveur a trouvé une bonne solution, mais sa borne inférieure (ce qu'il peut prouver comme minimum possible) reste éloignée : il ne peut pas prouver l'optimalité. Ce n'est pas une mesure de la qualité du planning, qui est bien meilleur que FCFS.

**Le vérificateur ne fait-il pas confiance au modèle ?**
Non : il travaille sur la liste explicite des séances, sans importer le modèle ni FCFS, et `tests.py` montre qu'il détecte 8 types d'erreurs.

---

## 13. Références

- Vieira B., Hans E.W., van Vliet-Vroegindeweij C., van de Kamer J., van Harten W. (2016). *Operations research for resource planning and -use in radiotherapy: a literature review*. BMC Medical Informatics and Decision Making, 16:149.
- Google OR-Tools — documentation CP-SAT : https://developers.google.com/optimization/cp
- Notebooks du cours CoursIA (J.-S. Boige) :
  - [CSP-4-Scheduling](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-4-Scheduling.ipynb)
  - [App-4-JobShopScheduling](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Applications/CSP/App-4-JobShopScheduling.ipynb)
  - [Planners-7-OR-Tools](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/SymbolicAI/Planners/03-Advanced/Planners-7-OR-Tools.ipynb)
