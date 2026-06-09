"""
Scraper Lissac - Toutes les boutiques de France
Stratégie : requête par grande ville + dédoublonnage par ID

Installation :
    pip install requests beautifulsoup4

Usage :
    python lissac_scraper.py
"""

import csv
import time
import re
import logging
from dataclasses import dataclass, fields, astuple
from typing import Optional
import requests
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────

API_URL    = "https://opticien.lissac.fr/resultats"
OUTPUT_CSV = "lissac_boutiques.csv"
DELAY      = 0.8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://opticien.lissac.fr/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Liste des villes avec coordonnées + bbox ──────────────────────────────────
# Format : (nom, lat, lon, south, west, north, east)
# Bbox assez large pour couvrir toute l'agglomération

VILLES = [
    # Île-de-France
    ("Paris",         48.8575, 2.3514,  48.8155, 2.2242,  48.9021, 2.4699)
]


# ── Modèle ────────────────────────────────────────────────────────────────────

@dataclass
class Boutique:
    id:           Optional[str]
    nom:          Optional[str]
    adresse:      Optional[str]
    code_postal:  Optional[str]
    ville:        Optional[str]
    telephone:    Optional[str]
    note:         Optional[str]
    nb_avis:      Optional[str]
    statut:       Optional[str]
    url_boutique: Optional[str]


# ── Formatage téléphone ───────────────────────────────────────────────────────

def format_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("33") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) == 10:
        return " ".join(digits[i:i+2] for i in range(0, 10, 2))
    return raw


# ── Parsing HTML ──────────────────────────────────────────────────────────────

def parse_items(html: str) -> list[Boutique]:
    soup = BeautifulSoup(html, "html.parser")
    boutiques = []

    for article in soup.select("article.b-result"):

        # ID
        article_id = None
        id_el = article.find(id=re.compile(r"result-\d+"))
        if id_el:
            article_id = id_el["id"].replace("result-", "")

        # Nom + URL
        lien = article.select_one("a[href*='lissac.fr']")
        nom          = lien.get_text(strip=True) if lien else None
        url_boutique = lien["href"] if lien else None

        # Adresse
        addr_tag = article.select_one(".b-result__address")
        adresse = code_postal = ville = None
        if addr_tag:
            parts = [t.strip() for t in addr_tag.stripped_strings]
            rue = parts[0] if len(parts) > 0 else None
            cp  = parts[1] if len(parts) > 1 else None
            vil = parts[2] if len(parts) > 2 else None
            code_postal = cp
            ville       = vil
            adresse     = f"{rue}, {cp} {vil}" if rue and cp and vil else addr_tag.get_text(strip=True)

        # Téléphone
        tel_tag   = article.select_one("a[href^='tel:']")
        telephone = None
        if tel_tag:
            label = tel_tag.get("aria-label", "").strip()
            telephone = label if label else format_phone(
                tel_tag.get("href", "").replace("tel:", "")
            )

        # Note
        note_tag = article.select_one(".b-rating__grade")
        note     = note_tag.get_text(strip=True) if note_tag else None

        avis_tag = article.select_one(".b-rating__count")
        nb_avis  = re.sub(r"[^\d]", "", avis_tag.get_text()) if avis_tag else None

        # Statut
        statut_tag = article.select_one(".b-today")
        statut     = re.sub(r"\s+", " ", statut_tag.get_text(strip=True)) if statut_tag else None

        boutiques.append(Boutique(
            id=article_id, nom=nom, adresse=adresse,
            code_postal=code_postal, ville=ville,
            telephone=telephone, note=note, nb_avis=nb_avis,
            statut=statut, url_boutique=url_boutique,
        ))

    return boutiques


# ── Appel API ─────────────────────────────────────────────────────────────────

def fetch_ville(session: requests.Session, ville_data: tuple) -> list[Boutique]:
    nom_ville, lat, lon, south, west, north, east = ville_data
    all_b = []

    params = {
        "q": f"{nom_ville}, France",
        "p": f"{lat},{lon}",
        "s": "geocoder",
        "b": f"{south},{west},{north},{east}",
        "__xhr": "1",
        "page": 1,
    }

    try:
        resp = session.get(API_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data      = resp.json()
        results   = data.get("results", {})
        last_page = results.get("last_page", 1)
        total     = results.get("total", 0)

        log.info(f"  {nom_ville} : {total} boutiques, {last_page} page(s)")

        all_b.extend(parse_items(results.get("items", "")))

        for page_num in range(2, last_page + 1):
            time.sleep(DELAY)
            params["page"] = page_num
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            all_b.extend(parse_items(data.get("results", {}).get("items", "")))

    except Exception as e:
        log.warning(f"  ⚠️  Erreur {nom_ville} : {e}")

    return all_b


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
    log.info(f"🚀 Scraper Lissac — {len(VILLES)} zones à couvrir")
    session     = requests.Session()
    all_boutiques: list[Boutique] = []
    seen_ids:   set[str] = set()

    for i, ville_data in enumerate(VILLES, 1):
        log.info(f"[{i}/{len(VILLES)}] {ville_data[0]}...")
        boutiques = fetch_ville(session, ville_data)

        # Dédoublonnage par ID
        nouvelles = 0
        for b in boutiques:
            key = b.id or b.url_boutique or b.nom
            if key and key not in seen_ids:
                seen_ids.add(key)
                all_boutiques.append(b)
                nouvelles += 1

        log.info(f"    → {nouvelles} nouvelles boutiques (total : {len(all_boutiques)})")
        time.sleep(DELAY)

    log.info(f"\n{'='*50}")
    log.info(f"Total boutiques uniques : {len(all_boutiques)}")

    if all_boutiques:
        export_csv(all_boutiques, OUTPUT_CSV)
    else:
        log.error("❌ Aucune boutique trouvée.")


if __name__ == "__main__":
    main()