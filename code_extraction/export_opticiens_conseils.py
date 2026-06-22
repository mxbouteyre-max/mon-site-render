"""
export_opticiens_conseils.py

Optimisation principale vs version précédente :
  - Blocage des ressources inutiles via Chrome DevTools Protocol (CDP) :
    images, fonts, media, feuilles de style, scripts tiers (analytics,
    CDN Shopify...) ne sont plus téléchargés. On ne charge que le HTML
    et les scripts strictement nécessaires au rendu du contenu.
    → Division du temps par page estimée par 3 à 5.
  - wait_until="domcontentloaded" au lieu de "networkidle" : on n'attend
    plus que toutes les requêtes réseau soient terminées, juste que le
    DOM soit prêt.
"""

import re
from bs4 import BeautifulSoup
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

BASE_URL  = "https://www.opticienconseil.fr"
START_URL = f"{BASE_URL}/a/magasins"
OUTPUT    = "opticiens_conseils.csv"

# Types de ressources à bloquer — on ne garde que "document" et "script"
# (nécessaires pour le rendu JS du store locator Shopify)
BLOCKED_RESOURCE_TYPES = {
    "image", "media", "font", "stylesheet",
    "texttrack", "manifest", "other",
}

# Domaines tiers à bloquer (analytics, CDN images, etc.)
BLOCKED_DOMAINS = {
    "cdn.shopify.com",
    "cdn-gkefn.nitrocdn.com",
    "googletagmanager.com",
    "google-analytics.com",
    "facebook.net",
    "connect.facebook.net",
    "static.hotjar.com",
    "widget.trustpilot.com",
}


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Désactive le chargement d'images au niveau Chrome (en plus du CDP)
    options.add_experimental_option(
        "prefs", {"profile.managed_default_content_settings.images": 2}
    )
    return webdriver.Chrome(options=options)


def enable_request_blocking(driver):
    """Active l'interception réseau via CDP et bloque les ressources inutiles."""
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setBlockedURLs", {
        "urls": [f"*{domain}*" for domain in BLOCKED_DOMAINS]
    })


driver = make_driver()
enable_request_blocking(driver)
wait = WebDriverWait(driver, 20)

try:
    # ─────────────────────────────────────────────────────────
    # ÉTAPE 1 : Collecte des URLs de boutiques
    # ─────────────────────────────────────────────────────────
    print("Ouverture de la page boutiques…")
    driver.get(START_URL)

    try:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'a[href*="/a/magasins/boutiques/"]')
            )
        )
    except TimeoutException:
        print("⚠ Timeout : aucun lien de boutique trouvé après 20s.")

    links = set()
    for el in driver.find_elements(
        By.CSS_SELECTOR, 'a[href*="/a/magasins/boutiques/"]'
    ):
        href = el.get_attribute("href")
        if href:
            href = href.split("?")[0].split("#")[0]
            links.add(href)

    links = sorted(links)
    print(f"{len(links)} boutiques trouvées")

    # ─────────────────────────────────────────────────────────
    # ÉTAPE 2 : Scraping de chaque fiche
    # ─────────────────────────────────────────────────────────
    rows = []

    for i, url in enumerate(links, start=1):
        print(f"[{i}/{len(links)}] {url}")

        try:
            driver.get(url)

            try:
                wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
            except TimeoutException:
                print(f"  ⚠ Timeout sur {url}, on continue")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            data = {
                "url": url,
                "nom": "",
                "adresse": "",
                "telephone": "",
                "email": "",
            }

            # NOM
            h1 = soup.find("h1")
            if h1:
                data["nom"] = clean_text(h1.get_text())

            # ADRESSE — lien Google Maps en priorité (contient le CP)
            maps_link = soup.find(
                "a", href=lambda h: h and "google.com/maps/dir" in h
            )
            if maps_link:
                data["adresse"] = clean_text(maps_link.get_text(" "))
            else:
                address = soup.select_one(".store-address-link p")
                if address:
                    data["adresse"] = clean_text(address.get_text(" "))

            # TELEPHONE
            tel = soup.select_one('a[href^="tel:"]')
            if tel:
                data["telephone"] = (
                    tel.get("data-phone") or clean_text(tel.get_text())
                )

            # EMAIL
            email = soup.select_one('a[href^="mailto:"]')
            if email:
                data["email"] = (
                    email.get("data-email")
                    or email.get("href", "").replace("mailto:", "").strip()
                )

            rows.append(data)

        except WebDriverException as e:
            print(f"  ⚠ Erreur WebDriver : {e}")

finally:
    driver.quit()

# ─────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)

df.to_csv(OUTPUT, sep=";", encoding="utf-8-sig", index=False)

print(f"\nCSV généré : {OUTPUT}  ({len(df)} boutiques)")