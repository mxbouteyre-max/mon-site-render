"""
Scraper Jimmy Fairly - Toutes les boutiques de France
Les données sont embarquées directement dans le HTML en GeoJSON.
Pas besoin de Playwright !

Installation :
    pip install requests beautifulsoup4

Usage :
    python jimmy_fairly_scraper.py
"""

import csv
import re
import json
import logging
from dataclasses import dataclass, fields, astuple
from typing import Optional
import requests
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────

URL        = "https://www.jimmyfairly.com/fr/pages/stores"
OUTPUT_CSV = "jimmy_fairly_boutiques.csv"
BASE_URL   = "https://www.jimmyfairly.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Modèle ────────────────────────────────────────────────────────────────────

@dataclass
class Boutique:
    id:           Optional[str]
    nom:          Optional[str]
    titre:        Optional[str]
    pays:         Optional[str]
    code:         Optional[str]
    adresse:      Optional[str]
    cp:  Optional[str]
    ville:        Optional[str]
    latitude:     Optional[str]
    longitude:    Optional[str]
    url: Optional[str]


# ── Parsing ───────────────────────────────────────────────────────────────────

def format_horaire(h: str) -> str:
    """Convertit '1000-2000' → '10:00 - 20:00', '' → 'Fermée'."""
    if not h:
        return "Fermée"
    # Gère les créneaux multiples ex: "1100-1300-1400-1900"
    parts = h.split("-")
    heures = []
    for i in range(0, len(parts) - 1, 2):
        debut = parts[i].zfill(4)
        fin   = parts[i+1].zfill(4)
        heures.append(f"{debut[:2]}:{debut[2:]} - {fin[:2]}:{fin[2:]}")
    return " / ".join(heures) if heures else h


def extract_adresse(raw: str):
    """Extrait code postal et ville depuis une adresse complète."""
    m = re.search(r"(\d{5})\s+([^,]+)", raw)
    if m:
        return m.group(1), m.group(2).strip()
    return None, None


def parse_geojson(geojson: dict, france_only: bool = True) -> list[Boutique]:
    boutiques = []
    features = geojson.get("features", [])

    for feature in features:
        props = feature.get("properties", {})
        geo   = feature.get("geometry", {})

        pays = props.get("country", "")
        if france_only and pays.lower() != "france":
            continue

        adresse_raw = props.get("address", "")
        cp, ville   = extract_adresse(adresse_raw)

        oh = props.get("opening_hours", {})

        url_relative = props.get("url", "")
        url_boutique = BASE_URL + url_relative if url_relative else None

        coords = geo.get("coordinates", [None, None])

        boutiques.append(Boutique(
            id=str(props.get("id", "")),
            nom=props.get("name", ""),
            titre=props.get("title", ""),
            pays=pays,
            code=props.get("code", ""),
            adresse=adresse_raw,
            cp=cp,
            ville=ville,
            latitude=str(coords[1]) if coords[1] else None,
            longitude=str(coords[0]) if coords[0] else None,
            url=url_boutique,
        ))

    return boutiques


# ── Export CSV ────────────────────────────────────────────────────────────────

def export_csv(boutiques: list[Boutique], filepath: str):
    col_names = [f.name for f in fields(Boutique)]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerow(col_names)
        for b in boutiques:
            writer.writerow(astuple(b))
    log.info(f"✅ CSV exporté : {filepath} ({len(boutiques)} boutiques)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("🚀 Démarrage du scraper Jimmy Fairly...")
    log.info(f"Chargement de {URL} ...")

    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Le GeoJSON est dans un <script type="application/json" x-ref="json">
    script_tag = soup.find("script", {"type": "application/json", "x-ref": "json"})

    if not script_tag:
        # Fallback : cherche n'importe quel script contenant "FeatureCollection"
        log.warning("Tag principal non trouvé, recherche fallback...")
        for tag in soup.find_all("script", {"type": "application/json"}):
            if "FeatureCollection" in (tag.string or ""):
                script_tag = tag
                break

    if not script_tag:
        log.error("❌ Impossible de trouver le bloc GeoJSON dans le HTML.")
        log.error("Le site a peut-être changé de structure.")
        return

    try:
        geojson = json.loads(script_tag.string)
    except json.JSONDecodeError as e:
        log.error(f"❌ Erreur de parsing JSON : {e}")
        return

    total_features = len(geojson.get("features", []))
    log.info(f"GeoJSON trouvé : {total_features} boutiques au total (tous pays)")

    boutiques = parse_geojson(geojson, france_only=True)
    log.info(f"Boutiques France uniquement : {len(boutiques)}")

    if boutiques:
        export_csv(boutiques, OUTPUT_CSV)

        # Aperçu des 3 premières
        log.info("\n── Aperçu ──────────────────────────────────")
        for b in boutiques[:3]:
            log.info(f"  {b.nom} | {b.adresse} ")
    else:
        log.warning("Aucune boutique française trouvée.")


if __name__ == "__main__":
    main()