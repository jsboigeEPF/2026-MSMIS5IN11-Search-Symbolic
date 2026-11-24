"""Téléchargement des sources officielles, sans versionner les gros fichiers."""
from pathlib import Path
import re
from itertools import chain
import zipfile
import tempfile
import py7zr
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from .problem import CoverageProblem

# Sources officielles : liens et détails documentés dans le README.
GEODAE_DATASET_API = "https://www.data.gouv.fr/api/1/datasets/geodae-base-nationale-des-defibrillateurs/"
GEODAE_CSV_FALLBACK = "https://www.data.gouv.fr/api/1/datasets/r/edb6a9e1-2f16-4bbf-99e7-c3eb6b90794c"
INSEE_ZIP = "https://www.insee.fr/fr/statistiques/fichier/7655475/Filosofi2019_carreaux_200m_csv.zip"
CACHE = Path(__file__).resolve().parents[1] / "data_cache"


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    print(f"Téléchargement vers {path.name} (peut être volumineux)...")
    try:
        with requests.get(url, timeout=(15, 180), stream=True,
                          headers={"User-Agent": "ProjetEtudiant-DefibCoverage/1.0"}) as response:
            response.raise_for_status()
            with open(tmp, "wb") as output:
                for block in response.iter_content(chunk_size=1024 * 1024):
                    if block:
                        output.write(block)
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return path


def get_sources(geo_csv=None, insee_zip=None):
    geodae = Path(geo_csv) if geo_csv else CACHE / "geodae.csv"
    insee = Path(insee_zip) if insee_zip else CACHE / "Filosofi2019_carreaux_200m_csv.zip"
    if not geodae.exists():
        try:
            r = requests.get(GEODAE_DATASET_API, timeout=20)
            r.raise_for_status()
            resources = r.json().get("resources", [])
            possible = [res for res in resources if res.get("format", "").lower() == "csv"]
            url = possible[0].get("url") if possible else GEODAE_CSV_FALLBACK
        except requests.RequestException:
            url = GEODAE_CSV_FALLBACK
        download(url, geodae)
    if not insee.exists():
        download(INSEE_ZIP, insee)
    return geodae, insee


def _csv_reader(path_or_file, **kwargs):
    """Lit les fichiers CSV officiels par blocs et reconnaît les délimiteurs."""
    sep = ";"
    preview = pd.read_csv(path_or_file, sep=sep, nrows=2,
                          encoding="utf-8-sig", low_memory=False)
    if len(preview.columns) == 1:
        sep = ","
    if hasattr(path_or_file, "seek"):
        path_or_file.seek(0)
    return pd.read_csv(path_or_file, sep=sep, encoding="utf-8-sig",
                       chunksize=40000, dtype=str, low_memory=False, **kwargs)


