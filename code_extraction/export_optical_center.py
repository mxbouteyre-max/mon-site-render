"""
Scraper Optical Center v2 - Mode Playwright + interception réseau
Détecte automatiquement si une API est utilisée, sinon parse le HTML rendu.

Installation :
    pip install playwright beautifulsoup4
    playwright install chromium

Usage :
    python optical_center_scraper_v2.py
"""

import csv
import time
import re
import json
import logging
from dataclasses import dataclass, fields, astuple
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Response

# ── Configuration ─────────────────────────────────────────────────────────────

STORE_LOCATOR_URL = "https://www.optical-center.fr/magasins"
BASE_URL          = "https://www.optical-center.fr"
OUTPUT_CSV        = "optical_center_boutiques.csv"
DELAY             = 1.5   # secondes entre chaque page
HEADLESS          = True  # False pour voir le navigateur

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Modèle ────────────────────────────────────────────────────────────────────

@dataclass
class Boutique:
    nom:          Optional[str]
    adresse:      Optional[str]
    code_postal:  Optional[str]
    ville:        Optional[str]
    telephone:    Optional[str]
    horaires:     Optional[str]
    statut:       Optional[str]
    type_service: Optional[str]
    url_page:     Optional[str]
    url_maps:     Optional[str]


# ── Interception réseau ───────────────────────────────────────────────────────

intercepted_api_calls: list[dict] = []

def handle_response(response: Response):
    """Capture toutes les réponses JSON qui ressemblent à un store locator."""
    url = response.url
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type:
        return
    # Filtre les URLs qui semblent liées aux magasins
    keywords = ["store", "magasin", "location", "boutique", "shop", "loca"]
    if not any(k in url.lower() for k in keywords):
        return
    try:
        body = response.json()
        intercepted_api_calls.append({"url": url, "body": body})
        log.info(f"🔍 API interceptée : {url}")
    except Exception:
        pass


# ── Parsing HTML ──────────────────────────────────────────────────────────────

def parse_html(html: str) -> list[Boutique]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    boutiques = []

    items = soup.select("li")
    for li in items:
        nom_tag = li.select_one("[data-e2e-location-name]")
        if not nom_tag:
            continue
        nom = nom_tag.get_text(strip=True)
        if not nom:
            continue

        street = li.select_one("[data-e2e-address-street]")
        city   = li.select_one("[data-e2e-address-city]")

        adresse  = street.get_text(strip=True) if street else None
        ville_raw = city.get_text(strip=True) if city else None
        code_postal, ville = None, None
        if ville_raw:
            m = re.match(r"(\d{5})\s*(.*)", ville_raw)
            if m:
                code_postal, ville = m.group(1), m.group(2).strip()
            else:
                ville = ville_raw

        tel_tag   = li.select_one("a[href^='tel:']")
        telephone = tel_tag.get_text(strip=True) if tel_tag else None

        status_tag = li.select_one("[class*='status__message']")
        statut     = status_tag.get_text(strip=True) if status_tag else None

        type_tag     = li.select_one("[class*='__type']")
        type_service = type_tag.get_text(strip=True) if type_tag else None

        horaires_tags = li.select("[class*='hours'] span, [class*='horaire'] span")
        horaires = " | ".join(t.get_text(strip=True) for t in horaires_tags) or None

        lien_tag = li.select_one("a[href*='/magasins/']")
        url_page = None
        if lien_tag and lien_tag.get("href"):
            href = lien_tag["href"]
            url_page = href if href.startswith("http") else BASE_URL + href

        maps_tag = li.select_one("a[href*='google.com/maps']")
        url_maps = maps_tag["href"] if maps_tag else None

        boutiques.append(Boutique(
            nom=nom, adresse=adresse, code_postal=code_postal, ville=ville,
            telephone=telephone, horaires=horaires, statut=statut,
            type_service=type_service, url_page=url_page, url_maps=url_maps,
        ))

    return boutiques


# ── Parsing réponse API (si interceptée) ─────────────────────────────────────

