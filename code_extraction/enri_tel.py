"""
Enrichissement CSV Jimmy Fairly - Numéros de téléphone via Google Maps
Scrape maps.google.com pour chaque boutique

Installation :
    pip install playwright beautifulsoup4
    python -m playwright install chromium

Usage :
    python enrichissement_telephone_v2.py
"""

import csv
import time
import re
import logging
from playwright.sync_api import sync_playwright

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_CSV  = "jimmy_fairly_boutiques.csv"
OUTPUT_CSV = "jimmy_fairly_avec_tel.csv"
DELIMITER  = ";"
DELAY      = 2.0
HEADLESS   = False  # Passe à False pour voir le navigateur défiler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Nettoyage numéro ──────────────────────────────────────────────────────────

def clean_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("0"):
        return digits
    if digits.startswith("33") and len(digits) == 11:
        return "0" + digits[2:]
    return digits if len(digits) >= 9 else ""


# ── Recherche Google Maps ─────────────────────────────────────────────────────

def search_google_maps(page, nom: str, adresse: str, ville: str) -> str:
    """
    Cherche 'Jimmy Fairly + adresse' sur Google Maps et extrait le téléphone.
    """
    query = f"Jimmy Fairly {adresse} {ville} France"
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(2.5)

        # ── Accepte les cookies Google si la popup apparaît ──
        try:
            consent_btn = page.query_selector(
                "button[aria-label*='Tout accepter'], "
                "button[aria-label*='Accept all'], "
                "form:nth-child(2) button"
            )
            if consent_btn:
                consent_btn.click()
                time.sleep(1.5)
        except Exception:
            pass

        # ── Si plusieurs résultats, clique sur le premier ──
        try:
            first = page.query_selector(
                "a[href*='/maps/place/'], "
                "[class*='hfpxzc']"          # classe interne Google Maps
            )
            if first:
                first.click()
                time.sleep(2.5)
        except Exception:
            pass

        # ── Cherche le numéro de téléphone dans la fiche ──
        # Google Maps met le tel dans un bouton avec aria-label contenant le numéro
        phone_selectors = [
            "button[data-item-id*='phone']",
            "button[aria-label*='Appeler']",
            "button[aria-label*='Phone']",
            "[data-tooltip*='Copier le numéro']",
            "a[href^='tel:']",
        ]

        for selector in phone_selectors:
            els = page.query_selector_all(selector)
            for el in els:
                # Essaie aria-label en premier (contient souvent le numéro)
                label = el.get_attribute("aria-label") or ""
                href  = el.get_attribute("href") or ""
                text  = el.inner_text().strip()

                for raw in [label, href, text]:
                    cleaned = clean_phone(raw)
                    if cleaned:
                        return cleaned

        # ── Fallback : cherche dans tout le texte de la page ──
        content = page.inner_text("body")
        # Cherche un pattern de numéro FR : 0X XX XX XX XX
        matches = re.findall(r"0[1-9](?:[\s.\-]?\d{2}){4}", content)
        for match in matches:
            cleaned = clean_phone(match)
            if cleaned:
                return cleaned

    except Exception as e:
        log.warning(f"  ⚠️  Erreur Maps pour '{nom}' : {e}")

    return ""


# ── Lecture CSV ───────────────────────────────────────────────────────────────

def load_csv(filepath: str) -> tuple[list[dict], list[str]]:
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=DELIMITER)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("📞 Enrichissement téléphonique via Google Maps...")

    rows, fieldnames = load_csv(INPUT_CSV)
    total = len(rows)
    log.info(f"  → {total} boutiques à traiter")

    if "telephone" not in fieldnames:
        fieldnames = fieldnames + ["telephone"]

    found_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            geolocation={"longitude": 2.3522, "latitude": 48.8566},
            permissions=["geolocation"],
        )
        page = context.new_page()

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f_out:
            writer = csv.DictWriter(
                f_out,
                fieldnames=fieldnames,
                delimiter=DELIMITER,
                quoting=csv.QUOTE_ALL,
                extrasaction="ignore",
            )
            writer.writeheader()

            for i, row in enumerate(rows, 1):
                nom     = row.get("nom", "")
                adresse = row.get("adresse", "")
                ville   = row.get("ville", "")

                log.info(f"[{i}/{total}] {nom} — {ville}...")

                tel = search_google_maps(page, nom, adresse, ville)
                row["telephone"] = tel

                if tel:
                    found_count += 1
                    log.info(f"  ✅ {tel}")
                else:
                    log.info(f"  ❌ Non trouvé")

                writer.writerow(row)

                if i < total:
                    time.sleep(DELAY)

        browser.close()

    # ── Résumé final ──────────────────────────────────────────────────────────
    log.info(f"\n{'='*50}")
    log.info(f"✅ Terminé ! Fichier : {OUTPUT_CSV}")
    log.info(f"   Trouvés    : {found_count}/{total}")
    log.info(f"   Manquants  : {total - found_count}/{total}")


if __name__ == "__main__":
    main()