def load_population(zip_path, city_code):
    """Carreaux Filosofi 2019 : la variable `ind` est un proxy démographique."""
    code = str(city_code).zfill(5)
    frames = []
    pattern = re.compile(r"RES200mN(\d+)E(\d+)")
    # L'INSEE distribue ici un ZIP qui contient lui-même une archive 7z.
    # On extrait les CSV dans un répertoire temporaire sans les versionner.
    with tempfile.TemporaryDirectory(prefix="insee_defib_") as temporary:
        temp_dir = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            entries = archive.namelist()
            csv_files = [name for name in entries if name.lower().endswith(".csv")]
            seven_z_files = [name for name in entries if name.lower().endswith(".7z")]
            if not csv_files and not seven_z_files:
                raise ValueError("L'archive INSEE ne contient ni CSV ni 7z")
            for member in csv_files + seven_z_files:
                archive.extract(member, path=temp_dir)
        for seven_z in temp_dir.rglob("*.7z"):
            print(f"Extraction INSEE : {seven_z.name} (peut prendre un moment)...")
            with py7zr.SevenZipFile(seven_z, mode="r") as nested:
                nested.extractall(path=temp_dir)
        csv_paths = list(temp_dir.rglob("*.csv"))
        if not csv_paths:
            raise ValueError("Aucun fichier CSV trouvé après extraction du 7z INSEE")
        csv_paths.sort(key=lambda path: ("200" not in path.name.lower(), len(path.name)))
        for csv_path in csv_paths:
            try:
                iterator = _csv_reader(csv_path)
                first = next(iterator, None)
                if first is None or not {"lcog_geo", "idcar_200m", "ind"}.issubset(first.columns):
                    continue
                for chunk in chain([first], iterator):
                    selected = chunk[chunk["lcog_geo"].fillna("").str.contains(
                        rf"(?<!\d){re.escape(code)}(?!\d)", regex=True)]
                    if not selected.empty:
                        frames.append(selected[["idcar_200m", "ind"]].copy())
            except (UnicodeError, pd.errors.ParserError):
                continue
    if not frames:
        raise ValueError(f"Aucun carreau INSEE trouvé pour la commune {code}")
    df = pd.concat(frames, ignore_index=True).drop_duplicates("idcar_200m")
    coords = df["idcar_200m"].str.extract(pattern).astype(float)
    df["ind"] = pd.to_numeric(df["ind"].str.replace(",", ".", regex=False), errors="coerce")
    valid = coords.notna().all(axis=1) & df["ind"].notna() & (df["ind"] > 0)
    coords = coords.loc[valid]
    pop = df.loc[valid, "ind"].to_numpy(dtype=float)
    if not len(pop):
        raise ValueError("Carreaux de population invalides")
    # L'identifiant INSEE représente le coin inférieur gauche d'une maille de 200m.
    x3035 = coords[1].to_numpy() + 100
    y3035 = coords[0].to_numpy() + 100
    transformer = Transformer.from_crs("EPSG:3035", "EPSG:2154", always_xy=True)
    x, y = transformer.transform(x3035, y3035)
    return np.column_stack([x, y]), pop


def load_existing(geodae_csv, city_code):
    code = str(city_code).zfill(5)
    points = []
    required = {"c_lat_coor1", "c_long_coor1", "c_com_insee"}
    for chunk in _csv_reader(geodae_csv):
        if not required.issubset(chunk.columns):
            raise ValueError(f"Géo'DAE : colonnes attendues absentes : {required - set(chunk.columns)}")
        filtered = chunk[chunk["c_com_insee"].fillna("").str.strip().str.zfill(5) == code].copy()
        if filtered.empty:
            continue
        lat = pd.to_numeric(filtered["c_lat_coor1"].str.replace(",", ".", regex=False), errors="coerce")
        lon = pd.to_numeric(filtered["c_long_coor1"].str.replace(",", ".", regex=False), errors="coerce")
        good = lat.between(41, 52) & lon.between(-6, 11)
        points.extend(zip(lon[good], lat[good]))
    if not points:
        print("Attention : aucun DAE utilisable trouvé pour cette commune dans le fichier.")
        return np.empty((0, 2))
    points = np.unique(np.round(np.asarray(points, dtype=float), 5), axis=0)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    x, y = transformer.transform(points[:, 0], points[:, 1])
    return np.column_stack([x, y])


def make_city_problem(city_code, city_name, radius_m=350, max_candidates=160,
                      geodae_csv=None, insee_zip=None):
    geo_path, insee_path = get_sources(geodae_csv, insee_zip)
    demand, population = load_population(insee_path, city_code)
    existing = load_existing(geo_path, city_code)
    # Contrôle de cohérence géographique : une ligne Géo'DAE peut porter
    # le code INSEE de la commune malgré des coordonnées incorrectes.
    # On exclut uniquement les points à plus de 5 km de l'emprise des
    # carreaux de population : ces points n'affectent pas le calcul local.
    if len(existing):
        buffer_m = 5000.0
        lower = demand.min(axis=0) - buffer_m
        upper = demand.max(axis=0) + buffer_m
        plausible = np.all((existing >= lower) & (existing <= upper), axis=1)
        removed = int((~plausible).sum())
        if removed:
            print(f"Contrôle géographique : {removed} DAE hors secteur exclus "
                  f"(plus de {buffer_m/1000:g} km au-delà des carreaux INSEE).")
        existing = existing[plausible]
    # Les candidats sont des centres des carreaux peuplés. Le plafonnement
    # limite le temps de calcul tout en conservant tous les points de demande.
    order = np.argsort(-population, kind="stable")[:min(max_candidates, len(population))]
    candidates = demand[order]
    return CoverageProblem(demand, population, candidates, existing, radius_m,
                           mode="real", city=city_name)