def parse_api_response(body: dict | list) -> list[Boutique]:
    """
    Tente de parser une réponse JSON générique de store locator.
    À affiner selon la vraie structure de l'API.
    """
    boutiques = []

    # Cherche une liste dans la réponse
    items = []
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        # Clés communes : "results", "stores", "locations", "data", "items"
        for key in ("results", "stores", "locations", "data", "items", "features"):
            if key in body and isinstance(body[key], list):
                items = body[key]
                break

    for item in items:
        if not isinstance(item, dict):
            continue

        def get(*keys):
            """Cherche une valeur parmi plusieurs clés possibles."""
            for k in keys:
                if k in item and item[k]:
                    return str(item[k])
                # Cherche dans les sous-dicts courants
                for sub in ("address", "contact", "properties", "store"):
                    if sub in item and isinstance(item[sub], dict):
                        if k in item[sub] and item[sub][k]:
                            return str(item[sub][k])
            return None

        nom          = get("name", "storeName", "nom", "title", "label")
        adresse      = get("address", "street", "address1", "rue", "streetAddress")
        code_postal  = get("zipCode", "postalCode", "zip", "codePostal", "postcode")
        ville        = get("city", "ville", "locality", "town")
        telephone    = get("phone", "tel", "telephone", "phoneNumber")
        url_page     = get("url", "storeUrl", "link", "href")
        type_service = get("type", "category", "storeType")

        boutiques.append(Boutique(
            nom=nom, adresse=adresse, code_postal=code_postal, ville=ville,
            telephone=telephone, horaires=None, statut=None,
            type_service=type_service,
            url_page=url_page if url_page and url_page.startswith("http") else (BASE_URL + url_page if url_page else None),
            url_maps=None,
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


# ── Scraping avec Playwright ──────────────────────────────────────────────────

def detect_next_page(page: Page) -> Optional[str]:
    """Retourne l'URL de la page suivante si elle existe, sinon None."""
    try:
        # Cherche un lien "suivant" ou "next"
        next_btn = page.query_selector(
            "a[class*='next'], a[rel='next'], [aria-label*='suivant'], "
            "[aria-label*='next'], [class*='pagination__next']"
        )
        if next_btn:
            href = next_btn.get_attribute("href")
            if href:
                return href if href.startswith("http") else BASE_URL + href
    except Exception:
        pass
    return None


def has_more_results(page: Page, prev_count: int) -> bool:
    """Vérifie s'il y a encore des boutiques non chargées (scroll infini)."""
    try:
        items = page.query_selector_all("[data-e2e-location-name]")
        return len(items) > prev_count
    except Exception:
        return False


def main():
    log.info("🚀 Démarrage du scraper Optical Center v2 (Playwright)...")
    all_boutiques: list[Boutique] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
        )
        page = context.new_page()

        # Active l'interception réseau
        page.on("response", handle_response)

        log.info(f"Chargement de {STORE_LOCATOR_URL} ...")
        page.goto(STORE_LOCATOR_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ── Cas 1 : Une API a été interceptée ────────────────────────────────
        if intercepted_api_calls:
            log.info(f"✨ {len(intercepted_api_calls)} appel(s) API intercepté(s) !")
            log.info("Dump des URLs interceptées :")
            for call in intercepted_api_calls:
                log.info(f"  → {call['url']}")
                # Sauvegarde le JSON brut pour analyse
                with open("api_response_dump.json", "w", encoding="utf-8") as f:
                    json.dump(call["body"], f, ensure_ascii=False, indent=2)
                log.info("    JSON sauvegardé dans api_response_dump.json")

            # Tente de parser la première réponse API
            boutiques = parse_api_response(intercepted_api_calls[0]["body"])
            if boutiques:
                log.info(f"  → {len(boutiques)} boutiques parsées depuis l'API")
                all_boutiques.extend(boutiques)
            else:
                log.warning("  Parse API a retourné 0 résultats — voir api_response_dump.json")

        # ── Cas 2 : Pagination classique ─────────────────────────────────────
        else:
            log.info("Pas d'API détectée — parsing HTML page par page...")
            page_num = 1

            while True:
                log.info(f"  Page {page_num} : parsing HTML...")
                html = page.content()
                boutiques = parse_html(html)

                if not boutiques:
                    # Essaie de scroller pour déclencher un éventuel lazy load
                    log.info("  0 boutiques — tentative de scroll...")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    html = page.content()
                    boutiques = parse_html(html)

                log.info(f"  → {len(boutiques)} boutiques trouvées")
                all_boutiques.extend(boutiques)

                # Cherche la page suivante
                next_url = detect_next_page(page)
                if not next_url:
                    log.info("  Fin de la pagination.")
                    break

                log.info(f"  → Page suivante : {next_url}")
                time.sleep(DELAY)
                page.goto(next_url, wait_until="networkidle", timeout=30000)
                page_num += 1

        browser.close()

    # ── Résumé ────────────────────────────────────────────────────────────────
    log.info(f"\n{'='*50}")
    log.info(f"Total boutiques récupérées : {len(all_boutiques)}")

    if all_boutiques:
        export_csv(all_boutiques, OUTPUT_CSV)
    else:
        log.error(
            "❌ Toujours 0 boutiques.\n"
            "Pistes :\n"
            "  1. Ouvre api_response_dump.json pour voir la structure de l'API\n"
            "  2. Passe HEADLESS=False pour voir ce que charge le navigateur\n"
            "  3. Le site bloque peut-être les bots — essaie avec un vrai navigateur\n"
        )


if __name__ == "__main__":
    main()