"""
Scraper Visual.fr - Toutes les boutiques
1. Récupère les 49 boutiques via l'API markers
2. Visite chaque page boutique pour extraire adresse, téléphone, email
3. Exporte en CSV

Installation :
    pip install requests beautifulsoup4

Usage :
    python visual_scraper.py
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

API_URL    = "https://www.visual.fr/wp-json/geodir/v2/markers/"
BASE_URL   = "https://www.visual.fr"
OUTPUT_CSV = "visual_boutiques.csv"
DELAY      = 1.5

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
    id:          Optional[str]
    nom:         Optional[str]
    adresse:     Optional[str]
    code_postal: Optional[str]
    ville:       Optional[str]
    telephone:   Optional[str]
    fax:         Optional[str]
    email:       Optional[str]
    latitude:    Optional[str]
    longitude:   Optional[str]
    url:         Optional[str]


# ── Parsing fiche boutique ────────────────────────────────────────────────────

def parse_fiche(html: str, url: str) -> dict:
    """Extrait adresse, téléphone, email depuis la page d'une boutique."""
    soup = BeautifulSoup(html, "html.parser")
    result = {
        "adresse": None, "code_postal": None, "ville": None,
        "telephone": None, "fax": None, "email": None,
    }

    # Le bloc contact est dans #infocontactTab
    contact_div = soup.select_one(
        "#infocontactTab .geodir_post_meta, "
        ".text--geodir-field-infocontact, "
        "[class*='geodir-field-infocontact']"
    )

    if not contact_div:
        # Fallback : cherche directement dans toute la page
        contact_div = soup

    # Récupère tous les <li> du bloc
    items = contact_div.select("li")
    for li in items:
        text = li.get_text(strip=True)

        # Téléphone : "Tél : XX XX XX XX XX"
        if text.lower().startswith("tél"):
            raw = re.sub(r"[Tt]él\s*:\s*", "", text).strip()
            result["telephone"] = raw

        # Fax
        elif text.lower().startswith("fax"):
            raw = re.sub(r"[Ff]ax\s*:\s*", "", text).strip()
            result["fax"] = raw

        # Adresse : contient un tiret séparateur "rue - CP Ville"
        elif " - " in text and re.search(r"\d{5}", text):
            # Format : "19 rue de la République - 09100 Pamiers"
            parts = text.split(" - ", 1)
            adresse = parts[0].strip()
            reste   = parts[1].strip() if len(parts) > 1 else ""
            m = re.match(r"(\d{5})\s+(.*)", reste)
            if m:
                result["adresse"]     = adresse
                result["code_postal"] = m.group(1)
                result["ville"]       = m.group(2).strip()
            else:
                result["adresse"] = text

        # Email
        mailto = li.select_one("a[href^='mailto:']")
        if mailto:
            result["email"] = mailto.get_text(strip=True)

    return result


# ── Récupération page boutique ────────────────────────────────────────────────

def get_boutique_url(session: requests.Session, boutique_id: str) -> Optional[str]:
    """
    Trouve l'URL de la fiche boutique depuis l'ID WordPress.
    WordPress redirige /?p=ID vers l'URL finale.
    """
    try:
        resp = session.get(
            f"{BASE_URL}/?p={boutique_id}",
            headers=HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code == 200 and "/magasin/" in resp.url:
            return resp.url
    except Exception:
        pass
    return None


def fetch_fiche(session: requests.Session, url: str) -> Optional[str]:
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        log.warning(f"  ⚠️  Erreur fetch {url} : {e}")
        return None


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
    log.info("🚀 Démarrage du scraper Visual.fr...")
    session = requests.Session()

    # ── Étape 1 : récupère tous les markers ───────────────────────────────
    log.info("Chargement de la liste des boutiques...")
    try:
        resp = session.get(
            API_URL,
            params={"post_type": "gd_place", "country": "France"},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data  = resp.json()
        items = data.get("items", [])
        log.info(f"  → {len(items)} boutiques trouvées")
    except Exception as e:
        log.error(f"❌ Erreur API markers : {e}")
        return

    # ── Étape 2 : visite chaque fiche boutique ────────────────────────────
    all_boutiques: list[Boutique] = []

    for i, item in enumerate(items, 1):
        boutique_id = item.get("m", "")
        nom         = item.get("t", "")
        lat         = item.get("lt", "")
        lon         = item.get("ln", "")

        log.info(f"[{i}/{len(items)}] {nom} (ID: {boutique_id})...")

        # Trouve l'URL via redirection WordPress /?p=ID
        url = get_boutique_url(session, boutique_id)
        if not url:
            log.warning(f"  ⚠️  URL introuvable pour ID {boutique_id}")
            all_boutiques.append(Boutique(
                id=boutique_id, nom=nom, adresse=None, code_postal=None,
                ville=None, telephone=None, fax=None, email=None,
                latitude=lat, longitude=lon, url=None,
            ))
            time.sleep(DELAY)
            continue

        log.info(f"  → {url}")

        # Scrape la fiche
        html = fetch_fiche(session, url)
        if not html:
            all_boutiques.append(Boutique(
                id=boutique_id, nom=nom, adresse=None, code_postal=None,
                ville=None, telephone=None, fax=None, email=None,
                latitude=lat, longitude=lon, url=url,
            ))
            time.sleep(DELAY)
            continue

        details = parse_fiche(html, url)

        if details["telephone"]:
            log.info(f"  ✅ Tél : {details['telephone']} | {details.get('adresse', '')} {details.get('code_postal', '')} {details.get('ville', '')}")
        else:
            log.info(f"  ❌ Pas de téléphone trouvé")

        all_boutiques.append(Boutique(
            id=boutique_id,
            nom=nom,
            adresse=details["adresse"],
            code_postal=details["code_postal"],
            ville=details["ville"],
            telephone=details["telephone"],
            fax=details["fax"],
            email=details["email"],
            latitude=lat,
            longitude=lon,
            url=url,
        ))

        time.sleep(DELAY)

    # ── Export ────────────────────────────────────────────────────────────
    log.info(f"\n{'='*50}")
    found = sum(1 for b in all_boutiques if b.telephone)
    log.info(f"Total : {len(all_boutiques)} boutiques | Tél trouvés : {found}")
    export_csv(all_boutiques, OUTPUT_CSV)


if __name__ == "__main__":
    main()